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

def on_react_add(react, channel_id, msg_id):
    if msg_id not in status.msgs_to_watch:
        return
    def on_update(functor):
        def f(prev):
            n = functor(prev)
            status.msgs_to_watch = state.msg_to_watch - p.msg_ids | { n.msg_id }
        return f


    tasks[channel_id], result = schedule_task(tasks[channel_id], update_reacts(lambda r: r | { react }))
    await result


msg_id_update = Observable()

@msg_id_update.watch
def msgs_to_watch(prev_msg_ids, next_msg_ids, curr_val = fset()):
    return curr_val - prev_msg_ids | next_msg_ids

class Observable:
    subbers: list
    values: dict

    def sub(func):
        self.subbers.append(func)

    def unsub(func):
        self.subbers.remove(func)

    def pub(*args):
        for func in self.subbers:
            func(*args)

    def watch(func):
        def update_value(*args):
            args = (*args, self.values[func]) if func in self.values else args
            self.values[func] = func(*args)
        self.sub(update_value)
        return (lambda: self.values[func])

    @contextmanager
    def collect():
        events = []
        collect_event = lambda *event: events.append(event)
        self.sub(collect_event)
        yield events
        self.unsub(collect_event)

def some_watch_fn(
msg_ids
msg_ids = defaultdict(lambda: (o := Observable(), o.watch(some_watch_fn))[0])


on_change = [
    lambda p, n: g.msgs_to_watch = msgs_to_watch(g.msgs_to_watch, p, n),
    lambda p, n: g.
]

async def update_discord(msg_ids, prev_state, next_state):
    

"""
Per-channel states:
    current state/task
    msg_ids

Observable: state[channel_id]
Subscribers:
    - update_discord(bot?, channel, prev, next)
    - msgs_to_watch(prev, next)
    - channel_to_msg_ids

on_reaction():
1. check msg_ids[channel_id].values()
2. wait for tasks[channel_id]
3. set tasks[channel_id] to task that calls on_update():
    for each substate:
        update discord state (bot, chan_id, msg_ids, prev_state, next_state) -> msg_ids
        update msg_ids[channel_id]
    return last substate

start_pug():
1. check msg_ids[channel_id].values()
2. wait for tasks[channel_id]
3. set tasks[channel_id] to task that sets next state to WaitingState
4. update discord state (msg_ids, prev_state, next_state) -> msg_ids
5. update msg_ids[channel_id]

react_add >> states >> discord -> msg_id_map
react_rem >>
set_state >>

react -> react_filter(channel) -> update_state -> discordify
      |                                               |
      +-----------------------------------------------+
"""

tasks = pipe() >> (
            sched_task,
            scan(update_state),
            with_prev(update_discord),
            lambda channel, msg_ids: g_msg_ids[channel] = msg_ids),
        )

curr_state = PugState()
msg_ids = frozenset()
while True:
    updates = list(update_queue)
    update_queue.clear()

    next_thing = await first(state_update_iter, incoming_message)
    if next_thing is state_update_iter:
        curr_state = next_thing.result()
    else:
        msg_id, reaction = next_thing.result()
        if 

