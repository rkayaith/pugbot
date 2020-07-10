import asyncio
import contextlib
from dataclasses import dataclass, field, replace
from typing import Dict, NamedTuple, FrozenSet

from discord.ext.commands import Bot

class React(NamedTuple):
    user_id: int
    emoji: str

@dataclass(frozen=True)
class State:
    reacts: FrozenSet[React]
    async def on_update(self, reacts: FrozenSet[React]):
        yield replace(self, reacts=reacts)

# TODO: figure out how to make everything work with this being immutable
@dataclass
class BotStatus:
    bot: Bot
    states: Dict[int, State] = field(default_factory=dict)
    tasks: Dict[int, asyncio.Task] = field(default_factory=dict)

    def set_state(self, channel_id, state):
        self.states[channel_id] = state



async def on_raw_reaction_add(event):
    add_reacts = { React(event.user_id, event.emoji.name) }
    await schedule_state_update(event.channel_id, lambda r: r | add_reacts)

async def on_raw_reaction_remove(event):
    remove_reacts = { React(event.user_id, event.emoji.name) }
    await schedule_state_update(event.channel_id, lambda r: r - remove_reacts)

async def on_state_change(status, prev_state, next_state):
    # TODO: some stuff
    pass

async def run_state_update(status, curr_state, next_reacts, on_change=on_state_change):
    with contextlib.suppress(asyncio.CancelledError):
        async for next_state in curr_state.on_update(next_reacts):
            t = asyncio.create_task(on_change(status, curr_state, next_state))
            try:
                await asyncio.shield(t)
                yield (curr_state := next_state)
            except asyncio.CancelledError:
                await t
                yield next_state
                return

async def schedule_state_update(status, channel_id, update_reacts, run_update=run_state_update):
    """
    Schedule an update for the 'channel_id' state. Any currently running updates for the state are cancelled, and the
    """
    # NOTE: We can guarantee that we can't be preempted by not 'await'ing anything.

    # Wait until there's no pending state updates. We 'cancel()' any running
    # tasks to hurry them along.
    while (task := status.tasks.get(channel_id)) is not None:
        task.cancel()
        await asyncio.sleep(0)
        # swallow 'task' related errors, since they'll be handled below
        with contextlib.suppress(Exception):
            await task
    curr_state = status.states[channel_id]

    # update the current state
    async def apply_update():
        async for state in run_update(status, curr_state, next_reacts):
            status.set_state(channel_id, state)
    next_reacts = frozenset(update_reacts(curr_state.reacts))
    try:
        status.tasks[channel_id] = asyncio.create_task(apply_update())
        await status.tasks[channel_id]
    finally:
        del status.tasks[channel_id]



""" sketch """
async def update_reacts(bot, ctx, chan_id, msg_id, update_fn):
    async with ctx.lock:
        # we only track reacts to the main message
        # TODO: track reacts to all messages?
        if msg_id != msg_id_map[main]:
            return
        ctx.reacts = (reacts := frozenset(update_fn(ctx.reacts)))
        prev_state = ctx.state

    async for next_state in prev_state.on_update(bot, reacts=reacts):
        async with ctx.lock:
            # if someone changed the state while we were getting the next one,
            # so we can stop here
            if ctx.state is not prev_state:
                return

            # apply changes to discord
            tasks = update_discord(bot, ctx, chan_id, prev_state, next_state)
            await asyncio.gather(tasks)
        prev_state = next_state
