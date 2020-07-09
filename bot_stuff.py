from discord import Embed, Message
from discord.ext import commands

# TODO: rename file to discord_stuff?

class Bot(commands.Bot):
    @property
    def user_id(self):
        return self._connection.self_id

    def send_message(self, chan_id, content=None, *, embed=None):
        # see: https://github.com/Rapptz/discord.py/blob/master/discord/abc.py#L781
        content = str(content) if content is not None else None
        embed   = embed.to_dict() if embed is not None else None
        result  = self._connection.http.send_message(chan_id, content, embed=embed)
        async def msg_id():
            return (await result)['id']
        return msg_id()

    def edit_message(self, chan_id, msg_id, *, content=None, embed=None):
        # see: https://github.com/Rapptz/discord.py/blob/master/discord/message.py#L754
        content = str(content) if content is not None else None
        embed   = embed.to_dict() if embed is not None else None

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

import asyncio
from dataclasses import dataclass
from collections import defaultdict
from itertools import chain

@dataclass
class ChanCtx:
    lock: asyncio.Lock
    msg_id_map: int
    reactions: frozenset

def invert_dict(d):
    """
    Return the dictionary 'inv', where
        inv[v] = { the set of keys in 'd' that map to 'v' }
    """
    inv = {}
    for key, val in d.items():
        inv.setdefault(val, set()).add(key)
    return inv

def as_fut(obj):
    fut = asyncio.Future()
    fut.set_result(obj)
    return fut

async def update_discord(bot, chan_id, msg_ids, key_to_msg, key_to_next_msg):
    assert msg_ids.keys() == key_to_msg.keys()
    msg_to_keys = defaultdict(set, invert_dict(key_to_msg))

    def try_map(map_func, unmapped, free_keys, next_msg_ids):
        # copy inputs so we can modify them
        free_keys, next_msg_ids = set(free_keys), dict(next_msg_ids)

        def attempt_map(key):
            if (key_to_use := map_func(key, key_to_next_msg[key], free_keys)) is None:
                return True
            free_keys.remove(key_to_use)
            next_msg_ids[key] = msg_ids[key_to_use]
            return False

        return list(filter(attempt_map, unmapped)), free_keys, next_msg_ids

    def no_change(key, msg, free_keys):
        # key, msg -> key, msg
        if key in free_keys and msg == key_to_msg[key]:
            print(f"{key} -> {key} (no_change)")
            return key

    def change_key(key, msg, free_keys):
        # different_key, msg -> key, msg
        if (cand_keys := msg_to_keys[msg] & free_keys):
            # prioritize keys that can't be used by change_msg()
            key_to_use = next(chain(cand_keys - key_to_next_msg.keys(), cand_keys))
            print(f"{key_to_use} -> {key} (change_key)")
            return key_to_use

    def change_msg(key, msg, free_keys):
        # key, different_msg -> key, msg
        if key in free_keys:
            assert msg != key_to_msg[key]
            bot.edit_message(chan_id, msg_ids[key], content=msg)  # TODO: await this
            return key


    unmapped     = key_to_next_msg.keys()
    free_keys    = key_to_msg.keys()
    next_msg_ids = {}

    unmapped, free_keys, next_msg_ids = try_map(no_change,  unmapped, free_keys, next_msg_ids)
    unmapped, free_keys, next_msg_ids = try_map(change_key, unmapped, free_keys, next_msg_ids)
    unmapped, free_keys, next_msg_ids = try_map(change_msg, unmapped, free_keys, next_msg_ids)

    # create new messages for any remaining keys that weren't assigned to
    for key in unmapped:
        print(f"None -> {key} (send_msg)")
        next_msg_ids[key] = await bot.send_message(chan_id, content=key_to_next_msg[key])

    # delete unused messages
    for key in free_keys:
        print(f"{key} -> {None} (del_msg)")
        await bot.delete_message(chan_id, msg_ids[key])

    return next_msg_ids
