from collections import defaultdict, Counter
from dataclasses import dataclass, fields, replace
from functools import cached_property
from operator import attrgetter as get
import random
from typing import Tuple, FrozenSet, NamedTuple, Union

from discord import Embed, Emoji
from flag import flag

from .bot_stuff import Bot, mention
from .utils import create_index, fset


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

    async def on_update(self):
        yield self


@dataclass(frozen=FROZEN)
class StoppedState(State):
    @property
    def messages(self):
        return {}


# TODO: move this somewhere?
def user_set(reacts):
    return fset(r.user_id for r in reacts)

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

FLAG_EMOJIS   = ['\U0001F3F3\U0000FE0F\U0000200D\U0001F308', '\U0001F3F4\U0000200D\U00002620\U0000FE0F'] + list(map(flag, ['in', 'cn', 'br', 'ae', 'kp', 'im']))
OPTION_EMOJIS = [f'{i}\N{COMBINING ENCLOSING KEYCAP}' for i in range(10)] + [chr(i) for i in range(ord('\N{REGIONAL INDICATOR SYMBOL LETTER A}'), ord('\N{REGIONAL INDICATOR SYMBOL LETTER A}') + 26)]
#DONE_EMOJI = '\N{WHITE HEAVY CHECK MARK}'

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
            state = replace(state, history=(*state.history, state.messages))
            yield VoteState.make(state, state.host_ids, state.capt_ids, state.player_ids)

    @cached_property
    def messages(self):
        # for the player emoji, pick a random one that someone's reacted with,
        # with a default if there's no player reacts yet
        choices = { r.emoji for r in self.reacts } - { HOST_EMOJI, CAPT_EMOJI , SKIP_EMOJI, WAIT_EMOJI }
        player_emoji = random.choice(list(choices) or [PLAYER_EMOJI])

        if self.admin_wait:
            # TODO: use get_member() so we can use display_name.
            #       for that we need to get the channel id from somewhere...
            pauser_names = (str(self.bot.get_user(r.user_id).name) for r in self.admin_wait)
            footer = f"PUG paused by {', '.join(pauser_names)}. Waiting for them to unpause..."
        elif self.enough_ppl or self.admin_skip:
            footer = 'PUG starting now...'
        else:
            admin_names = (str(self.bot.get_user(user_id)) for user_id in self.admin_ids)
            footer = (
                f"The PUG will start when there's at least {MIN_HOSTS} host, {MIN_CAPTS} captains, and {MIN_PLAYERS} players.\n"
                f"{' and '.join(admin_names)} can stop the PUG from starting by reacting with {WAIT_EMOJI}"
            )
        return {
            'main': (Embed(
                title='**Waiting for players**',
                colour=0xf5d442,
                description=(
                    f"React with {HOST_EMOJI} if you can host.\n"
                    f"React with {CAPT_EMOJI} to captain.\n"
                    f"React with anything else to play.\n"
                ))
                .add_field(name=f"{HOST_EMOJI}  {len(self.host_ids)} hosts",
                           value=EMPTY + ' '.join(map(mention, self.host_ids)))
                .add_field(name=f"{CAPT_EMOJI}  {len(self.capt_ids)} captains",
                           value=EMPTY + ' '.join(map(mention, self.capt_ids)))
                .add_field(inline=False,
                           name=f"{player_emoji}  {len(self.player_ids)} players",
                           value=EMPTY + ' '.join(map(mention, self.player_ids)))
                .set_footer(text=footer)
            ),
            **dict(enumerate(self.history))
        }

    @cached_property
    def reacts_by_emoji(self):
        reacts_without_bot = (r for r in self.reacts if r.user_id != self.bot.user_id)
        return defaultdict(set, create_index(reacts_without_bot, get('emoji')))

    @cached_property
    def admin_wait(self):
        return self.reacts & { React(a_id, WAIT_EMOJI) for a_id in self.admin_ids }

    @cached_property
    def admin_skip(self):
        return self.reacts & { React(a_id, SKIP_EMOJI) for a_id in self.admin_ids }

    @cached_property
    def host_ids(self):
        return user_set(self.reacts_by_emoji[HOST_EMOJI])

    @cached_property
    def capt_ids(self):
        return user_set(self.reacts_by_emoji[CAPT_EMOJI])

    @cached_property
    def player_ids(self):
        return (user_set(self.reacts - self.reacts_by_emoji[HOST_EMOJI]
                                     - self.admin_wait - self.admin_skip)
                                     - { self.bot.user_id })
    @property
    def enough_ppl(self):
        return (len(self.host_ids) >= MIN_HOSTS and
                len(self.capt_ids) >= MIN_CAPTS and
                len(self.player_ids) >= MIN_PLAYERS)


@dataclass(frozen=FROZEN)
class VoteState(State):
    host_ids: Tuple[int]
    capt_ids: Tuple[int]
    player_ids: Tuple[int]

    @classmethod
    def make(cls, from_state, host_ids, capt_ids, player_ids):
        assert len(host_ids) >= 1 and len(capt_ids) >= 2
        state = super().make(from_state, tuple(host_ids), tuple(capt_ids), tuple(player_ids))
        # skip voting if there's nothing to vote on
        if not state.host_voting and not state.capt_voting:
            [host_id] = host_ids
            return PickState.make(state, host_id, capt_ids, player_ids)
        return state

    @property
    def messages(self):
        admin_names = (str(self.bot.get_user(u)) for u in self.admin_ids)
        embed = (Embed(
            title='**PUG voting**',
            colour=0xf5d442,
            description='React to vote for a host/captains')
            .set_footer(text=f"{' and '.join(admin_names)} can end this early by reacting with {SKIP_EMOJI}"))

        if self.host_voting:
            embed.add_field(name=f"Vote for a host",
                            value='\n'.join(f"{e} {mention(u)}" for e, u
                                            in zip(self.host_emojis, self.host_ids)))
        if self.capt_voting:
            embed.add_field(name=f"Vote for captains",
                            value='\n'.join(f"{e} {mention(u)}" for e, u
                                            in zip(self.capt_emojis, self.capt_ids)))

        return {
            'main': embed,
            **dict(enumerate(self.history))
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
            if voting and not bot_reacts <= state.reacts:
                yield (state := replace(state, reacts=state.reacts | bot_reacts))

        # TODO: TEST: remove bot's reacts before counting
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
            yield PickState.make(state, host_id, (red_capt, blu_capt), state.player_ids)

    @property
    def host_voting(self):
        return len(self.host_ids) != 1

    @property
    def capt_voting(self):
        return len(self.capt_ids) != 2

    @cached_property
    def host_emojis(self):
        # pick random emojis to use. the RNG is seeded based on the host ids so
        # that the emojis chosen are stable.
        return sorted(random.Random(hash(self.host_ids))
                            .sample(FLAG_EMOJIS, k=len(self.host_ids)))

    @property
    def capt_emojis(self):
        return OPTION_EMOJIS[:len(self.capt_ids)]


@dataclass(frozen=FROZEN)
class PickState(State):
    host_id: int
    capt_ids: Tuple[int]
    player_ids: Tuple[int]

    @property
    def messages(self):
        return { 'main': 'bruh' }

