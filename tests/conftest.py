import pytest
from unittest.mock import MagicMock, call, create_autospec

from bot_stuff import Bot
from utils import as_fut


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

    mock_bot.add_reaction.return_value = as_fut(None)
    mock_bot.remove_reaction.return_value = as_fut(None)
    mock_bot.clear_reaction.return_value = as_fut(None)
    mock_bot.clear_reactions.return_value = as_fut(None)

    return mock_bot


