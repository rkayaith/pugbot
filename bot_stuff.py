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

async def update_discord(bot, chan_id, prev_msg_ids, prev_msgs, next_msgs):
    assert prev_msg_ids.keys() == prev_msgs.keys()

    msg_to_prev_keys = invert_dict(prev_msgs)

    def no_change(key, msg):
        if msg == prev_msgs.get(key):
            print(f"{key} -> {key} (no_change)")
            return (key, msg), as_fut(prev_msg_ids[key])

    def remap_id(key, msg):
        # if there's already a message with the same content but a different key,
        # remap that message id to this key
        if (existing_keys := msg_to_prev_keys.get(msg)):
            prev_key = next(iter(existing_keys))  # just pick one randomly TODO: prioritize keys that can't be used by edit_msg()
            print(f"{prev_key} -> {key} (remap_id)")
            return (prev_key, msg), as_fut(prev_msg_ids[prev_key])

    def edit_msg(key, msg):
        if (prev_msg := prev_msgs.get(key)) is not None:
            # a message with this key exists
            if key in msg_to_prev_keys[prev_msg]:
                # that message hasn't been mapped yet
                # reuse the message and edit it's content
                print(f"{key} -> {key} (edit)")
                async def edit():
                    # TODO: not the best way to do this...
                    bot.edit_message(chan_id, prev_msg_ids[key], content=msg)
                    return prev_msg_ids[key]
                return (key, prev_msg), edit()

    def send_msg(key, msg):
        print(f"None -> {key} (send)")
        return None, bot.send_message(chan_id, content=msg)


    next_msg_ids = {}
    def try_map(map_func):
        def filter_fn(item):
            key, msg = item
            if (ret := map_func(key, msg)) is None:
                # mapping failed, keep 'item'
                return True

            prev_value, msg_id = ret
            next_msg_ids[key] = msg_id
            if prev_value is not None:
                # remove 'prev_key' from the set of available keys left to be mapped
                prev_key, prev_msg = prev_value
                msg_to_prev_keys[prev_msg].remove(prev_key)

            # mapping succeeded, filter out 'item'
            return False
        return filter_fn


    msgs_to_map = next_msgs.items()
    msgs_to_map = list(filter(try_map(no_change), msgs_to_map))
    msgs_to_map = list(filter(try_map(remap_id), msgs_to_map))
    msgs_to_map = list(filter(try_map(edit_msg), msgs_to_map))
    msgs_to_map = list(filter(try_map(send_msg), msgs_to_map))
    assert len(msgs_to_map) == 0

    # TODO: bleh. find another way
    next_msg_ids = { key: await msg_id for key, msg_id in next_msg_ids.items() }

    # delete unused messages
    for keys in msg_to_prev_keys.values():
        for key in keys:
            await bot.delete_message(chan_id, prev_msg_ids[key])

    return next_msg_ids

    """
    # update message content
    for key, msg in next_msgs.items():

        if msg in msg_to_prev_key:
            # message 
            next_msg_ids[key] = prev_msg_ids[msg_to_prev_key[msg]]
            continue

        assert False, "TODO"

        msg_type = { 'embed': msg } if isinstance(msg, Embed) else { 'content', msg }
        if key in ctx.msg_id_map:
            # edit the existing message
            msg_id = ctx.msg_id_map[key]
            tasks.append(bot.edit_message(chan_id, **msg_type))
        else:
            # create a new message
            # TODO: can we await the task later?
            ctx.msg_id_map[key] = await bot.send_message(chan_id, **msg_type)
            # ctx only tracks reacts to the 'main' message, so we clear it
            if key == 'main':
                ctx.reacts = fset()

        # TODO: if the main message changed we should set ctx.reacts = fset()

    return msg_id_map

    # add new reacts
    additions = next_state.reacts - ctx.reacts
    removals  = ctx.reacts - next_state.reacts
    for user_id, emoji in additions:
        assert user_id == bot.user.id  # we can't add reactions from other people
        tasks,append(bot.add_reaction(chan_id, msg_id, emoji))

    # TODO: if removals == ctx.reacts we can use clear_reactions(). might want to do it only if len(removals) > 1 though
    for user_id, emoji in removals:
        tasks,append(bot.remove_reaction(chan_id, msg_id, user_id, emoji))
    """
