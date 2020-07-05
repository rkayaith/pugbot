import asyncio
from dataclasses import replace
import pytest
from unittest.mock import create_autospec
from discord.ext import commands

from rewrite import BotStatus, State, React, schedule_state_update, run_state_update, on_state_change

# TODO: move to utils
def fset(*args):
    return frozenset(args)

pytestmark = pytest.mark.asyncio

DELTA = 1E-20

"""
def mock_bot():
    class MockBot:
        class MockChannel:
            async def
        def get_channel(id):
            return MockChannel()

async def test_on_state_change():
    prev_state = State(fset())
    next_state = State(fset(React(1, '1')))
    bot = create_autospec(commands.Bot(command_prefix=None))
    breakpoint()
    await on_state_change(bot, prev_state, next_state)
"""

async def test_schedule_state_update_inter():
    sleep_time = 2 * DELTA
    test_states = [State(fset()), State(fset()), State(fset())]

    # yield a state then wait 'sleep_time' seconds
    async def mock_run_update(bot, prev_state, next_state):
        for state in test_states:
            yield state
            await asyncio.sleep(sleep_time)

    status = BotStatus(bot=None)
    status.set_state((channel_id := 0), State(fset()))
    # schedule the state update
    t = asyncio.create_task(
        schedule_state_update(status, channel_id, lambda _: [],  mock_run_update)
    )
    await asyncio.sleep(DELTA)
    # check that 'states' has been updated and wait 'sleep_time' seconds
    for state in test_states:
        assert len(status.states) == 1 and len(status.tasks) == 1
        assert status.states[channel_id] is state
        await asyncio.sleep(sleep_time)

    await t
    assert len(status.states) == 1 and len(status.tasks) == 0
    assert status.states[channel_id] is test_states[-1]


async def test_schedule_state_update_raise():
    class MockException(Exception):
        pass
    async def run_update_raise(prev_state, next_state):
        raise MockException()

    bot = None
    channel_id = 0
    states, tasks = { channel_id: State(fset()) }, {}

    # 'tasks' should be cleaned up even though the update had raised an error
    with pytest.raises(MockException):
        await schedule_state_update(bot, states, tasks, channel_id, lambda _: [],  run_update_raise)
    assert len(tasks) == 0


async def test_schedule_state_update_raise():
    class MockException(Exception):
        pass

    async def run_update(bot, prev_state, next_state):
        return
        yield

    async def run_update_raise(bot, prev_state, next_state):
        try:
            await asyncio.sleep(1000)
        finally:
            raise MockException()
        yield

    bot = None
    channel_id = 0
    states, tasks = { channel_id: State(fset()) }, {}

    # start first update
    should_raise = asyncio.create_task(schedule_state_update(bot, states, tasks, channel_id, lambda _: [],  run_update_raise))
    await asyncio.sleep(DELTA)
    # next update should run even though the previous one raised an error
    await schedule_state_update(bot, states, tasks, channel_id, lambda _: [],  run_update)

    # awaiting the first update should raise the error
    with pytest.raises(MockException):
        await should_raise
    assert len(tasks) == 0
