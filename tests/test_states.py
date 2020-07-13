import asyncio
from dataclasses import replace
from itertools import chain
import random
import pytest

from states import IdleState, VoteState, React, HOST_EMOJI, CAPT_EMOJI, SKIP_EMOJI, WAIT_EMOJI, MIN_HOSTS, MIN_CAPTS, MIN_PLAYERS
from utils import alist, fset

def test_idle_props(mock_bot):
    admin_ids = set(range(0, 2))
    host_ids  = set(range(2, 5))
    capt_ids  = set(range(5, 7))
    other_ids = set(range(7, 17))
    add_reacts = lambda state, reacts: replace(state, reacts=state.reacts | reacts)

    state = IdleState(mock_bot, admin_ids, fset(), ('historic message',))
    assert 0 == len(state.host_ids) == len(state.capt_ids) == len(state.player_ids)

    # bot reacts don't count towards anything
    state = add_reacts(state, { React(mock_bot.user_id, e) for e in (HOST_EMOJI, CAPT_EMOJI, SKIP_EMOJI, WAIT_EMOJI) })
    assert 0 == len(state.host_ids) == len(state.capt_ids) == len(state.player_ids)

    state = add_reacts(state, { React(u, SKIP_EMOJI) for u in admin_ids })
    assert len(admin_ids) == len(state.admin_skip)
    assert 0 == len(state.admin_wait)
    state = add_reacts(state, { React(u, WAIT_EMOJI) for u in admin_ids })
    assert len(admin_ids) == len(state.admin_skip) == len(state.admin_wait)
    # admin reacts don't count towards players
    assert 0 == len(state.host_ids) == len(state.capt_ids) == len(state.player_ids)

    # hosts dont count as players
    state = add_reacts(state, { React(u, HOST_EMOJI) for u in host_ids })
    assert len(host_ids) == len(state.host_ids)
    assert 0 == len(state.capt_ids) == len(state.player_ids)

    # captains count as players
    state = add_reacts(state, { React(u, CAPT_EMOJI) for u in capt_ids })
    assert len(host_ids) == len(state.host_ids)
    assert len(capt_ids) == len(state.capt_ids) == len(state.player_ids)

    state = add_reacts(state, { React(u, random.choice(range(4))) for u in other_ids })
    assert len(host_ids) == len(state.host_ids)
    assert len(capt_ids) == len(state.capt_ids)
    assert len(capt_ids) + len(other_ids) == len(state.player_ids)

    # we don't double-count players who react multiple times
    state = add_reacts(state, { React(u, random.choice(range(4))) for u in other_ids })
    assert len(capt_ids) + len(other_ids) == len(state.player_ids)

    # accessing messages doesn't cause an exception
    state.messages

@pytest.mark.asyncio
async def test_idle_transition(mock_bot):
    admin_id = 0
    admin_wait = { React(admin_id, WAIT_EMOJI) }
    admin_skip = { React(admin_id, SKIP_EMOJI) }
    pugger_reacts = fset(chain(
        (React(u, HOST_EMOJI) for u in range(MIN_HOSTS)),
        (React(u, CAPT_EMOJI) for u in range(MIN_CAPTS)),
        (React(u, random.choice(range(4))) for u in range(MIN_PLAYERS))
    ))
    initial_state = IdleState(mock_bot, { admin_id }, fset(), tuple())

    # we don't go anywhere when noone's reacted yet
    next_states = await alist(initial_state.on_update(fset()))
    assert len(next_states) == 1 and isinstance(next_states[-1], IdleState)
    next_states[0].messages

    # we go to the voting state when everyone's reacted
    next_states = await alist(initial_state.on_update(pugger_reacts))
    assert len(next_states) == 2 and isinstance(next_states[-1], VoteState)
    next_states[0].messages

    # ...unless an admin says to wait
    next_states = await alist(initial_state.on_update(pugger_reacts | admin_wait))
    assert len(next_states) == 1 and isinstance(next_states[-1], IdleState)
    next_states[0].messages

    # ...UNLESS an admin says to start
    next_states = await alist(initial_state.on_update(pugger_reacts | admin_wait | admin_skip))
    assert len(next_states) == 2 and isinstance(next_states[-1], VoteState)
    next_states[0].messages
