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

async def update_discord(bot, chan_id, prev_msg_ids, prev_msgs, next_msgs):
    assert prev_msg_ids.keys() == prev_msgs.keys()

    next_msg_ids = {}

    tasks = []
    msg_to_prev_key = invert_dict(prev_msgs)


    remaining_items = set(next_msgs.items())

    # for existing messages with an unchanged key, use the previous message id
    for key, msg in list(remaining_items):
        if msg == prev_msgs.get(key):
            # this message already exists with the same key.
            remaining_items.remove((key, msg))
            msg_to_prev_key[msg].remove(key)
            next_msg_ids[key] = prev_msg_ids[key]

    # for existing messages with a changed but existing key,
    # try to use the existing key's id
    for key, msg in list(remaining_items):
        if msg_to_prev_key.get(msg):
            # message exists but with a different key.
            remaining_items.remove((key, msg))
            prev_key = msg_to_prev_key[msg].pop()
            next_msg_ids[key] = prev_msg_ids[prev_key]

    # for new messages with an existing key,
    # try to use the existing key's id and edit the message
    for key, msg in list(remaining_items):
        if key in prev_msgs and msg_to_prev_key[prev_msgs[key]]:
            # key existed before with a different message, **and is still unused**
            remaining_items.remove((key, msg))
            msg_to_prev_key[prev_msgs[key]].remove(key)
            next_msg_ids[key] = prev_msg_ids[key]
            await bot.edit_message(chan_id, next_msg_ids[key], content=msg)

    # for remaining messages, create a new message
    for key, msg in list(remaining_items):
        # TODO: make an assertion or something
        next_msg_ids[key] = await bot.send_message(chan_id, content=msg)

    # delete unused messages
    for keys in msg_to_prev_key.values():
        for key in keys:
            await bot.delete_message(chan_id, prev_msg_ids[key])

    return next_msg_ids


    # new msg:     key not in prev_msgs
    # unchanged:   msg is prev_msgs[key]
    # key changed: msg is not prev_msgs[key] and msg in (unclaimed) prev_msgs.values()
    # msg changed: msg is not prev_msgs[key] and msg_ids[key] is available

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
