import asyncio
from dataclasses import dataclass, replace
import os
import random
import sys
from typing import FrozenSet, List, Optional, Union
import traceback

from discord import ChannelType, Member, Message, Status, TextChannel, User, errors, utils
from discord.ext import commands

MIN_HOSTS = 1
MIN_PLAYERS = int(os.environ.get('MIN_PLAYERS', default='8'))
MAX_PLAYERS = 12
HOST_EMOJI = '\N{Regional Indicator Symbol Letter H}'
DONE_EMOJI = '\N{WHITE HEAVY CHECK MARK}'


pugs = {}   # per-channel pug states
locks = {}  # per-channel lock for pug states


async def update_state(msg):
    """ Update pug state using a new message. """
    async with locks[msg.channel.id]:
        # compute the next state
        next_state = await pugs[msg.channel.id].next(msg)

        if next_state.msg is None:
            # if the new state doesn't have a message, create one and add reactions
            next_state = replace(next_state, msg=await msg.channel.send(next_state))
            await asyncio.gather(*(next_state.msg.add_reaction(r) for r in next_state.REACTS))
        else:
            # otherwise just edit the existing message
            await next_state.msg.edit(content=next_state)

        print(next_state)
        pugs[msg.channel.id] = next_state

def setup(bot):
    async def init(msg):
        assert msg.channel.id not in pugs
        pugs[msg.channel.id] = IdleState(bot, msg, None)
        locks[msg.channel.id] = asyncio.Lock()
        await asyncio.gather(*(msg.add_reaction(r) for r in IdleState.REACTS))
        await update_state(msg)

    @bot.command(aliases=['s'])
    async def start(ctx, channel: TextChannel = None):
        """ Start the bot in a channel """
        if channel is None:
            channel = ctx.channel

        if channel.type != ChannelType.text:
            await ctx.send("PUGs can only run in text channels.")
            return

        if channel.id in pugs:
            await ctx.send(f"I'm already running in {channel.mention}.")
            return

        await init(await channel.send("Loading..."))

        if channel != ctx.channel:
            await ctx.send(f"Started in {channel.mention}.")

    @bot.command()
    async def stop(ctx, channel: TextChannel = None):
        if channel is None:
            channel = ctx.channel
        channel_name = getattr(channel, 'mention', f"'{channel}'")

        if channel.id not in pugs:
            await ctx.send(f"I'm not running in {channel_name}.")
            return

        async with locks[channel.id]:
            del pugs[channel.id]
            del locks[channel.id]
        await ctx.send(f"Stopped in {channel_name}.")

    @bot.command()
    async def resume(ctx, msg: Message):
        """ Start the bot on an existing message. """
        await init(msg)

    @bot.command(aliases=['p'])
    async def poke(ctx, channel: TextChannel = None):
        """ Force the bot to update its state (in case it gets stuck) """
        if channel is None:
            channel = ctx.channel
        channel_name = getattr(channel, 'mention', f"'{channel}'")

        if channel.id not in pugs:
            await ctx.send(f"Nothing to poke in {channel_name}.")
            return

        await update_state(await channel.fetch_message(pugs[channel.id].msg.id))
        if channel != ctx.channel:
            await ctx.send(f"Poked {channel_name}.")


    @bot.command()
    @commands.is_owner()
    async def status(ctx):
        """ Print out the bot's state in all channels. """
        await ctx.send('**Status**\n' + (
            '\n\n'.join(f"`channel: {chan_id} | msg: {state.msg.id}`\n{state}" for chan_id, state in pugs.items())
            or 'Not active in any channels.'
        ))

    @bot.command()
    @commands.is_owner()
    async def clean(ctx, channel: TextChannel = None):
        """ Clean up the bot's messages in a channel """
        if channel is None:
            channel = ctx.channel
        await channel.purge(check=lambda m: m.author == bot.user)

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


@dataclass(frozen=True)
class PugState:
    REACTS = []

    bot: commands.Bot
    msg: Optional[Message]
    notice: Optional[Message]

    @classmethod
    async def notify(cls, state, content):
        assert state.msg is not None
        if state.notice is not None:
            await state.notice.delete()
        return replace(state, notice = await state.msg.channel.send(content))


@dataclass(frozen=True)
class IdleState(PugState):
    REACTS = [HOST_EMOJI]

    hosts: FrozenSet[Union[User, Member]] = frozenset()
    players: FrozenSet[Union[User, Member]] = frozenset()

    def __str__(self):
        return (
            f"**Waiting for players**\n"
            f"React with {HOST_EMOJI} if you can host.\n"
            f"React with anything else to play.\n"
            f"```\n"
            f"{len(self.hosts)} host(s):   {strjoin(self.hosts)}\n"
            f"{len(self.players)} player(s): {strjoin(self.players)}\n"
            f"```"
        )

    async def next(self, new_msg: Message):
        assert new_msg.id == self.msg.id

        host_reacts = { r for r in new_msg.reactions if r.emoji == HOST_EMOJI }
        player_reacts = set(new_msg.reactions) - host_reacts

        hosts = frozenset([u for r in host_reacts async for u in r.users()]) - { self.bot.user }
        players = frozenset([u for r in player_reacts async for u in r.users()]) - { self.bot.user }

        # if we're still waiting for people, stay in the idle state
        if len(hosts) < MIN_HOSTS or len(players) < MIN_PLAYERS:
            return replace(self, msg=new_msg, hosts=hosts, players=players)

        # if there's idle players, remove them and try again
        is_afk = lambda user: isinstance(user, Member) and user.status != Status.online
        afks = list(filter(is_afk, hosts | players))
        if afks:
            next_state = await PugState.notify(self, f"Removing afk players: `{strjoin(afks)}`")
            await asyncio.gather(*(react.remove(user) for user in afks for react in new_msg.reactions))
            return await next_state.next(await new_msg.channel.fetch_message(new_msg.id))

        # start pug
        await self.msg.delete()  # delete the current message
        host = random.choice(list(hosts))
        team_size = min(MAX_PLAYERS, len(players)) // 2
        players = random.sample(players, k=team_size * 2)
        red, blu = players[:team_size], players[team_size:]
        return RunningState(self.bot, None, self.notice, host, red, blu)


@dataclass(frozen=True)
class RunningState(PugState):
    REACTS = [DONE_EMOJI]

    host: Member
    red: List[Member]
    blu: List[Member]

    def __str__(self):
        return (
            f"**PUG started**\n"
            f"React with {DONE_EMOJI} once the PUG is done.\n"
            f"```\n"
            f"Host: {self.host}\n"
            f"\n"
            f"RED: {strjoin(self.red)}\n"
            f"BLU: {strjoin(self.blu)}\n"
            f"```"
        )

    async def next(self, msg: Message):
        assert msg.id == self.msg.id

        done_react = utils.get(msg.reactions, emoji=DONE_EMOJI)
        if done_react.count > 2 or await bot_owner_reacted(self.bot, done_react):
            # update the current message
            await self.msg.clear_reactions()
            await self.msg.edit(content=(
                f"**PUG finished**\n"
                f"```\n"
                f"Host: {self.host}\n"
                f"\n"
                f"RED: {strjoin(self.red)}\n"
                f"BLU: {strjoin(self.blu)}\n"
                f"```"
            ))

            # start the next pug
            return IdleState(self.bot, msg=None, notice=self.notice)


def strjoin(it, sep=', '):
    return sep.join(map(str, it))


async def bot_owner_reacted(bot, reaction):
    """ returns whether the bot owner has reacted with 'reaction' """
    return await reaction.users().find(bot.is_owner) is not None
