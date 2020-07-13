import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
import sys
import traceback
from typing import Any, Dict, FrozenSet, Union

from discord import ChannelType, Object, TextChannel
from discord.ext import commands

from bot_stuff import Bot, update_discord
from states import React, State, StoppedState, IdleState
from utils import fset

@dataclass
class ChanCtx:
    state: State
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    msg_id_map: Dict[Any, int] = field(default_factory=dict)
    reacts: FrozenSet[React] = fset()


def setup(bot):
    chan_ctxs = defaultdict(lambda: ChanCtx(StoppedState(
        bot=bot,
        admin_ids={bot.owner_id},
        reacts=fset(),
        history=tuple()
    )))

    @bot.command(aliases=['s'])
    async def start(ctx, channel: TextChannel = None):
        """ Starts the bot in a channel """
        if channel is None:
            channel = ctx.channel

        if channel.type != ChannelType.text:
            await ctx.send("PUGs can only run in text channels.")
            return

        chan_ctx = chan_ctxs[channel.id]
        if not isinstance(chan_ctx.state, StoppedState):
            await ctx.send(f"I'm already running in {channel.mention}.")
            return

        await update_state(bot, channel.id, chan_ctx, lambda state: IdleState.make(state, admin_ids=state.admin_ids | { ctx.author.id }))

        if channel != ctx.channel:
            await ctx.send(f"Started in {channel.mention}.")

#   @bot.command()
#   async def stop(ctx, channel: TextChannel = None):
#       """ Stops the bot in a channel """
#       if channel is None:
#           channel = ctx.channel
#       channel_name = getattr(channel, 'mention', f"'{channel}'")
#
#       if channel.id not in pugs:
#           await ctx.send(f"I'm not running in {channel_name}.")
#           return
#
#       async with locks[channel.id]:
#           await pugs[channel.id].msg.edit(content='**Pugbot Stop**')
#           await pugs[channel.id].msg.clear_reactions()
#           del pugs[channel.id]
#           del locks[channel.id]
#       await ctx.send(f"Stopped in {channel_name}.")

    # @bot.command()
    # async def randmap(ctx):
        # """ Picks a random map """
        # await ctx.send(f"Random map: {rand_map()}")

#   @bot.command(hidden=True)
#   @commands.is_owner()
#   async def status(ctx):
#       """ Print out the bot's state in all channels. """
#       await ctx.send('**Status**\n' + (
#           '\n\n'.join(f"`{chan_id}-{state.msg.id}` {state.msg.channel.mention}\n{state}" for chan_id, state in pugs.items())
#           or 'Not active in any channels.'
#       ))

    @bot.listen()
    async def on_ready():
        # make sure the bot's owner_id value is set by making a call to is_owner()
        await bot.is_owner(Object(None))
        print(f"Bot owner is {bot.get_user(bot.owner_id)}")

    @bot.listen()
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            print(f"Exception occured in '{ctx.command}'", file=sys.stderr)
            traceback.print_exception(None, error.original, error.original.__traceback__, file=sys.stderr)
            await ctx.send(f'Something went wrong ({type(error.original).__name__}).')
            return

        await ctx.send(error)

    """
    @bot.listen('on_raw_reaction_add')
    @bot.listen('on_raw_reaction_remove')
    async def on_raw_reaction(event):
        # ignore the bot's reactions
        if event.user_id == bot.user.id:
            return

        # ignore reactions to channels we aren't watching
        if event.channel_id not in pugs:
            return

        # ignore reactions to messages we aren't watching
        if event.message_id != pugs[event.channel_id].msg.id:
            return

        # fetch the full message and update state
        # NOTE: if we used the 'reaction_add' and 'reaction_remove' events we
        #       wouldn't have to fetch the message, but those events only fire
        #       for messages in the bot's message cache.
        channel = bot.get_channel(event.channel_id)
        msg = await channel.fetch_message(event.message_id)
        await update_state(msg)
    """


async def update_state(bot, chan_id, ctx, next_state_fn):
    async with ctx.lock:
        curr_state = ctx.state
        next_state = next_state_fn(curr_state)
        curr_reacts = ctx.reacts
        next_reacts = next_state.reacts

        # apply changes to discord
        ctx.msg_id_map = await update_discord(bot, chan_id, ctx.msg_id_map,
                                              curr_state.messages, next_state.messages,
                                              curr_reacts, next_reacts)

        # update ctx
        ctx.state  = next_state
        ctx.reacts = next_state.reacts
    return next_state


async def update_reacts(bot, ctx, chan_id, msg_id, update_fn):
    async with ctx.lock:
        # we only care about reacts to the main message
        # TODO: track reacts to all messages?
        if msg_id != first(msg_id_map.values()):
            return
        ctx.reacts = (reacts := frozenset(update_fn(ctx.reacts)))
        curr_state = ctx.state

    async def state_sequence(start_state, reacts):
        state_seq = start_state.on_update(bot, reacts=reacts)
        while True:
            async for state in state_seq:
                yield state

            # call on_update() on the final state and
            # see if it gives us something different
            state_seq = state.on_update(bot, reacts=state.reacts)
            if state == (next_state := await state_seq.anext()):
                # it didn't, so stop here
                return
            yield next_state

    async for next_state in state_sequence(curr_state, reacts):
        async with ctx.lock:
            # someone changed the state while we were getting the next one,
            # so we can stop here
            if ctx.state is not curr_state:
                return

            # apply changes to discord
            ctx.msg_id_map = await update_discord(bot, ctx, chan_id, curr_state, next_state)
            ctx.state  = next_state
            ctx.reacts = next_state.reacts
        curr_state = next_state


