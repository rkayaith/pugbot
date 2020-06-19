import asyncio
from dataclasses import dataclass, replace
import os
from operator import itemgetter as get
import random
import sys
from typing import ClassVar, FrozenSet, List, Optional, Tuple, Union
import traceback

from discord import ChannelType, Member, Message, Reaction, Status, TextChannel, User, errors, utils
from discord.ext import commands
from flag import flag

from mem import pugs, locks

MIN_HOSTS = 1
MIN_CAPTS = 2
MIN_VOTES = 5
MIN_PLAYERS = int(os.environ.get('MIN_PLAYERS', default='8'))
MAX_PLAYERS = 12

SKIP_EMOJI = '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}'
PAUSE_EMOJI = '\N{DOUBLE VERTICAL BAR}\uFE0F'
HOST_EMOJI = '\N{GLOBE WITH MERIDIANS}'
DONE_EMOJI = '\N{WHITE HEAVY CHECK MARK}'
CAPT_EMOJI = '\N{BILLED CAP}'

FLAG_EMOJIS = ['\U0001F3F3\U0000FE0F\U0000200D\U0001F308', '\U0001F3F4\U0000200D\U00002620\U0000FE0F'] + list(map(flag, ['in', 'cn', 'br', 'ae', 'kp', 'im']))
OPTION_EMOJIS = [f'{i}\N{COMBINING ENCLOSING KEYCAP}' for i in range(10)] + [chr(i) for i in range(ord('\N{REGIONAL INDICATOR SYMBOL LETTER A}'), ord('\N{REGIONAL INDICATOR SYMBOL LETTER A}') + 26)]

MAP_LIST = [
    ('ctf_conflict', 1), ('koth_harvest', 1), ('koth_contra', 1),
    ('dkoth_kots', 0.5), ('ctf_conflict2', 0.5), ('ctf_rsm', 0.5), ('cp_mountainjazz', 0.5), ('koth_odvuschwa', 0.5),
    ('koth_corinth', 0.1), ('cp_kistra', 0.1), ('ctf_eiger', 0.1),
    ('koth_viaduct', 0.1), ('koth_valley', 0.1), ('arena_harvest', 0.1),
]


def rand_map():
    maps = [m for m, w in MAP_LIST]
    weights = [w for m, w in MAP_LIST]
    [map_name] = random.choices(maps, weights=weights, k=1)
    return map_name

async def update_state(msg):
    """ Update pug state using a new message. """
    assert msg.channel.id in pugs
    assert msg.channel.id in locks

    async with locks[msg.channel.id]:
        prev_state = pugs[msg.channel.id]
        # HACK: if this file has been reloaded, remake the state instance with the new type definition
        if type(prev_state) != (new_type := globals()[type(prev_state).__name__]):
            prev_state = new_type(**vars(prev_state))

        # compute the next state
        next_state = await prev_state.next(msg)

        if next_state.msg is None:
            # if the new state doesn't have a message, create one and add reactions
            next_state = replace(next_state, msg=await msg.channel.send(next_state))
            await asyncio.gather(*(next_state.msg.add_reaction(r) for r in next_state.reacts))
        else:
            # otherwise just edit the existing message
            await next_state.msg.edit(content=next_state)

        print(next_state)
        pugs[msg.channel.id] = next_state

    # delete the old message if we're using a new one now
    if prev_state.msg.id != next_state.msg.id:
        await prev_state.msg.delete()


def setup(bot):
    async def init(msg):
        assert msg.channel.id not in pugs
        pugs[msg.channel.id] = IdleState(bot, msg, None)
        locks[msg.channel.id] = asyncio.Lock()
        await asyncio.gather(*(msg.add_reaction(r) for r in IdleState.reacts))
        await update_state(msg)

    @bot.command(aliases=['s'])
    async def start(ctx, channel: TextChannel = None):
        """ Starts the bot in a channel """
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
        """ Stops the bot in a channel """
        if channel is None:
            channel = ctx.channel
        channel_name = getattr(channel, 'mention', f"'{channel}'")

        if channel.id not in pugs:
            await ctx.send(f"I'm not running in {channel_name}.")
            return

        async with locks[channel.id]:
            await pugs[channel.id].msg.edit(content='**Pugbot Stop**')
            await pugs[channel.id].msg.clear_reactions()
            del pugs[channel.id]
            del locks[channel.id]
        await ctx.send(f"Stopped in {channel_name}.")

    @bot.command(hidden=True)
    async def resume(ctx, msg: Message):
        """ Start the bot on an existing message. """
        assert msg.channel.type == ChannelType.text
        await init(msg)
        await ctx.send(f"Resumed in {msg.channel.mention} (<{msg.jump_url}>).")

    @bot.command(aliases=['p'], hidden=True)
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
    async def randmap(ctx):
        """ Picks a random map """
        await ctx.send(f"Random map: {rand_map()}")

    @bot.command(hidden=True)
    @commands.is_owner()
    async def status(ctx):
        """ Print out the bot's state in all channels. """
        await ctx.send('**Status**\n' + (
            '\n\n'.join(f"`{chan_id}-{state.msg.id}` {state.msg.channel.mention}\n{state}" for chan_id, state in pugs.items())
            or 'Not active in any channels.'
        ))

    @bot.command(hidden=True)
    @commands.is_owner()
    async def clean(ctx, channel: TextChannel = None):
        """ Clean up the bot's messages in a channel """
        if channel is None:
            channel = ctx.channel
        if channel.type != ChannelType.text:
            await ctx.send("This only works in text channels.")
            return

        assert channel.id not in pugs
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
    bot: commands.Bot
    msg: Optional[Message]
    notice: Optional[Message]

    @classmethod
    async def notify(cls, state, content):
        assert state.msg is not None
        if state.notice is not None:
            await state.notice.delete()
        return replace(state, notice=await state.msg.channel.send(content))


@dataclass(frozen=True)
class IdleState(PugState):
    reacts: ClassVar[List[str]] = [HOST_EMOJI, CAPT_EMOJI]

    hosts: FrozenSet[Union[User, Member]] = frozenset()
    captains: FrozenSet[Union[User, Member]] = frozenset()
    players: FrozenSet[Union[User, Member]] = frozenset()

    def __str__(self):
        return (
            f"**Waiting for players**\n"
            f"React with {HOST_EMOJI} if you can host.\n"
            f"React with {CAPT_EMOJI} to captain.\n"
            f"React with anything else to play.\n"
            f"```\n"
            f"{len(self.hosts)} host(s):     {', '.join(u.name for u in self.hosts)}\n"
            f"{len(self.captains)} captains(s): {', '.join(u.name for u in self.captains)}\n"
            f"{len(self.players)} player(s):   {', '.join(u.name for u in self.players)}\n"
            f"```"
        )

    async def next(self, new_msg: Message):
        assert new_msg.id == self.msg.id

        reactions = [(reaction, user)
                     for reaction in new_msg.reactions
                     async for user in reaction.users()
                     if user != self.bot.user]

        hosts    = frozenset(u for r, u in reactions if r.emoji == HOST_EMOJI)
        captains = frozenset(u for r, u in reactions if r.emoji == CAPT_EMOJI)
        players  = frozenset(u for r, u in reactions if r.emoji != HOST_EMOJI)

        # if we're still waiting for people, stay in the idle state
        end_early = (SKIP_EMOJI, self.bot.owner_id) in ((r.emoji, u.id) for r, u in reactions)
        keep_waiting = (PAUSE_EMOJI, self.bot.owner_id) in ((r.emoji, u.id) for r, u in reactions)
        if keep_waiting or (not end_early and (len(hosts) < MIN_HOSTS or len(captains) < MIN_CAPTS or len(players) < MIN_PLAYERS)):
            return replace(self, msg=new_msg, hosts=hosts, captains=captains, players=players)

        # if anyone is idle, remove them and try again
        afks = [(r, user) for r, user in reactions
                if not isinstance(user, Member) or user.status != Status.online]
        if afks:
            next_state = await PugState.notify(self, f"Removing afk players: `{strjoin({ u for _, u in afks })}`")
            await asyncio.gather(*(reaction.remove(user) for reaction, user in afks))
            return await next_state.next(await new_msg.channel.fetch_message(new_msg.id))

        # start pug
        # captains = captains | { self.bot.user }; hosts = hosts | { self.bot.user }  # TODO: remove this hack
        return VoteState(self.bot, None, self.notice, hosts, captains, players)


@dataclass(frozen=True)
class VoteState(PugState):
    hosts: FrozenSet[Member]
    captains: FrozenSet[Member]
    players: FrozenSet[Member]

    @property
    def reacts(self):
        return self.host_emojis + self.capt_emojis

    @property
    def host_emojis(self):
        # randomize the emoji order
        # TODO: might be better to save the shuffled list instead of reshuffling every time
        return random.Random(hash(self.hosts)).sample(FLAG_EMOJIS, k=len(self.hosts))

    @property
    def capt_emojis(self):
        return OPTION_EMOJIS[:len(self.captains)]

    def __str__(self):
        # TODO: skip/hide voting when it's not needed
        return (
            f"**PUG voting**\n"
            f"{HOST_EMOJI} - **Vote for a host:**\n"
            + '\n'.join(f'> {e} - {m.name}' for m, e in zip(self.hosts, self.host_emojis)) +" \n"
            f"{CAPT_EMOJI} - **Vote for captains:**\n"
            + '\n'.join(f'> {e} - {m.name}' for m, e in zip(self.captains, self.capt_emojis)) + "\n"
        )

    async def next(self, msg: Message):
        assert msg.id == self.msg.id

        host_votes = [utils.get(msg.reactions, emoji=e).count - 1 for e in self.host_emojis]
        capt_votes = [utils.get(msg.reactions, emoji=e).count - 1 for e in self.capt_emojis]

        # wait until we have enough votes
        end_early = (utils.get(msg.reactions, emoji=SKIP_EMOJI) is not None)  # allow owner to end voting early. TODO: check if reacting user is the bot owner
        if not end_early and (sum(host_votes) < MIN_VOTES or sum(capt_votes) < MIN_VOTES):
            return replace(self, msg=msg)

        # find the best host and top two captains
        _, host = max(zip(host_votes, self.hosts), key=get(0))
        (_, red_capt), (_, blu_capt) = sorted(zip(capt_votes, self.captains), key=get(0))[-2:]

        # start team-picking
        # testusers = set(map(msg.channel.guild.get_member, [723040252683616277, 723041156208001057, 723314051811115119, 723314517806678097, 723333772099190794, 723342828243255310, 723343877817499689])); self = replace(self, players=self.players | testusers)  # TODO: remove this hack
        return PickState.make(self.bot, None, self.notify, host, red_capt, blu_capt, self.players)


PICKED_EMOJI = '\N{NO ENTRY SIGN}'
PICK_ORDER = [0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 0]

@dataclass(frozen=True)
class PickState(PugState):
    host: Member
    players: FrozenSet[Member]
    teams: Tuple[Tuple[Member, ...], Tuple[Member, ...]]
    pick_idx: int

    @classmethod
    def make(cls, bot, msg, notify, host, red_capt, blu_capt, players):
        return cls(bot, msg, notify,
                   host=host,
                   players=players - { red_capt, blu_capt },
                   teams=((red_capt,), (blu_capt,)),
                   pick_idx=0)


    def __str__(self):
        is_picked = [any(p in t for t in self.teams) for p in self.players]
        emojis    = [PICKED_EMOJI if picked else r for picked, r in zip(is_picked, self.reacts)]
        names     = [f'~~{p.name}~~' if picked else p.name for picked, p in zip(is_picked, self.players)]
        captain   = self.teams[PICK_ORDER[self.pick_idx]][0]
        return (
            f"**PUG team picking: {CAPT_EMOJI} {captain.mention} - Pick a player**\n"
            f"**Host:** {self.host.name}\n"
            f"**Teams:**\n"
            f"> **RED**: {strjoin(m.name for m in self.teams[0])}\n"
            f"> **BLU**: {strjoin(m.name for m in self.teams[1])}\n"
            f"**Players:**\n" + '\n'.join(f'> {e} - {n}' for e, n in zip(emojis, names)) + "\n"
        )

    @property
    def reacts(self):
        return OPTION_EMOJIS[:len(self.players)]

    async def next(self, msg: Message):
        assert msg.id == self.msg.id

        picking_team = PICK_ORDER[self.pick_idx]
        team_size = min(MAX_PLAYERS, len(self.players) + 2) // 2
        assert len(self.teams[picking_team]) < team_size

        captain = self.teams[picking_team][0]
        for emoji, player in zip(self.reacts, self.players):
            if (react := utils.get(msg.reactions, emoji=emoji)) and captain in await react.users().flatten():
                teams = (*self.teams[:picking_team],
                         (*self.teams[picking_team], player),
                         *self.teams[picking_team+1:])

                await react.clear()

                pick_idx = self.pick_idx + 1
                # if the next team to pick is already full, skip their pick
                while pick_idx < len(PICK_ORDER) and len(teams[PICK_ORDER[pick_idx]]) >= team_size:
                    pick_idx += 1

                if pick_idx < len(PICK_ORDER):
                    return replace(self, msg=msg, pick_idx=pick_idx, teams=teams)

                # all teams are full, start the pug
                return RunningState(self.bot, None, self.notify, self.host, teams[0], teams[1])

        return replace(self, msg=msg)


@dataclass(frozen=True)
class RunningState(PugState):
    reacts: ClassVar[List[str]] = [DONE_EMOJI]

    host: Member
    red: Tuple[Member, ...]
    blu: Tuple[Member, ...]

    @classmethod
    def make_random(cls, bot, msg, notice, hosts, players):
        host = random.choice(list(hosts))
        team_size = min(MAX_PLAYERS, len(players)) // 2
        players = tuple(random.sample(players, k=team_size * 2))
        red, blu = players[:team_size], players[team_size:]
        return cls(bot, msg, notice, host, red, blu)

    def __str__(self):
        return (
            f"**PUG started**\n"
            f"**PUG info:**\n"
            f"> **Host**: {self.host.mention}\n"
            f"> **RED**:  {strjoin(u.mention for u in self.red)}\n"
            f"> **BLU**:  {strjoin(u.mention for u in self.blu)}\n"
            f"React with {DONE_EMOJI} once the PUG is done.\n"
        )

    async def next(self, msg: Message):
        assert msg.id == self.msg.id

        done_react = utils.get(msg.reactions, emoji=DONE_EMOJI)
        if done_react.count > 2 or await bot_owner_reacted(self.bot, done_react):
            await msg.channel.send(content=(
                f"**PUG finished**\n"
                f"**PUG info:**\n"
                f"> **Host**: {self.host.name}\n"
                f"> **RED**: {strjoin(u.name for u in self.red)}\n"
                f"> **BLU**: {strjoin(u.name for u in self.blu)}\n"
            ))

            # start the next pug
            return IdleState(self.bot, msg=None, notice=self.notice)
        return replace(self, msg=msg)


def strjoin(it, sep=', '):
    return sep.join(map(str, it))


async def bot_owner_reacted(bot, reaction):
    """ returns whether the bot owner has reacted with 'reaction' """
    return await reaction.users().find(bot.is_owner) is not None
