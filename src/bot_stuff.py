import asyncio
from collections import defaultdict
from itertools import chain, starmap
from operator import attrgetter as get

from discord import Embed, Message
from discord.ext import commands

from .utils import as_fut, create_index, first, invert_dict, retval_as_fut

# TODO: rename file to discord_stuff?


class Bot(commands.Bot):
    @property
    def user_id(self):
        return self._connection.self_id

    def send_message(self, chan_id, content_or_embed=None, /, *, content=None, embed=None):
        if content_or_embed:
            assert content is embed is None
            (embed := content_or_embed) if isinstance(content_or_embed, Embed) else (content := content_or_embed)

        # see: https://github.com/Rapptz/discord.py/blob/master/discord/abc.py#L781
        content = str(content) if content is not None else None
        embed   = embed.to_dict() if embed is not None else None

        assert content or embed
        result  = self._connection.http.send_message(chan_id, content, embed=embed)
        async def msg_id():
            return int((await result)['id'])
        return msg_id()

    def edit_message(self, chan_id, msg_id, content_or_embed=None, /, *, content=None, embed=None):
        if content_or_embed:
            assert content is embed is None
            (embed := content_or_embed) if isinstance(content_or_embed, Embed) else (content := content_or_embed)

        # see: https://github.com/Rapptz/discord.py/blob/master/discord/message.py#L754
        content = str(content) if content is not None else None
        embed   = embed.to_dict() if embed is not None else None

        assert content or embed
        return self._connection.http.edit_message(chan_id, msg_id, content=content, embed=embed)

    def delete_message(self, chan_id, msg_id):
        return self._connection.http.delete_message(chan_id, msg_id)

    def add_reaction(self, chan_id, msg_id, emoji):
        return self._connection.http.add_reaction(chan_id, msg_id, Message._emoji_reaction(emoji))

    def remove_reaction(self, chan_id, msg_id, emoji, user_id):
        emoji = Message._emoji_reaction(emoji)
        if user_id == self.user_id:
            return self._connection.http.remove_own_reaction(chan_id, msg_id, emoji)
        else:
            return self._connection.http.remove_reaction(chan_id, msg_id, emoji, user_id)

    def clear_reaction(self, chan_id, msg_id, emoji):
        return self._connection.http.clear_single_reaction(chan_id, msg_id, Message._emoji_reaction(emoji))

    def clear_reactions(self, chan_id, msg_id):
        return self._connection.http.clear_reactions(chan_id, msg_id)


async def update_discord(bot, chan_id, msg_ids, key_to_msg, key_to_new_msg, old_reacts, new_reacts):
    assert msg_ids.keys() == key_to_msg.keys()

    # create a mapping from message content -> keys of messages with that content
    msg_to_keys = defaultdict(set, invert_dict(key_to_msg))

    # awaitables to run. we'll only run these at the very end, so that if an
    # error happens halfway through this function we won't leave discord in a
    # half-updated state.
    aws = []

    """
    Each of these functions takes the key and content of a message that will be
    sent, and tries to find the key of an existing message for it to use.
    """
    # key, msg -> key, msg
    def no_change(key, msg, free_keys):
        if key in free_keys and msg == key_to_msg[key]:
            print(f"{key} -> {key} (no_change)")
            return key

    # different_key, msg -> key, msg
    def change_key(key, msg, free_keys):
        if (cand_keys := msg_to_keys[msg] & free_keys):
            # prioritize keys that can't be used by change_msg(). there
            # might still be broken edge cases here, not sure...
            key_to_use = next(chain(cand_keys - key_to_new_msg.keys(), cand_keys))
            print(f"{key_to_use} -> {key} (change_key)")
            return key_to_use

    # key, different_msg -> key, msg
    def change_msg(key, msg, free_keys):
        if key in free_keys:
            assert msg != key_to_msg[key]
            aws.append(bot.edit_message(chan_id, msg_ids[key], msg))
            print(f"{key} -> {key} (change_msg)")
            return key


    def try_map(map_func, unmapped, free_keys, msg_id_futs):
        """
        Take a mapping function and try and apply it to a set of unmapped messages.
        Returns the keys of messages it wasn't able to map.
        """
        # copy inputs so we can modify them
        free_keys, msg_id_futs = set(free_keys), dict(msg_id_futs)

        def attempt_map(key):
            if (key_to_use := map_func(key, key_to_new_msg[key], free_keys)) is None:
                return True
            free_keys.remove(key_to_use)
            msg_id_futs[key] = as_fut(msg_ids[key_to_use])
            return False

        return list(filter(attempt_map, unmapped)), free_keys, msg_id_futs

    unmapped     = key_to_new_msg.keys()  # keys of new messages needing to be mapped
    free_keys    = key_to_msg.keys()      # keys of existing messages we can reuse
    msg_id_futs  = {}                     # mapping from new message key -> id future

    """
    Apply the mapping strategies. We want to try a single strategy on all
    messages before moving on to the next strategy, so that the 'best' one is
    applied as often as possible.
    """
    unmapped, free_keys, msg_id_futs = try_map(no_change,  unmapped, free_keys, msg_id_futs)
    unmapped, free_keys, msg_id_futs = try_map(change_key, unmapped, free_keys, msg_id_futs)
    unmapped, free_keys, msg_id_futs = try_map(change_msg, unmapped, free_keys, msg_id_futs)

    # create new messages for anything that wasn't mapped to an existing message
    for key in unmapped:
        print(f"None -> {key} (send_msg)")
        msg_id_futs[key], coro = retval_as_fut(bot.send_message(chan_id, key_to_new_msg[key]))
        aws.append(coro)

    # delete unused messages
    for key in free_keys:
        print(f"{key} -> {None} (del_msg)")
        aws.append(bot.delete_message(chan_id, msg_ids[key]))


    # we only track reacts for the "main" message
    main_key     = first(key_to_msg)
    new_main_key = first(key_to_new_msg)
    main_id      = msg_ids.get(main_key)
    main_id_fut  = msg_id_futs.get(new_main_key, as_fut(None))

    # if we're tracking a different message now, we assume it has no reacts
    # TODO: should we remove all the reacts from the old message?
    if not main_id_fut.done() or main_id_fut.result() != main_id:
        old_reacts = set()

    async def add_react(msg_id_fut, emoji):
        assert (msg_id := await msg_id_fut) is not None
        await bot.add_reaction(chan_id, msg_id, emoji)
    # add reactions to the new main message
    # sort them so they get added in a consistent order
    for user_id, emoji in sorted(new_reacts - old_reacts):
        try:
            assert user_id == bot.user_id  # we can only add reactions from the bot
        except:
            breakpoint()
        aws.append(add_react(main_id_fut, emoji))

    # remove reactions from old main message
    def remove_reacts(reacts):
        reacts_by_emoji = create_index(reacts, get('emoji'))
        # use clear_reactions() if we're deleting all reactions. calling it is a
        # bit risky since we might accidentally remove a new reaction as it
        # comes in, so we only use if we're removing more than 1 set of reacts.
        if len(new_reacts) == 0 and len(reacts_by_emoji) > 1:
            return [bot.clear_reactions(chan_id, main_id)]
        return chain(*starmap(remove_reacts_by_emoji, reacts_by_emoji.items()))

    new_emojis = { r.emoji for r in new_reacts }
    def remove_reacts_by_emoji(emoji, reacts):
        # use_clear reactions() if we're deleting all reacts with a certain emoji
        # and deleting more than one react.
        if emoji not in new_emojis and len(reacts) > 1:
            return [bot.clear_reaction(chan_id, main_id, emoji)]
        return starmap(remove_react_by_user, reacts)

    def remove_react_by_user(user_id, emoji):
        return bot.remove_reaction(chan_id, main_id, emoji, user_id)

    aws.extend(remove_reacts(old_reacts - new_reacts))

    # run all the tasks now
    await asyncio.gather(*aws)

    # all the message id futures should be finished now.
    # we make sure the keys here have the same order as 'key_to_new_msg', so
    # that the main message is first.
    return { key: msg_id_futs[key].result() for key in key_to_new_msg }


def mention(user_id):
    return f'<@{user_id}>'
