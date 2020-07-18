import asyncio
from dataclasses import replace
from itertools import chain
import random
import pytest

from src.states import State, IdleState, VoteState, PickState, RunningState, StoppedState
from src.states import MIN_HOSTS, MIN_CAPTS, MIN_PLAYERS, MIN_VOTES
from src.states import React, HOST_EMOJI, CAPT_EMOJI, SKIP_EMOJI, WAIT_EMOJI, OPTION_EMOJIS, DONE_EMOJI
from src.utils import alist, fset

TEST_ADMIN_ID = 1234

@pytest.fixture
def base_state(mock_bot):
    return State(mock_bot, { TEST_ADMIN_ID }, fset(), tuple())


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


admin_wait = { React(TEST_ADMIN_ID, WAIT_EMOJI) }
admin_skip = { React(TEST_ADMIN_ID, SKIP_EMOJI) }
min_puggers = ({ React(u, HOST_EMOJI) for u in range(MIN_HOSTS) } |
               { React(u, CAPT_EMOJI) for u in range(MIN_CAPTS) } |
               { React(u, random.choice(range(4))) for u in range(MIN_PLAYERS) })
@pytest.mark.parametrize("expected_state, reacts", [
    # don't go anywhere when noone's reacted
    (IdleState, fset()),
    # go to the picking state when everyone's reacted
    (PickState, min_puggers),
    # ...unless an admin says to wait
    (IdleState, min_puggers | admin_wait),
    # ...UNLESS an admin says to start
    (PickState, min_puggers | admin_wait | admin_skip),
    # go to the voting state if there's extra hosts or captains
    (VoteState, min_puggers | { React(10, HOST_EMOJI) }),
    (VoteState, min_puggers | { React(10, CAPT_EMOJI) }),
])
@pytest.mark.asyncio
async def test_idle_update(base_state, expected_state, reacts):
    next_states = await alist(IdleState.make(base_state, reacts=reacts).on_update())
    assert isinstance(next_states[-1], expected_state)
    assert [s.messages for s in next_states]


@pytest.mark.parametrize("expected_state, n_hosts, n_capts, admin_skip, n_host_votes, n_capt_votes", [
    # voting waits if we don't have enough votes
    (VoteState, 2, 3, False, 0, 0),
    (VoteState, 2, 3, False, MIN_VOTES, MIN_VOTES - 1),
    (VoteState, 2, 3, False, MIN_VOTES - 1, MIN_VOTES),
    # voting ends if we have enough votes
    (PickState, 2, 3, False, MIN_VOTES, MIN_VOTES),
    (PickState, 1, 3, False, 0, MIN_VOTES),
    (PickState, 2, 2, False, MIN_VOTES, 0),
    # voting ends if an admin says so, even if we don't have enough votes
    (PickState, 2, 3,  True, 1, 1),
])
@pytest.mark.asyncio
async def test_vote_update(base_state, expected_state, n_hosts, n_capts, admin_skip, n_host_votes, n_capt_votes):
    init_state = VoteState.make(base_state,
                                host_ids=fset(range(n_hosts)),
                                capt_ids=fset(range(n_capts)),
                                player_ids=fset(range(MIN_PLAYERS)))

    reacts = set()
    if admin_skip:
        reacts |= { React(TEST_ADMIN_ID, SKIP_EMOJI) }
    best_host = 0
    best_capt = 1
    reacts |= { React(u, init_state.host_emojis[best_host]) for u in range(n_host_votes) }
    reacts |= { React(u, init_state.capt_emojis[best_capt]) for u in range(n_capt_votes) }
    reacts |= { React(u, 'other') for u in range(20) }

    next_states = await alist(replace(init_state, reacts=reacts).on_update())
    assert isinstance(next_states[-1], expected_state)
    assert [s.messages for s in next_states]

    if expected_state is PickState:
        # make sure PickState only has the "best people"
        if n_host_votes > 0:
            assert next_states[-1].host_id == best_host
        if n_capt_votes > 0:
            assert next_states[-1].capt_ids[1] == best_capt
    else:
        # make sure bot is adding the correct reacts
        expected_bot_reacts = set()
        if n_hosts > 1:
            expected_bot_reacts |= { (init_state.bot.user_id, e) for e in init_state.host_emojis }
        if n_capts > 2:
            expected_bot_reacts |= { (init_state.bot.user_id, e) for e in init_state.capt_emojis }
        assert next_states[-1].reacts >= expected_bot_reacts


@pytest.mark.asyncio
async def test_pick_update(base_state):
    host_id = 10
    capt_ids = (3, 9)
    player_ids = tuple(range(1000, 1007))
    init_state = PickState.make(base_state, host_id, capt_ids, player_ids)

    async def pick(state, capt, pick_idx):
        return (await alist(replace(state, reacts=state.reacts | { React(capt, OPTION_EMOJIS[pick_idx]) }).on_update()))[-1]

    state = init_state
    for capt_idx, pick_idx in [(0, 0), (1, 3), (1, 4), (0, 1), (0, 2), (1, 5)]:
        state = await pick(state, capt_ids[capt_idx], pick_idx)
        assert state.team_ids[capt_idx][-1] == player_ids[pick_idx]
        state.messages

    state = (await alist(state.on_update()))[-1]
    assert isinstance(state, RunningState)
    assert state.red_ids == (capt_ids[0], player_ids[0], player_ids[1], player_ids[2])
    assert state.blu_ids == (capt_ids[1], player_ids[3], player_ids[4], player_ids[5])


@pytest.mark.parametrize('expected_state, reacts', [
    (RunningState, { React(1000, DONE_EMOJI) }),
    (IdleState, { React(1000, DONE_EMOJI), React(1001, DONE_EMOJI) }),
    (IdleState, { React(TEST_ADMIN_ID, DONE_EMOJI) }),
])
@pytest.mark.asyncio
async def test_running_update(base_state, expected_state, reacts):
    host_id = 10
    red_ids = tuple(range(1000, 1000+6))
    blu_ids = tuple(range(2000, 2000+6))
    init_state = RunningState.make(base_state, host_id, red_ids, blu_ids)

    next_states = await alist(replace(init_state, reacts=reacts).on_update())
    assert isinstance(next_states[-1], expected_state)
    [state.messages for state in next_states]
