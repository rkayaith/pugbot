import asyncio
from dataclasses import dataclass, replace
import random
from typing import FrozenSet

from discord import Embed, TextChannel

from src.bot_stuff import mention
from src.rewrite import update_state
from src.states import State, StoppedState, React, EMPTY, DONE_EMOJI

def setup(bot):
    from src.mem import chan_ctxs

    @bot.command()
    async def dance(ctx, channel: TextChannel = None):
        if channel is None:
            channel = ctx.channel

        chan_ctx = chan_ctxs[channel.id]
        if not isinstance(chan_ctx.state, StoppedState):
            await ctx.send(f"I'm already running in {channel.mention}.")
            return

        await update_state(bot, chan_ctx, channel.id, lambda c: DanceState.make(c.state, admin_ids=c.state.admin_ids | { ctx.author.id }))

        if channel != ctx.channel:
            await ctx.send(f"Started dancing in {channel.mention}.")
        print(f"Started dancing in {channel.mention}.")


@dataclass(frozen=True)
class DanceState(State):
    dance_idx: int = 0
    users: FrozenSet[int] = frozenset()

    @property
    def messages(state):
        title = ' '.join(str(state.bot.get_user(u)) for u in state.users)
        mentions = ' '.join(map(mention, state.users))
        description = (('\n' + mentions + EMPTY.join([' ']*5))
                       .join(DANCE[state.dance_idx].split('\n')))
        description = description[:2048]  # embed description has a character limit
        return {
            'main': Embed(
                title=title,
                description=description,
                colour = random.randint(0, 0xffffff)
            )
        }

    async def on_update(state):
        if state.reacts & { (u, DONE_EMOJI) for u in state.admin_ids }:
            yield StoppedState.make(state)
            return

        users = state.users | { r.user_id for r in state.reacts }
        yield (state := replace(state, users=users))
        while True:
            await asyncio.sleep(1)
            next_idx = (state.dance_idx + 1) % len(DANCE)
            yield (state := replace(state, dance_idx=next_idx))
DANCE = [
    """

    ⠀⠀⠀⣀⣶⣀
    ⠀⠀⠀⠒⣛⣭
    ⠀⠀⠀⣀⠿⣿⣶
    ⠀⣤⣿⠤⣭⣿⣿
    ⣤⣿⣿⣿⠛⣿⣿⠀⣀
    ⠀⣀⠤⣿⣿⣶⣤⣒⣛
    ⠉⠀⣀⣿⣿⣿⣿⣭⠉
    ⠀⠀⣭⣿⣿⠿⠿⣿
    ⠀⣶⣿⣿⠛⠀⣿⣿
    ⣤⣿⣿⠉⠤⣿⣿⠿
    ⣿⣿⠛⠀⠿⣿⣿
    ⣿⣿⣤⠀⣿⣿⠿
    ⠀⣿⣿⣶⠀⣿⣿⣶
    ⠀⠀⠛⣿⠀⠿⣿⣿
    ⠀⠀⠀⣉⣿⠀⣿⣿
    ⠀⠶⣶⠿⠛⠀⠉⣿
    ⠀⠀⠀⠀⠀⠀⣀⣿
    ⠀⠀⠀⠀⠀⣶⣿⠿
    """,
    """



    ⠀⠀⠀⠀⠀⠀⠀⠀⣤⣿⣿⠶⠀⠀⣀⣀
    ⠀⠀⠀⠀⠀⠀⣀⣀⣤⣤⣶⣿⣿⣿⣿⣿⣿
    ⠀⠀⣀⣶⣤⣤⠿⠶⠿⠿⠿⣿⣿⣿⣉⣿⣿
    ⠿⣉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠛⣤⣿⣿⣿⣀
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⣿⣿⣿⣿⣶⣤
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣤⣿⣿⣿⣿⠿⣛⣿
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⠛⣿⣿⣿⣿
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣶⣿⣿⠿⠀⣿⣿⣿⠛
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⠀⠀⣿⣿⣿
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠿⠿⣿⠀⠀⣿⣶
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⠛⠀⠀⣿⣿⣶
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⣿⣿⠤
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠿⣿
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣀
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣶⣿
    """,
    """



    ⠀⠿⣿⣿⣀
    ⠀⠉⣿⣿⣀
    ⠀⠀⠛⣿⣭⣀⣀⣤
    ⠀⠀⣿⣿⣿⣿⣿⠛⠿⣶⣀
    ⠀⣿⣿⣿⣿⣿⣿⠀⠀⠀⣉⣶
    ⠀⠀⠉⣿⣿⣿⣿⣀⠀⠀⣿⠉
    ⠀⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿
    ⠀⣀⣿⣿⣿⣿⣿⣿⣿⣿⠿
    ⠀⣿⣿⣿⠿⠉⣿⣿⣿⣿
    ⠀⣿⣿⠿⠀⠀⣿⣿⣿⣿
    ⣶⣿⣿⠀⠀⠀⠀⣿⣿⣿
    ⠛⣿⣿⣀⠀⠀⠀⣿⣿⣿⣿⣶⣀
    ⠀⣿⣿⠉⠀⠀⠀⠉⠉⠉⠛⠛⠿⣿⣶
    ⠀⠀⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣿
    ⠀⠀⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠉⠉
    ⣀⣶⣿⠛
    """,
    """



    ⠀⠀⠀⠀⠀⠀⠀⣀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⣿⣿⣿⣤⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣤⣤⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠉⣿⣿⣿⣶⣿⣿⣿⣶⣶⣤⣶⣶⠶⠛⠉⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⣤⣿⠿⣿⣿⣿⣿⣿⠀⠀⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠛⣿⣤⣤⣀⣤⠿⠉⠀⠉⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠉⠉⠉⠉⠉⠀⠀⠀⠀⠉⣿⣿⣿⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣶⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⣿⣿⠛⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣛⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⣶⣿⣿⠛⠿⣿⣿⣿⣶⣤⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⣿⠛⠉⠀⠀⠀⠛⠿⣿⣿⣶⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⣿⣀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠿⣶⣤⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠛⠿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣿⣿⠿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠛⠉⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    """,
    """



    ⠀⠀⠀⠀⠀⠀⣤⣶⣶
    ⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⣀⣀
    ⠀⠀⠀⠀⠀⣀⣶⣿⣿⣿⣿⣿⣿
    ⣤⣶⣀⠿⠶⣿⣿⣿⠿⣿⣿⣿⣿
    ⠉⠿⣿⣿⠿⠛⠉⠀⣿⣿⣿⣿⣿
    ⠀⠀⠉⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⣤⣤
    ⠀⠀⠀⠀⠀⠀⠀⣤⣶⣿⣿⣿⣿⣿⣿
    ⠀⠀⠀⠀⠀⣀⣿⣿⣿⣿⣿⠿⣿⣿⣿⣿
    ⠀⠀⠀⠀⣀⣿⣿⣿⠿⠉⠀⠀⣿⣿⣿⣿
    ⠀⠀⠀⠀⣿⣿⠿⠉⠀⠀⠀⠀⠿⣿⣿⠛
    ⠀⠀⠀⠀⠛⣿⣿⣀⠀⠀⠀⠀⠀⣿⣿⣀
    ⠀⠀⠀⠀⠀⣿⣿⣿⠀⠀⠀⠀⠀⠿⣿⣿
    ⠀⠀⠀⠀⠀⠉⣿⣿⠀⠀⠀⠀⠀⠀⠉⣿
    ⠀⠀⠀⠀⠀⠀⠀⣿⠀⠀⠀⠀⠀⠀⣀⣿
    ⠀⠀⠀⠀⠀⠀⣀⣿⣿
    ⠀⠀⠀⠀⠤⣿⠿⠿⠿
    """,
    """
    ⠀⠀⠀⠀⣀
    ⠀⠀⣶⣿⠿⠀⠀⠀⣀⠀⣤⣤
    ⠀⣶⣿⠀⠀⠀⠀⣿⣿⣿⠛⠛⠿⣤⣀
    ⣶⣿⣤⣤⣤⣤⣤⣿⣿⣿⣀⣤⣶⣭⣿⣶⣀
    ⠉⠉⠉⠛⠛⠿⣿⣿⣿⣿⣿⣿⣿⠛⠛⠿⠿
    ⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⣿⠿
    ⠀⠀⠀⠀⠀⠀⠀⠿⣿⣿⣿⣿
    ⠀⠀⠀⠀⠀⠀⠀⠀⣭⣿⣿⣿⣿⣿
    ⠀⠀⠀⠀⠀⠀⠀⣤⣿⣿⣿⣿⣿⣿
    ⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⣿⣿⠿
    ⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⣿⠿
    ⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⣿
    ⠀⠀⠀⠀⠀⠀⠀⠉⣿⣿⣿⣿
    ⠀⠀⠀⠀⠀⠀⠀⠀⠉⣿⣿⣿⣿
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⣿⠛⠿⣿⣤
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣿⠀⠀⠀⣿⣿⣤
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⠀⠀⠀⣶⣿⠛⠉
    ⠀⠀⠀⠀⠀⠀⠀⠀⣤⣿⣿⠀⠀⠉
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉
    """,
    """



    ⠀⠀⠀⠀⠀⠀⣶⣿⣶
    ⠀⠀⠀⣤⣤⣤⣿⣿⣿
    ⠀⠀⣶⣿⣿⣿⣿⣿⣿⣿⣶
    ⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿
    ⠀⠀⣿⣉⣿⣿⣿⣿⣉⠉⣿⣶
    ⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⠿⣿
    ⠀⣤⣿⣿⣿⣿⣿⣿⣿⠿⠀⣿⣶
    ⣤⣿⠿⣿⣿⣿⣿⣿⠿⠀⠀⣿⣿⣤
    ⠉⠉⠀⣿⣿⣿⣿⣿⠀⠀⠒⠛⠿⠿⠿
    ⠀⠀⠀⠉⣿⣿⣿⠀⠀⠀⠀⠀⠀⠉
    ⠀⠀⠀⣿⣿⣿⣿⣿⣶
    ⠀⠀⠀⠀⣿⠉⠿⣿⣿
    ⠀⠀⠀⠀⣿⣤⠀⠛⣿⣿
    ⠀⠀⠀⠀⣶⣿⠀⠀⠀⣿⣶
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⣭⣿⣿
    ⠀⠀⠀⠀⠀⠀⠀⠀⣤⣿⣿⠉
    """,
    """



    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⣤⣶
    ⠀⠀⠀⠀⠀⣀⣀⠀⣶⣿⣿⠶
    ⣶⣿⠿⣿⣿⣿⣿⣿⣿⣿⣿⣤⣤
    ⠀⠉⠶⣶⣀⣿⣿⣿⣿⣿⣿⣿⠿⣿⣤⣀
    ⠀⠀⠀⣿⣿⠿⠉⣿⣿⣿⣿⣭⠀⠶⠿⠿
    ⠀⠀⠛⠛⠿⠀⠀⣿⣿⣿⣉⠿⣿⠶
    ⠀⠀⠀⠀⠀⣤⣶⣿⣿⣿⣿⣿
    ⠀⠀⠀⠀⠀⣿⣿⣿⣿⣿⣿⣿⠒
    ⠀⠀⠀⠀⣀⣿⣿⣿⣿⣿⣿⣿
    ⠀⠀⠀⠀⠀⣿⣿⣿⠛⣭⣭⠉
    ⠀⠀⠀⠀⠀⣿⣿⣭⣤⣿⠛
    ⠀⠀⠀⠀⠀⠛⠿⣿⣿⣿⣭
    ⠀⠀⠀⠀⠀⠀⠀⣿⣿⠉⠛⠿⣶⣤
    ⠀⠀⠀⠀⠀⠀⣀⣿⠀⠀⣶⣶⠿⠿⠿
    ⠀⠀⠀⠀⠀⠀⣿⠛
    ⠀⠀⠀⠀⠀⠀⣭⣶
    """,
    """

    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⣤⣤
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿
    ⠀⠀⣶⠀⠀⣀⣤⣶⣤⣉⣿⣿⣤⣀
    ⠤⣤⣿⣤⣿⠿⠿⣿⣿⣿⣿⣿⣿⣿⣿⣀
    ⠀⠛⠿⠀⠀⠀⠀⠉⣿⣿⣿⣿⣿⠉⠛⠿⣿⣤
    ⠀⠀⠀⠀⠀⠀⠀⠀⠿⣿⣿⣿⠛⠀⠀⠀⣶⠿
    ⠀⠀⠀⠀⠀⠀⠀⠀⣀⣿⣿⣿⣿⣤⠀⣿⠿
    ⠀⠀⠀⠀⠀⠀⠀⣶⣿⣿⣿⣿⣿⣿⣿⣿
    ⠀⠀⠀⠀⠀⠀⠀⠿⣿⣿⣿⣿⣿⠿⠉⠉
    ⠀⠀⠀⠀⠀⠀⠀⠉⣿⣿⣿⣿⠿
    ⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⠉
    ⠀⠀⠀⠀⠀⠀⠀⠀⣛⣿⣭⣶⣀
    ⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⣿
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⠉⠛⣿
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⠀⠀⣿⣿
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣉⠀⣶⠿
    ⠀⠀⠀⠀⠀⠀⠀⠀⣶⣿⠿
    ⠀⠀⠀⠀⠀⠀⠀⠛⠿⠛
    """,
    """


    ⠀⠀⠀⣶⣿⣶
    ⠀⠀⠀⣿⣿⣿⣀
    ⠀⣀⣿⣿⣿⣿⣿⣿
    ⣶⣿⠛⣭⣿⣿⣿⣿
    ⠛⠛⠛⣿⣿⣿⣿⠿
    ⠀⠀⠀⠀⣿⣿⣿
    ⠀⠀⣀⣭⣿⣿⣿⣿⣀
    ⠀⠤⣿⣿⣿⣿⣿⣿⠉
    ⠀⣿⣿⣿⣿⣿⣿⠉
    ⣿⣿⣿⣿⣿⣿
    ⣿⣿⣶⣿⣿
    ⠉⠛⣿⣿⣶⣤
    ⠀⠀⠉⠿⣿⣿⣤
    ⠀⠀⣀⣤⣿⣿⣿
    ⠀⠒⠿⠛⠉⠿⣿
    ⠀⠀⠀⠀⠀⣀⣿⣿
    ⠀⠀⠀⠀⣶⠿⠿⠛
    """
]
