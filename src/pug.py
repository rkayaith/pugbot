import asyncio
from dataclasses import dataclass, field, replace
from itertools import chain
import random
import sys
import textwrap
import traceback
from typing import Any, Dict, FrozenSet, Union
import zlib

from discord import ChannelType, Colour, Embed, Object, TextChannel
from discord.ext import commands

from .bot_stuff import Bot, update_discord
from .states import React, State, StoppedState, IdleState
from .utils import fset, first, anext

MAP_LIST = [
    # tier 1: classics
    [
        'ctf_RSM',
        'ctf_conflict',
        'ctf_conflict2',
        'dkoth_kots',
        'koth_contra',
        'koth_harvest',
    ],
    # tier 2: good
    [
        'cp_kistra',
        'ctf_eiger',
        'ctf_purple',
        'koth_corinth',
        'koth_odvuschwa',
        'koth_valley',
        'koth_viaduct_a3'
    ],
    # tier 3: spicy
    [
        'arena_contra',
        'arena_harvest',
        'cp_mountainjazz',
    ]
]

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
        reacts=fset(), history=tuple(),
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
            ctx.state = None
            del chan_ctxs[chan_id]
            print(f"Patching {chan_id} ctx failed, resetting state. Error:\n{err}")

    @commands.is_owner()
    @bot.command(hidden=True)
    async def status(ctx):
        s = ""
        for chan_id, chan_ctx in chan_ctxs.items():
            state = type(chan_ctx.state).__name__
            s += f"{chan_id} | {state}\n"
        s = (
            "```\n"
            "chan_id            | state\n"
            "-------------------+----------\n"
            f"{s}\n"
            "```\n"
        )
        await ctx.send(s)

    @commands.is_owner()
    @bot.command(hidden=True)
    async def reset(ctx):
        for chan_id in list(chan_ctxs):
            del chan_ctxs[chan_id]

    @commands.is_owner()
    @bot.command(hidden=True)
    async def poke(ctx):
        channel = ctx.channel
        chan_ctx = chan_ctxs[channel.id]
        await update_state(bot, chan_ctx, channel.id, lambda c: c.state)
        await ctx.send(f"poked")

    @bot.command()
    async def start(ctx, channel: TextChannel = None):
        """
        Starts a pug in a channel

        If no channel is given, the current channel is used.
        The PUG steps are:
          1. People react to the bot to queue up as a host/captain/player.
          2. If necessary, there's a vote to choose the host and 2 captains.
          3. Captains react to the bot to pick players. The captain with the
             least votes gets first pick.
          4. Once teams are picked, everyone gets pinged.
        Whoever starts the PUG has additional controls during some steps.
        """
        if channel is None:
            channel = ctx.channel

        if channel.type != ChannelType.text:
            await ctx.send("PUGs can only run in text channels.")
            return

        chan_ctx = chan_ctxs[channel.id]
        if not isinstance(chan_ctx.state, StoppedState):
            await ctx.send(f"I'm already running in {channel.mention}")
            return

        await update_state(bot, chan_ctx, channel.id, lambda c: IdleState.make(c.state, admin_ids=c.state.admin_ids | { ctx.author.id }))

        if channel != ctx.channel:
            await ctx.send(f"Started in {channel.mention}.")
        print(f"Started in {channel.mention}.")

    @bot.command()
    async def stop(ctx, channel: TextChannel = None):
        """ Stops the bot in a channel """
        if channel is None:
            channel = ctx.channel
        channel_name = getattr(channel, 'mention', f"'{channel}'")

        chan_ctx = chan_ctxs[channel.id]
        if isinstance(chan_ctx.state, StoppedState):
            await ctx.send(f"I'm not running in {channel_name}")
            return

        await update_state(bot, chan_ctx, channel.id, lambda c: StoppedState.make(c.state))
        await ctx.send(f"Stopped in {channel_name}")


    ncols = 3
    tier_list = []
    col_widths = [max(len(map_name) for tier in MAP_LIST
                                    for map_name in tier[i::ncols])
                  for i in range(ncols)]
    for i, tier in enumerate(MAP_LIST):
        rows = [tier[j:j+ncols] for j in range(0, len(tier), ncols)]
        tier_list += [f"\nTIER {i+1}:"]
        tier_list += ['  '.join(map_name.ljust(width) for map_name, width in zip(row, col_widths))
                                                      for row in rows]

    @bot.command(help=textwrap.dedent(
        f"""
        Picks a random map
        Maps are only picked from 'lowest_tier' and above, and are equally weighted.
        Defaults to picking from tier 2 and above.
        """) + '\n'.join(tier_list))
    async def randmap(ctx, lowest_tier: int = 2):
        await ctx.send(embed=map_to_embed(rand_map(lowest_tier)))

    @bot.command(hidden=True)
    async def maps(ctx, tier: int):
        """ Shows all the options the randmap command can choose from """
        for m in MAP_LIST[tier-1]:
            await ctx.send(embed=map_to_embed(m))

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
        if event.user_id == bot.user_id:
            print("ignored bot")
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


def rand_map(lowest_tier):
    tiers = MAP_LIST[:lowest_tier] or [['ctf_el_map']]
    maps = list(chain(*tiers))
    return random.choice(maps)

last_map = rand_map(-1)
def map_to_embed(map_name):
    global last_map

    hue = (zlib.adler32(map_name.encode()) & 0xff) / 0xff
    colour = Colour.from_hsv(hue, 0.5, 0.9)
    embed = Embed(title=f"Fuck {last_map.split('_', 1)[-1].capitalize()} All My Homies Play",
                  description=map_name,
                  colour=colour)

    mode = {
        '3cp': 'CP',
        '5cp': 'CP',
        'ad': 'AD',
        'arena': 'Arena',
        'cp': 'CP',
        'ctf': 'CTF',
        'dkoth': 'DKOTH',
        'koth': 'KOTH',
    }[map_name.split('_')[0].lower()]
    img_url = f"https://raw.githubusercontent.com/Derpduck/GG2-Map-Archive/master/{mode}/{map_name}.png"
    embed = embed.set_image(url=img_url)

    last_map = map_name
    return embed

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
        yield (state := next_state)


async def update_state(bot, ctx, chan_id, next_state_fn):
    # TODO: this whole function is kinda wack, should probably rethink this at
    #       some point

    async with ctx.lock:
        # TODO: don't do this. it's better if ctx.state.messages and
        #       ctx.msg_id_map stay in sync
        ctx.state = curr_state = next_state_fn(ctx)

    state_seq = state_sequence(curr_state)
    while (next_state := await anext(state_seq, None)) is not None:
        async with ctx.lock:
            if ctx.state is not curr_state:
                # someone changed the state while we were getting the next one,
                # so we can stop here
                return

            # NOTE: we use the messages and reacts from 'ctx', NOT 'curr_state'
            #       since we don't know whether that state was fully applied.
            next_msg_id_map = await update_discord(bot, chan_id, ctx.msg_id_map,
                                                  ctx.messages, next_state.messages,
                                                  ctx.reacts, next_state.reacts)
            ctx.messages = next_state.messages
            ctx.state    = next_state
            if first(ctx.msg_id_map.values()) == first(next_msg_id_map.values()):
                ctx.reacts = next_state.reacts
            else:
                # the main message changed, which means we should remove the old
                # reacts. we also remake the state sequence with the updated reacts.
                ctx.reacts = next_state.reacts - ctx.reacts
                state_seq = state_sequence(replace(next_state, reacts=ctx.reacts))
                print("restarting seq")
            ctx.msg_id_map = next_msg_id_map
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
