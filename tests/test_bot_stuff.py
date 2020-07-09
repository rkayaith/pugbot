import pytest

from discord import Embed, Emoji, Object
from bot_stuff import Bot, ChanCtx, update_discord
from collections import namedtuple

@pytest.mark.filterwarnings("ignore:coroutine")  # ignore un-awaited coroutine warnings
def test_bot(bot, chan_id):
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

from unittest.mock import call, create_autospec, MagicMock
from asyncio import Future

def as_fut(thing):
    fut = Future()
    fut.set_result(thing)
    return fut

@pytest.fixture
def chan_id():
    return 100

@pytest.fixture
def bot():
    return Bot(command_prefix='dont care')

@pytest.fixture
def mock_bot(bot):
    mock_bot = create_autospec(bot)
    # create_autospec() doesn't know that some functions return awaitables,
    # so we have to manually fix those
    mock_bot.send_message.return_value = as_fut(MagicMock())
    mock_bot.edit_message.return_value = as_fut(None)
    mock_bot.delete_message.return_value = as_fut(None)

    return mock_bot

@pytest.mark.asyncio
async def test_update_noop(mock_bot, chan_id):
    prev_msgs  = { 'cat': 'cat_msg', 'dog': 'dog_msg' }
    next_msgs  = prev_msgs
    msg_id_map = { 'cat': 0, 'dog': 1 }
    exp_id_map   = msg_id_map

    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                            prev_msgs, next_msgs)
    assert mock_bot.edit_message.call_count == 0
    assert mock_bot.send_message.call_count == 0
    assert mock_bot.delete_message.call_count == 0

@pytest.mark.asyncio
async def test_update_swap_key(mock_bot, chan_id):
    prev_msgs  = { 'cat': 'cat_msg', 'dog': 'dog_msg' }
    next_msgs  = { 'cat': 'dog_msg', 'dog': 'cat_msg' }
    msg_id_map = { 'cat': 0, 'dog': 1 }

    exp_id_map = { 'cat': 1, 'dog': 0 }
    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                            prev_msgs, next_msgs)
    assert mock_bot.edit_message.call_count == 0
    assert mock_bot.send_message.call_count == 0
    assert mock_bot.delete_message.call_count == 0

@pytest.mark.asyncio
async def test_update_edit(mock_bot, chan_id):
    prev_msgs  = { 'cat': 'cat_msg', 'dog': 'dog_msg' }
    next_msgs  = { 'cat': 'cat_msg', 'dog': 'a_different_dog_msg' }
    msg_id_map = { 'cat': 0, 'dog': 1 }

    exp_id_map = msg_id_map
    exp_edits  = [call(chan_id, exp_id_map['dog'], content=next_msgs['dog'])]

    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                            prev_msgs, next_msgs)
    assert mock_bot.edit_message.call_args_list == exp_edits
    assert mock_bot.send_message.call_count == 0
    assert mock_bot.delete_message.call_count == 0

@pytest.mark.asyncio
async def test_update_edit_duplicate(mock_bot, chan_id):
    prev_msgs  = { 'cat': 'cat_msg', 'dog_then_cat': 'dog_msg' }
    next_msgs  = { 'cat': 'cat_msg', 'dog_then_cat': 'cat_msg' }
    msg_id_map = { 'cat': 0, 'dog_then_cat': 1 }

    exp_id_map = msg_id_map
    exp_edits  = [call(chan_id, exp_id_map['dog_then_cat'], content=next_msgs['dog_then_cat'])]

    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                            prev_msgs, next_msgs)
    assert mock_bot.edit_message.call_args_list == exp_edits
    assert mock_bot.send_message.call_count == 0
    assert mock_bot.delete_message.call_count == 0


@pytest.mark.asyncio
async def test_update_send(mock_bot, chan_id):
    mock_bot.send_message.side_effect = [as_fut('new_msg_id')]
    prev_msgs  = { 'cat': 'cat_msg' }
    next_msgs  = { 'cat': 'cat_msg', 'dog': 'cat_msg' }
    msg_id_map = { 'cat': 0 }

    exp_id_map = { 'cat': 0, 'dog': 'new_msg_id' }
    exp_sends  = [call(chan_id, content=next_msgs['dog'])]
    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                              prev_msgs, next_msgs)
    assert mock_bot.edit_message.call_count == 0
    assert mock_bot.send_message.call_args_list == exp_sends
    assert mock_bot.delete_message.call_count == 0

@pytest.mark.asyncio
async def test_update_send_duplicate(mock_bot, chan_id):
    mock_bot.send_message.side_effect = [as_fut('new_msg_id')]
    prev_msgs  = { 'cat': 'cat_msg' }
    next_msgs  = { 'cat': 'cat_msg', 'another_cat': 'cat_msg' }
    msg_id_map = { 'cat': 0 }

    exp_id_map = { 'cat': 0, 'another_cat': 'new_msg_id' }
    exp_sends  = [call(chan_id, content=next_msgs['another_cat'])]
    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                              prev_msgs, next_msgs)
    assert mock_bot.edit_message.call_count == 0
    assert mock_bot.send_message.call_args_list == exp_sends
    assert mock_bot.delete_message.call_count == 0

@pytest.mark.asyncio
async def test_update_delete(mock_bot, chan_id):
    prev_msgs  = { 'cat': 'cat_msg', 'dog': 'dog_msg' }
    next_msgs  = { 'cat': 'cat_msg' }
    msg_id_map = { 'cat': 0, 'dog': 1 }

    exp_id_map = { 'cat': 0 }
    exp_dels   = [call(chan_id, msg_id_map['dog'])]
    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                              prev_msgs, next_msgs)
    assert mock_bot.edit_message.call_count == 0
    assert mock_bot.send_message.call_count == 0
    assert mock_bot.delete_message.call_args_list == exp_dels

@pytest.mark.asyncio
async def test_update_append_hist(mock_bot, chan_id):
    mock_bot.send_message.side_effect = [as_fut('new_msg_id')]
    prev_msgs  = { 'hist0': 'old_msg', 'newest': 'old_msg' }
    next_msgs  = { 'hist0': 'old_msg', 'hist1': 'old_msg', 'newest': 'new_msg' }
    msg_id_map = { 'hist0': 0, 'newest': 1 }

    exp_id_map = { 'hist0': 0, 'hist1': 1, 'newest': 'new_msg_id' }
    exp_sends  = [call(chan_id, content=next_msgs['newest'])]
    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                              prev_msgs, next_msgs)
    assert mock_bot.edit_message.call_count == 0
    assert mock_bot.send_message.call_args_list == exp_sends
    assert mock_bot.delete_message.call_count == 0


@pytest.mark.asyncio
@pytest.mark.skip("Current algo sometimes chooses suboptimal mapping")
async def test_update_test(mock_bot, chan_id):
    """
    The optimal mapping is:
        curr_dup -> prev, curr -> curr, prev -> None
    but currently the algo might randomly choose:
        curr -> prev, None -> curr, prev -> None, curr_dup -> None
    (the 'curr -> prev' mapping is randomly chosen over 'curr_dup -> prev')
    """
    prev_msgs  = { 'prev': 'prev_msg', 'curr': 'curr_msg', 'curr_dup': 'curr_msg' }
    next_msgs  = { 'prev': 'curr_msg', 'curr': 'next_msg' }
    msg_id_map = { 'prev': 0, 'curr': 1, 'curr_dup': 2 }

    exp_id_map = { 'prev': 2, 'curr': 1 }
    exp_edits  = [call(chan_id, exp_id_map['curr'], content=next_msgs['curr'])]
    exp_dels   = [call(chan_id, msg_id_map['prev'])]

    assert exp_id_map == await update_discord(mock_bot, chan_id, msg_id_map,
                                              prev_msgs, next_msgs)
    assert mock_bot.edit_message.call_args_list == exp_edits
    assert mock_bot.send_message.call_count == 0
    assert mock_bot.delete_message.call_args_list == exp_dels
