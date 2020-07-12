from asyncio import Future
import pytest
from unittest.mock import call

from discord import Embed

from rewrite import ChanCtx, React
from bot_stuff import update_discord
from utils import as_fut

@pytest.fixture
def chan_id():
    return 100

@pytest.mark.filterwarnings("ignore:coroutine")  # ignore un-awaited coroutine warnings
def test_bot_methods(bot, chan_id):
    msg_id = user_id = 1
    content = 'content'
    embed = Embed(title='embed')
    emoji = 'emoji'  # TODO: test with 'Emoji' instances as well

    # just check that all the bot functions can be called without raising errors
    bot.send_message(chan_id)
    bot.send_message(chan_id, content)
    bot.send_message(chan_id, embed=embed)

    bot.edit_message(chan_id, msg_id)
    bot.edit_message(chan_id, msg_id, content=content)
    bot.edit_message(chan_id, msg_id, embed=embed)

    bot.edit_message(chan_id, msg_id)

    bot.add_reaction(chan_id, msg_id, emoji)
    bot.remove_reaction(chan_id, msg_id, emoji, user_id)
    bot.remove_reaction(chan_id, msg_id, emoji, bot.user_id)

    bot.clear_reaction(chan_id, msg_id, emoji)

    bot.clear_reactions(chan_id, msg_id)

@pytest.mark.asyncio
async def test_update_msgs_noop(mock_bot, chan_id):
    prev_msgs  = { 'cat': 'cat_msg', 'dog': 'dog_msg' }
    next_msgs  = prev_msgs
    msg_id_map = { 'cat': 0, 'dog': 1 }
    exp_id_map   = msg_id_map

    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                              prev_msgs, next_msgs, set(), set())
    assert mock_bot.edit_message.call_count == 0
    assert mock_bot.send_message.call_count == 0
    assert mock_bot.delete_message.call_count == 0

@pytest.mark.asyncio
async def test_update_msgs_swap_key(mock_bot, chan_id):
    prev_msgs  = { 'cat': 'cat_msg', 'dog': 'dog_msg' }
    next_msgs  = { 'cat': 'dog_msg', 'dog': 'cat_msg' }
    msg_id_map = { 'cat': 0, 'dog': 1 }

    exp_id_map = { 'cat': 1, 'dog': 0 }
    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                              prev_msgs, next_msgs, set(), set())
    assert mock_bot.edit_message.call_count == 0
    assert mock_bot.send_message.call_count == 0
    assert mock_bot.delete_message.call_count == 0

@pytest.mark.asyncio
async def test_update_msgs_edit(mock_bot, chan_id):
    prev_msgs  = { 'cat': 'cat_msg', 'dog': 'dog_msg' }
    next_msgs  = { 'cat': 'cat_msg', 'dog': 'a_different_dog_msg' }
    msg_id_map = { 'cat': 0, 'dog': 1 }

    exp_id_map = msg_id_map
    exp_edits  = [call(chan_id, exp_id_map['dog'], content=next_msgs['dog'])]

    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                              prev_msgs, next_msgs, set(), set())
    assert mock_bot.edit_message.call_args_list == exp_edits
    assert mock_bot.send_message.call_count == 0
    assert mock_bot.delete_message.call_count == 0

@pytest.mark.asyncio
async def test_update_msgs_edit_duplicate(mock_bot, chan_id):
    prev_msgs  = { 'cat': 'cat_msg', 'dog_then_cat': 'dog_msg' }
    next_msgs  = { 'cat': 'cat_msg', 'dog_then_cat': 'cat_msg' }
    msg_id_map = { 'cat': 0, 'dog_then_cat': 1 }

    exp_id_map = msg_id_map
    exp_edits  = [call(chan_id, exp_id_map['dog_then_cat'], content=next_msgs['dog_then_cat'])]

    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                              prev_msgs, next_msgs, set(), set())
    assert mock_bot.edit_message.call_args_list == exp_edits
    assert mock_bot.send_message.call_count == 0
    assert mock_bot.delete_message.call_count == 0


@pytest.mark.asyncio
async def test_update_msgs_send(mock_bot, chan_id):
    mock_bot.send_message.side_effect = [as_fut('new_msg_id')]
    prev_msgs  = { 'cat': 'cat_msg' }
    next_msgs  = { 'cat': 'cat_msg', 'dog': 'cat_msg' }
    msg_id_map = { 'cat': 0 }

    exp_id_map = { 'cat': 0, 'dog': 'new_msg_id' }
    exp_sends  = [call(chan_id, content=next_msgs['dog'])]
    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                              prev_msgs, next_msgs, set(), set())
    assert mock_bot.edit_message.call_count == 0
    assert mock_bot.send_message.call_args_list == exp_sends
    assert mock_bot.delete_message.call_count == 0

@pytest.mark.asyncio
async def test_update_msgs_send_duplicate(mock_bot, chan_id):
    mock_bot.send_message.side_effect = [as_fut('new_msg_id')]
    prev_msgs  = { 'cat': 'cat_msg' }
    next_msgs  = { 'cat': 'cat_msg', 'another_cat': 'cat_msg' }
    msg_id_map = { 'cat': 0 }

    exp_id_map = { 'cat': 0, 'another_cat': 'new_msg_id' }
    exp_sends  = [call(chan_id, content=next_msgs['another_cat'])]
    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                              prev_msgs, next_msgs, set(), set())
    assert mock_bot.edit_message.call_count == 0
    assert mock_bot.send_message.call_args_list == exp_sends
    assert mock_bot.delete_message.call_count == 0

@pytest.mark.asyncio
async def test_update_msgs_delete(mock_bot, chan_id):
    prev_msgs  = { 'cat': 'cat_msg', 'dog': 'dog_msg' }
    next_msgs  = { 'cat': 'cat_msg' }
    msg_id_map = { 'cat': 0, 'dog': 1 }

    exp_id_map = { 'cat': 0 }
    exp_dels   = [call(chan_id, msg_id_map['dog'])]
    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                              prev_msgs, next_msgs, set(), set())
    assert mock_bot.edit_message.call_count == 0
    assert mock_bot.send_message.call_count == 0
    assert mock_bot.delete_message.call_args_list == exp_dels

@pytest.mark.asyncio
async def test_update_msgs_append_hist(mock_bot, chan_id):
    mock_bot.send_message.side_effect = [as_fut('new_msg_id')]
    prev_msgs  = { 'hist0': 'old_msg', 'newest': 'old_msg' }
    next_msgs  = { 'hist0': 'old_msg', 'hist1': 'old_msg', 'newest': 'new_msg' }
    msg_id_map = { 'hist0': 0, 'newest': 1 }

    exp_id_map = { 'hist0': 0, 'hist1': 1, 'newest': 'new_msg_id' }
    exp_sends  = [call(chan_id, content=next_msgs['newest'])]
    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                              prev_msgs, next_msgs, set(), set())
    assert mock_bot.edit_message.call_count == 0
    assert mock_bot.send_message.call_args_list == exp_sends
    assert mock_bot.delete_message.call_count == 0


@pytest.mark.asyncio
async def test_update_msgs_remap_optimal(mock_bot, chan_id):
    """
    The optimal mapping is:
        curr2 -> prev, curr -> curr, prev -> None
    but if the 'curr -> prev' mapping is chosen over 'curr2 -> prev' you get:
        curr -> prev, None -> curr, prev -> None, curr2 -> None
    """
    prev_msgs  = { 'prev': 'prev_msg', 'curr': 'curr_msg', 'curr2': 'curr_msg' }
    next_msgs  = { 'prev': 'curr_msg', 'curr': 'next_msg' }
    msg_id_map = { 'prev': 0, 'curr': 1, 'curr2': 2 }

    exp_id_map = { 'prev': 2, 'curr': 1 }
    exp_edits  = [call(chan_id, exp_id_map['curr'], content=next_msgs['curr'])]
    exp_dels   = [call(chan_id, msg_id_map['prev'])]

    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                              prev_msgs, next_msgs, set(), set())
    assert mock_bot.edit_message.call_args_list == exp_edits
    assert mock_bot.send_message.call_count == 0
    assert mock_bot.delete_message.call_args_list == exp_dels


@pytest.mark.asyncio
async def test_update_msgs_remap_optimal(mock_bot, chan_id):
    """
    The optimal mapping is:
        curr2 -> prev, curr -> curr, prev -> None
    but if the 'curr -> prev' mapping is chosen over 'curr2 -> prev' you get:
        curr -> prev, None -> curr, prev -> None, curr2 -> None
    """
    prev_msgs  = { 'prev': 'prev_msg', 'curr': 'curr_msg', 'curr2': 'curr_msg' }
    next_msgs  = { 'prev': 'curr_msg', 'curr': 'next_msg' }
    msg_id_map = { 'prev': 0, 'curr': 1, 'curr2': 2 }

    exp_id_map = { 'prev': 2, 'curr': 1 }
    exp_edits  = [call(chan_id, exp_id_map['curr'], content=next_msgs['curr'])]
    exp_dels   = [call(chan_id, msg_id_map['prev'])]

    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                              prev_msgs, next_msgs, set(), set())
    assert mock_bot.edit_message.call_args_list == exp_edits
    assert mock_bot.send_message.call_count == 0
    assert mock_bot.delete_message.call_args_list == exp_dels


@pytest.mark.asyncio
async def test_update_reacts_noop(mock_bot, chan_id):
    prev_msgs = next_msgs = { 'key': 'msg' }
    msg_id_map = { k: k for k in prev_msgs }

    prev_reacts = { React('bob', 'XD') }
    next_reacts = prev_reacts

    await update_discord(mock_bot, chan_id, msg_id_map, prev_msgs, next_msgs, prev_reacts, next_reacts)
    assert mock_bot.add_reaction.call_count == 0
    assert mock_bot.remove_reaction.call_count == 0
    assert mock_bot.clear_reaction.call_count == 0
    assert mock_bot.clear_reactions.call_count == 0

@pytest.mark.asyncio
async def test_update_reacts_add_rem_clr(mock_bot, chan_id):
    bot_id = mock_bot.user_id

    prev_msgs = next_msgs = { 'key': 'msg' }
    msg_id_map = { 'key': 'msg_id' }

    prev_reacts = {
        React('bob', 'XD'), React('alice', 'XD'),
        React('tom', 'uwu'), React('joe', 'uwu'),
        React('bob', 'cap'), React('joe', 'cap'), React('tom', 'cap')
    }
    next_reacts = { React('bob', 'XD'), React(bot_id, 'XD'), React('bob', 'cap') }

    exp_adds = [call(chan_id, 'msg_id', 'XD')]
    exp_rems = [call(chan_id, 'msg_id', 'XD', 'alice'), call(chan_id, 'msg_id', 'cap', 'joe'), call(chan_id, 'msg_id', 'cap', 'tom')]
    exp_clrs = [call(chan_id, 'msg_id', 'uwu')]

    await update_discord(mock_bot, chan_id, msg_id_map, prev_msgs, next_msgs, prev_reacts, next_reacts)
    assert mock_bot.add_reaction.call_args_list == exp_adds
    assert sorted(mock_bot.remove_reaction.call_args_list) == sorted(exp_rems)
    assert mock_bot.clear_reaction.call_args_list == exp_clrs
    assert mock_bot.clear_reactions.call_count == 0

@pytest.mark.asyncio
async def test_update_reacts_nuke(mock_bot, chan_id):
    bot_id = mock_bot.user_id

    prev_msgs = next_msgs = { 'key': 'msg' }
    msg_id_map = { 'key': 'msg_id' }

    prev_reacts = { React('bob', 'XD'), React('alice', ':)') }
    next_reacts = set()

    exp_nuke = [call(chan_id, 'msg_id')]

    await update_discord(mock_bot, chan_id, msg_id_map, prev_msgs, next_msgs, prev_reacts, next_reacts)
    assert mock_bot.add_reaction.call_count == 0
    assert mock_bot.remove_reaction.call_count == 0
    assert mock_bot.clear_reaction.call_count == 0
    assert mock_bot.clear_reactions.call_args_list == exp_nuke

@pytest.mark.asyncio
async def test_update_reacts_dont_nuke(mock_bot, chan_id):
    bot_id = mock_bot.user_id

    prev_msgs = next_msgs = { 'key': 'msg' }
    msg_id_map = { 'key': 'msg_id' }
    next_reacts = set()

    # remove_reaction() should be used instead of clear_reactions()
    prev_reacts = { React('bob', 'XD') }
    exp_nuke = [call(chan_id, 'msg_id')]
    await update_discord(mock_bot, chan_id, msg_id_map, prev_msgs, next_msgs, prev_reacts, next_reacts)
    assert mock_bot.add_reaction.call_count == 0
    assert mock_bot.remove_reaction.call_count == 1
    assert mock_bot.clear_reaction.call_count == 0
    assert mock_bot.clear_reactions.call_count == 0

    # clear_reaction() should be used instead of clear_reactions()
    prev_reacts = { React('bob', 'XD'), React('alice', 'XD') }
    await update_discord(mock_bot, chan_id, msg_id_map, prev_msgs, next_msgs, prev_reacts, next_reacts)
    assert mock_bot.add_reaction.call_count == 0
    assert mock_bot.remove_reaction.call_count == 1
    assert mock_bot.clear_reaction.call_count == 1
    assert mock_bot.clear_reactions.call_count == 0

# TODO: tests for when main message changes
