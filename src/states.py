from collections import defaultdict
from dataclasses import dataclass, fields, replace
from functools import cached_property
from operator import attrgetter as get
import random
from typing import Tuple, FrozenSet, NamedTuple, Union

from discord import Embed, Emoji

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

EMPTY = '\u200B'
SKIP_EMOJI = '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}'
WAIT_EMOJI = '\N{DOUBLE VERTICAL BAR}\uFE0F'
HOST_EMOJI = '\N{GLOBE WITH MERIDIANS}'
CAPT_EMOJI = '\N{BILLED CAP}'
#DONE_EMOJI = '\N{WHITE HEAVY CHECK MARK}'

LAPTOP_MAN = '\N{MAN}\N{ZERO WIDTH JOINER}\N{PERSONAL COMPUTER}'

@dataclass(frozen=True)
class IdleState(State):

    async def on_update(state):
        # add default reacts
        reacts = state.reacts | { React(state.bot.user_id, e) for e in (HOST_EMOJI, CAPT_EMOJI) }
        yield (state := replace(state, reacts=reacts))

        # pug admins can use reacts to wait/skip this state
        if (state.enough_ppl and not state.admin_wait) or state.admin_skip:
            # go to voting state
            state = replace(state, history=(*state.history, state.messages))
            yield VoteState.make(state, state.host_ids, state.capt_ids, state.player_ids)

    @cached_property
    def messages(self):
        # for the player emoji, pick a random one that someone's reacted with,
        # with a default if there's no player reacts yet
        choices = { r.emoji for r in self.reacts } - { HOST_EMOJI, CAPT_EMOJI , SKIP_EMOJI, WAIT_EMOJI }
        player_emoji = random.choice(list(choices) or [LAPTOP_MAN])

        if self.admin_wait:
            # TODO: use get_member() so we can use display_name instead of name.
            #       for that we need to get the channel id from somewhere...
            # TODO: not sure get_user() will even work... might have to call bot._connection.set_user(u._as_minimal_user_json()) somewhere
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
    host_ids: FrozenSet[int]
    capt_ids: FrozenSet[int]
    player_ids: FrozenSet[int]

    @property
    def messages(self):
        return { 'main': 'bruh' }
