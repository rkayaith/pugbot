import asyncio
import contextlib
from dataclasses import dataclass, replace
from typing import NamedTuple, FrozenSet

class React(NamedTuple):
    user_id: int
    emoji: str

@dataclass(frozen=True)
class State:
    reacts: FrozenSet[React]
    async def on_update(self, reacts: FrozenSet[React]):
        yield replace(self, reacts=reacts)



async def get_state(channel_id):
    pass


async def schedule_update(states, tasks, channel_id, /, add_reacts=set(), remove_reacts=set()):
    # NOTE: We can guarantee that we can't be preempted by not 'await'ing anything.

    # Wait until there's no pending state updates. We 'cancel()' any running
    # tasks to hurry them along.
    while (task := tasks.get(channel_id)) is not None:
        task.cancel()
        await asyncio.sleep(0)
        # swallow 'task' related errors, since they'll be handled below
        with contextlib.suppress(Exception):
            await task
    curr_state = states[channel_id]

    # update the current state
    next_reacts = curr_state.reacts - remove_reacts | add_reacts
    async def run_updates():
        async for state in apply_update(curr_state, next_reacts):
            states[channel_id] = state
    try:
        tasks[channel_id] = asyncio.create_task(run_updates())
        await tasks[channel_id]
    finally:
        del tasks[channel_id]


async def on_raw_reaction_add(event):
    reacts = { (event.user_id, event.emoji.name) }
    await schedule_update(event.channel_id, add_reacts=reacts)

    """
    curr_state = await get_state(event.channel_id)
    next_reactions = curr_state.reactions | { reaction }
    next_state = await schedule_update(curr_state, next_reactions)
    states[channel_id] = next_state
    """

async def apply_update(curr_state, next_reacts):
    async for next_state in curr_state.on_update(next_reacts):
        # do stuff based on difference between curr_state and next_state
        async def apply_changes(curr, next):
            pass

        t = asyncio.create_task(apply_changes(curr_state, next_state))
        try:
            await asyncio.shield(t)
            yield (curr_state := next_state)
        except asyncio.CancelledError:
            await t
            yield next_state
            return
