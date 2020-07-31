from collections import defaultdict, Counter
from dataclasses import dataclass, fields, replace
from itertools import chain
from functools import cached_property
from operator import attrgetter as get
import random
from typing import Tuple, FrozenSet, NamedTuple, Union

from discord import Embed, Emoji
from flag import flag

from .bot_stuff import Bot, mention
from .utils import create_index, fset, user_set


class React(NamedTuple):
    user_id: int
    emoji: Union[Emoji, str]


FROZEN = True
@dataclass(frozen=FROZEN)
class State:
    bot: Bot
    admin_ids: Tuple[int]
    reacts: FrozenSet[React]
    history: Tuple[Union[str, Embed]]

    @classmethod
    def make(cls, from_state, *args, **kwargs):
        base_fields = [kwargs.pop(f.name, getattr(from_state, f.name))
                       for f in fields(State)]
        return cls(*base_fields, *args, **kwargs)

    async def on_update(state):
        yield state


@dataclass(frozen=FROZEN)
class StoppedState(State):
    @property
    def messages(state):
        return { **dict(enumerate(state.history)) }


MIN_HOSTS = 1
MIN_CAPTS = 2
MIN_VOTES = 12
MAX_PLAYERS = 12
MIN_PLAYERS = 8

EMPTY = '\u200B'  # zero-width space
SKIP_EMOJI   = '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}'
WAIT_EMOJI   = '\N{DOUBLE VERTICAL BAR}\uFE0F'
HOST_EMOJI   = '\N{GLOBE WITH MERIDIANS}'
CAPT_EMOJI   = '\N{BILLED CAP}'
PLAYER_EMOJI = '\N{MAN}\N{ZERO WIDTH JOINER}\N{PERSONAL COMPUTER}'

FLAG_EMOJIS   = ['\U0001F3F3\U0000FE0F\U0000200D\U0001F308', '\U0001F3F4\U0000200D\U00002620\U0000FE0F'] + list(map(flag, ['in', 'cn', 'br', 'ae', 'kp', 'im', 'eu', 'il', 'mk', 'mx', 'jp']))
OPTION_EMOJIS = [f'{i}\N{COMBINING ENCLOSING KEYCAP}' for i in range(10)] + [chr(i) for i in range(ord('\N{REGIONAL INDICATOR SYMBOL LETTER A}'), ord('\N{REGIONAL INDICATOR SYMBOL LETTER A}') + 26)]
DONE_EMOJI = '\N{WHITE HEAVY CHECK MARK}'

@dataclass(frozen=True)
class IdleState(State):
    async def on_update(state):
        # add default reacts
        bot_reacts = { React(state.bot.user_id, e) for e in (HOST_EMOJI, CAPT_EMOJI) }
        yield (state := replace(state, reacts=state.reacts | bot_reacts))

        # pug admins can use reacts to wait/skip this state
        # TODO: remove admin skipping?
        if (state.enough_ppl and not state.admin_wait) or state.admin_skip:
            # go to voting state
            state = replace(state, history=(*state.history, state.messages['idle']))
            yield VoteState.make(state, state.host_ids, state.capt_ids, state.player_ids)

    @cached_property
    def messages(state):
        # for the player emoji, pick a random one that someone's reacted with,
        # with a default if there's no player reacts yet
        choices = { r.emoji for r in state.reacts } - { HOST_EMOJI, CAPT_EMOJI , SKIP_EMOJI, WAIT_EMOJI }
        player_emoji = random.choice(list(choices) or [PLAYER_EMOJI])

        if state.admin_wait:
            # TODO: use get_member() so we can use display_name.
            #       for that we need to get the channel id from somewhere...
            pauser_names = (str(state.bot.get_user(r.user_id).name) for r in state.admin_wait)
            footer = f"PUG paused by {', '.join(pauser_names)}. Waiting for them to unpause..."
        elif state.enough_ppl or state.admin_skip:
            footer = 'PUG starting now...'
        else:
            # TODO: add info about using SKIP_EMOJI
            admin_names = (str(state.bot.get_user(user_id)) for user_id in state.admin_ids)
            footer = (
                f"The PUG will start when there's at least {MIN_HOSTS} host, {MIN_CAPTS} captains, and {MIN_PLAYERS} players.\n"
                f"{' and '.join(admin_names)} can stop the PUG from starting by reacting with {WAIT_EMOJI}"
            )
        plural = lambda num, noun: f"{num} {noun}" + ('s' if num != 1 else '')
        return {
            'idle': (Embed(
                title='**Waiting for players**',
                colour=0xffac33,
                description=(
                    f"React with {HOST_EMOJI} if you can host.\n"
                    f"React with {CAPT_EMOJI} to captain.\n"
                    f"React with anything else to play.\n"
                ))
                .add_field(name=f"{HOST_EMOJI}  {plural(len(state.host_ids), 'host')}",
                           value=EMPTY + ' '.join(map(mention, state.host_ids)))
                .add_field(name=f"{CAPT_EMOJI}  {plural(len(state.capt_ids), 'captain')}",
                           value=EMPTY + ' '.join(map(mention, state.capt_ids)))
                .add_field(inline=False,
                           name=f"{player_emoji}  {plural(len(state.player_ids), 'player')}",
                           value=EMPTY + ' '.join(map(mention, state.player_ids)))
                .set_footer(text=footer)
            ),
            **dict(enumerate(state.history))
        }

    @cached_property
    def reacts_by_emoji(state):
        reacts_without_bot = (r for r in state.reacts if r.user_id != state.bot.user_id)
        return defaultdict(set, create_index(reacts_without_bot, get('emoji')))

    @cached_property
    def admin_wait(state):
        return state.reacts & { React(a_id, WAIT_EMOJI) for a_id in state.admin_ids }

    @cached_property
    def admin_skip(state):
        return state.reacts & { React(a_id, SKIP_EMOJI) for a_id in state.admin_ids }
        return state.reacts & r(state.admin_ids, SKIP_EMOJI)

    @cached_property
    def host_ids(state):
        return user_set(state.reacts_by_emoji[HOST_EMOJI])

    @cached_property
    def capt_ids(state):
        return user_set(state.reacts_by_emoji[CAPT_EMOJI])

    @cached_property
    def player_ids(state):
        return (user_set(state.reacts - state.reacts_by_emoji[HOST_EMOJI]
                                      - state.admin_wait - state.admin_skip)
                                      - { state.bot.user_id })
    @property
    def enough_ppl(state):
        return (len(state.host_ids) >= MIN_HOSTS and
                len(state.capt_ids) >= MIN_CAPTS and
                len(state.player_ids) >= MIN_PLAYERS)


@dataclass(frozen=FROZEN)
class VoteState(State):
    host_ids: Tuple[int]
    capt_ids: Tuple[int]
    player_ids: FrozenSet[int]

    @classmethod
    def make(cls, from_state, host_ids, capt_ids, player_ids):
        # if there aren't enough hosts or captains, add all the players and let
        # the people vote
        if len(host_ids) < 1:
            host_ids = set(host_ids) | set(player_ids)
        if len(capt_ids) < 2:
            capt_ids = set(capt_ids) | set(player_ids)

        assert len(host_ids) >= 1 and len(capt_ids) >= 2
        state = super().make(from_state, tuple(host_ids), tuple(capt_ids), fset(player_ids))
        # skip voting if there's nothing to vote on
        if not state.host_voting and not state.capt_voting:
            [host_id] = host_ids
            return PickState.make(state, host_id, capt_ids, player_ids)
        return state

    @property
    def messages(state):
        admin_names = (str(state.bot.get_user(u)) for u in state.admin_ids)
        embed = (Embed(
            title='**PUG voting**',
            colour=0xaa8ed6,
            description='React to vote for a host/captains')
            .set_footer(text=f"{' and '.join(admin_names)} can end this early by reacting with {SKIP_EMOJI}"))

        if state.host_voting:
            embed.add_field(name=f"Vote for a host",
                            value='\n'.join(f"{e} {mention(u)}" for e, u
                                            in zip(state.host_emojis, state.host_ids)))
        if state.capt_voting:
            embed.add_field(name=f"Vote for captains",
                            value='\n'.join(f"{e} {mention(u)}" for e, u
                                            in zip(state.capt_emojis, state.capt_ids)))

        return {
            'vote': embed,
            **dict(enumerate(state.history))
        }


    async def on_update(state):
        yield state

        # add default reacts. we add the host and capt reacts seperately, so
        # that the host reacts show up first.
        # TODO: these will cause unnecessary message edits, even though only
        #       the reacts are changing. 
        for emojis, voting in [(state.host_emojis, state.host_voting),
                               (state.capt_emojis, state.capt_voting)]:
            bot_reacts = { React(state.bot.user_id, e) for e in emojis }
            if voting and not bot_reacts <= state.reacts and len(bot_reacts) < 10:
                yield (state := replace(state, reacts=state.reacts | bot_reacts))

        def count_votes(emojis, ids):
            emoji_to_id = dict(zip(emojis, ids))
            votes = Counter({ i: 0 for i in ids })
            votes.update(emoji_to_id.get(r.emoji, 'other')
                         for r in state.reacts if r.user_id != state.bot.user_id)
            del votes['other']
            return votes
        host_votes = count_votes(state.host_emojis, state.host_ids)
        capt_votes = count_votes(state.capt_emojis, state.capt_ids)

        # admins can end this state early
        admin_skip = state.reacts & { React(a_id, SKIP_EMOJI) for a_id in state.admin_ids }
        if admin_skip or ((sum(host_votes.values()) >= MIN_VOTES or not state.host_voting) and
                          (sum(capt_votes.values()) >= MIN_VOTES or not state.capt_voting)):
            # start team picking
            [(host_id, _)] = host_votes.most_common(1)
            [(blu_capt, _), (red_capt, _)] = capt_votes.most_common(2)  # "worse" captain gets first pick (red)
            yield PickState.make(state, host_id, (red_capt, blu_capt), state.player_ids - { red_capt, blu_capt })

    @property
    def host_voting(state):
        return len(state.host_ids) != 1

    @property
    def capt_voting(state):
        return len(state.capt_ids) != 2

    @cached_property
    def host_emojis(state):
        # pick random emojis to use. the RNG is seeded based on the host ids so
        # that the emojis chosen are stable.
        return sorted(random.Random(hash(state.host_ids))
                            .sample(FLAG_EMOJIS, k=len(state.host_ids)))

    @property
    def capt_emojis(state):
        return OPTION_EMOJIS[:len(state.capt_ids)]


PICKED_EMOJI = '\N{NO ENTRY SIGN}'
PICKED_EMOJI = '\N{BLACK SMALL SQUARE}'
PICK_ORDER = [0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 0]
RED_EMOJI = '\N{LARGE RED SQUARE}'
BLU_EMOJI = '\N{LARGE BLUE SQUARE}'

@dataclass(frozen=FROZEN)
class PickState(State):
    host_id: int
    capt_ids: Tuple[int]
    player_ids: FrozenSet[int]
    team_ids: Tuple[Tuple[int, ...], Tuple[int, ...]] = (tuple(), tuple())
    pick_idx: int = 0

    @classmethod
    def make(cls, from_state, host_id, capt_ids, player_ids):
        assert len(capt_ids) == 2
        return super().make(from_state, host_id, tuple(capt_ids), fset(player_ids))

    @property
    def messages(state):
        teams_full = (len(state.red_ids) == len(state.blu_ids) == state.team_size)
        if teams_full:
            description = "Teams picked. PUG starting..."
            ping = {}
        else:
            picking_capt = state.capt_ids[PICK_ORDER[state.pick_idx]]
            description = (
                f"React to pick a player.\n"
                f"Current pick: {mention(picking_capt)}"
            )
            # TODO: include the number of players to pick
            ping = { ('ping', state.pick_idx): f"{mention(picking_capt)} - pick some players" }

        player_to_emoji = dict(zip(state.player_ids, OPTION_EMOJIS))
        def format_player(player_id):
            if player_id in state.unpicked_ids:
                return f"{player_to_emoji[player_id]} {mention(player_id)}"
            return f"{PICKED_EMOJI} ~~{mention(player_id)}~~"

        if teams_full:
            colour = 0x99aab5
        elif PICK_ORDER[state.pick_idx] == 0:
            colour = 0xdd2e44  # red
        else:
            colour = 0x55acee  # blu

        return {
            'pick': (Embed(
                title=f"**{state.team_size}v{state.team_size} PUG team picking**",
                colour=colour,
                description=(
                    description
                ))
                .add_field(name=f"{HOST_EMOJI} Host {HOST_EMOJI}",
                           value=mention(state.host_id),
                           inline=False)
                .add_field(name=f"{CAPT_EMOJI} Captains {CAPT_EMOJI}",
                           value=' '.join(map(mention, state.capt_ids)),
                           inline=False)
                .add_field(name=f"Players",
                           value='\n'.join(map(format_player, state.player_ids)))
                .add_field(name=f"{RED_EMOJI} RED {RED_EMOJI}",
                           value=EMPTY + '\n'.join(map(mention, state.red_ids)))
                .add_field(name=f"{BLU_EMOJI} BLU {BLU_EMOJI}",
                           value=EMPTY + '\n'.join(map(mention, state.blu_ids)))
            ),
            **ping,
            **dict(enumerate(state.history))
        }

    async def on_update(state):
        # if the teams are full, start the pug
        if len(state.red_ids) == len(state.blu_ids) == state.team_size:
            yield RunningState.make(state, state.host_id, state.red_ids, state.blu_ids)
            return

        # add bot reacts
        pick_emojis = [e for e, u in zip(OPTION_EMOJIS, state.player_ids)
                         if u in state.unpicked_ids]
        reacts = state.reacts | { React(state.bot.user_id, e) for e in pick_emojis }

        # check if the current captain picked anyone
        picking_team = PICK_ORDER[state.pick_idx]
        capt_picks = reacts & { (state.capt_ids[picking_team], e)
                                for e, u in zip(OPTION_EMOJIS, state.player_ids)
                                if u in state.unpicked_ids }
        if not capt_picks:
            yield (state := replace(state, reacts=reacts))
            print("no pick")
            return

        # add the picked player to the team
        _, picked_emoji = next(iter(capt_picks))
        picked_id = next(u for u, e in zip(state.player_ids, OPTION_EMOJIS)
                           if e == picked_emoji)
        print(f"team {picking_team} picked {picked_id}")
        team_ids = list(state.team_ids)  # modifying nested tuples... bleh
        team_ids[picking_team] = (*team_ids[picking_team], picked_id)
        team_ids = tuple(team_ids)

        # delete reacts for the picked player
        reacts = { r for r in reacts if r.emoji != picked_emoji }

        # increment pick index.
        # if the next team to pick is already full, skip their pick.
        pick_idx = state.pick_idx + 1
        while (pick_idx < len(PICK_ORDER) and
               len(team_ids[PICK_ORDER[pick_idx]]) >= state.team_size - 1):
            pick_idx += 1

        yield (state := replace(state, reacts=reacts, pick_idx=pick_idx, team_ids=team_ids))

    @property
    def red_ids(state):
        return (state.capt_ids[0], *state.team_ids[0])

    @property
    def blu_ids(state):
        return (state.capt_ids[1], *state.team_ids[1])

    @property
    def team_size(state):
        return min(MAX_PLAYERS, len(state.capt_ids) + len(state.player_ids)) // 2

    @cached_property
    def unpicked_ids(state):
        return state.player_ids - fset(state.team_ids[0] + state.team_ids[1])


@dataclass(frozen=FROZEN)
class RunningState(State):
    host_id: int
    red_ids: Tuple[int, ...]
    blu_ids: Tuple[int, ...]

    @cached_property
    def messages(state):
        score = (random.Random(hash(state.red_ids + state.blu_ids))
                       .choice(['5 - 0', '0 - 5']))
        return {
            'running': (
                Embed(
                    title=f"**{len(state.red_ids)}v{len(state.blu_ids)} PUG started**",
                    colour=0x77b255,
                    description=(
                        f"Fetching MMR data...\n"
                        f"Calculating odds...\n"
                        f"Predicted result: {score}"
                ))
                .add_field(name=f"{RED_EMOJI} RED {RED_EMOJI}",
                           value=EMPTY + '\n'.join(map(mention, state.red_ids)))
                .add_field(name=f"{BLU_EMOJI} BLU {BLU_EMOJI}",
                           value=EMPTY + '\n'.join(map(mention, state.blu_ids)))
                .add_field(name='Host', value=(
                           f"{mention(state.host_id)}\n\n"
                           f"**Captains**\n"
                           f"{mention(state.red_ids[0])}\n{mention(state.blu_ids[0])}"))
            ),
            ('running', 'notify'): 'PUG started: ' + ' '.join(map(mention, chain([state.host_id], state.red_ids, state.blu_ids))),
            **dict(enumerate(state.history))
        }

    async def on_update(state):
        yield state
        # stop the bot
        yield StoppedState.make(state, history=(*state.history,
                                                state.messages['running'],
                                                state.messages['running', 'notify']))
