import asyncio
import pytest

from rewrite import schedule_update, State, React

pytestmark = pytest.mark.asyncio

async def test_idk():
    channel_id = 0
    states = { channel_id: State(frozenset()) }
    tasks = {}

    new_react = React(123, 'emoji')

    await schedule_update(states, tasks, channel_id, add_reacts={ new_react })
    assert len(states) == 1
    assert len(tasks) == 0
    assert states[channel_id].reacts == { new_react }
