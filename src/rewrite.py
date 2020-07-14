import asyncio
from dataclasses import dataclass, field, replace
import sys
import traceback
from typing import Any, Dict, FrozenSet, Union

from discord import ChannelType, Embed, Object, TextChannel
from discord.ext import commands

from .bot_stuff import Bot, update_discord
from .states import React, State, StoppedState, IdleState
from .utils import fset, first


@dataclass
class ChanCtx:
    state: State
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # current discord state:
    msg_id_map: Dict[Any, int] = field(default_factory=dict)
    messages: Dict[Any, Union[str, Embed]] = field(default_factory=dict)
    reacts: FrozenSet[React] = fset()


def setup(bot):
    from src.mem import chan_ctxs
    chan_ctxs.default_factory = lambda: ChanCtx(StoppedState(
        bot=bot, admin_ids={ bot.owner_id },
        reacts=fset(), history=tuple()
    ))

    """
    This is big hack to support hot reloading code while the bot is running.
    When this module is reloaded, we try and track down every instance we've
    created and update its class to the new definition.
    """
    bot.__class__ = Bot

    import src.states
    for chan_id, ctx in list(chan_ctxs.items()):
        try:
            # we have to use object.__setattr__ since these are frozen dataclasses
            object.__setattr__(ctx.state, '__class__',
                               getattr(src.states, ctx.state.__class__.__name__))
        except Exception as err:
            del chan_ctxs[chan_id]
            print(f"Patching {chan_id} ctx failed, resetting state. Error:\n{err}")


    @bot.command()
    async def reset(ctx):
        for chan_id in list(chan_ctxs):
            del chan_ctxs[chan_id]


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

        await update_state(bot, chan_ctx, channel.id, lambda c: IdleState.make(c.state, admin_ids=c.state.admin_ids | { ctx.author.id }))

        if channel != ctx.channel:
            await ctx.send(f"Started in {channel.mention}.")
        print(f"Started in {channel.mention}.")

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

    @bot.listen('on_raw_reaction_add')
    @bot.listen('on_raw_reaction_remove')
    async def on_raw_reaction(event):
        # ignore the bot's reactions
        if event.user_id == bot.user.id:
            return

        # ignore reactions to channels we aren't watching
        if event.channel_id not in chan_ctxs:
            return

        react = React(event.user_id, str(event.emoji))
        if event.event_type == 'REACTION_ADD':
            update = lambda reacts: reacts | { react }
        else:
            update = lambda reacts: reacts - { react }

        await update_reacts(bot, chan_ctxs[event.channel_id],
                            event.channel_id, event.message_id, update)




async def state_sequence(start_state):
    state_seq = start_state.on_update()
    while True:
        async for state in state_seq:
            yield state

        # call on_update() on the final state and
        # see if it gives us something different
        state_seq = state.on_update()
        if state == (next_state := await state_seq.__anext__()):
            # it didn't, so stop here
            return
        yield next_state


async def update_state(bot, ctx, chan_id, next_state_fn):
    async with ctx.lock:
        ctx.state = curr_state = next_state_fn(ctx)

    async for next_state in state_sequence(curr_state):
        async with ctx.lock:
            if ctx.state is not curr_state:
                # someone changed the state while we were getting the next one,
                # so we can stop here
                return

            # NOTE: we use the messages and reacts from 'ctx', NOT 'curr_state'
            #       since we don't know whether that state was fully applied.
            ctx.msg_id_map = await update_discord(bot, chan_id, ctx.msg_id_map,
                                                  ctx.messages, next_state.messages,
                                                  ctx.reacts, next_state.reacts)
            ctx.state    = next_state
            ctx.reacts   = next_state.reacts
            ctx.messages = next_state.messages
        curr_state = next_state
    return curr_state


async def update_reacts(bot, ctx, chan_id, msg_id, update_reacts_fn):
    async with ctx.lock:
        # we only care about reacts to the main message
        # TODO: track reacts to all messages?
        if msg_id != first(ctx.msg_id_map.values()):
            return
        ctx.reacts = frozenset(update_reacts_fn(ctx.reacts))

    await update_state(bot, ctx, chan_id, lambda ctx: replace(ctx.state, reacts=ctx.reacts))
