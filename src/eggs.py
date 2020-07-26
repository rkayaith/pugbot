import asyncio
from dataclasses import dataclass, replace
import random
from typing import FrozenSet

from discord import Embed, TextChannel, User

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
            await ctx.send(f"I'm already running in {channel.mention}")
            return

        await update_state(bot, chan_ctx, channel.id, lambda c: DanceState.make(c.state, admin_ids=c.state.admin_ids | { ctx.author.id }))

        if channel != ctx.channel:
            await ctx.send(f"Started dancing in {channel.mention}")
        print(f"Started dancing in {channel.mention}")

    @bot.command()
    async def wall(ctx, channel: TextChannel = None):
        if channel is None:
            channel = ctx.channel

        chan_ctx = chan_ctxs[channel.id]
        if not isinstance(chan_ctx.state, StoppedState):
            await ctx.send(f"I'm already running in {channel.mention}")
            return

        await update_state(bot, chan_ctx, channel.id, lambda c: WallState.make(c.state, admin_ids=c.state.admin_ids | { ctx.author.id }))

        if channel != ctx.channel:
            await ctx.send(f"Started wall in {channel.mention}")
        print(f"Started wall in {channel.mention}")


    @bot.command()
    async def dm(ctx, user: User):
        await ctx.message.author.send(content=PASTA, tts=True)
        print(f"dm'd {ctx.message.author}")


ALPHABET = [chr(i) for i in range(ord('\N{REGIONAL INDICATOR SYMBOL LETTER A}'), ord('\N{REGIONAL INDICATOR SYMBOL LETTER A}') + 26)]
SPACE_EMOJI = '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}'
BACKSPACE_EMOJI = '\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}'
NEWLINE_EMOJI = '\N{LEFTWARDS ARROW WITH HOOK}'
@dataclass(frozen=True)
class WallState(State):
    text: str = EMPTY

    @property
    def messages(state):
        text = state.text[-2000:] + '\n'
        title, description = text.split('\n', 1)
        return {
            'main': Embed(
                title=title.strip() or ' ',
                description=description.strip() or ' ',
                colour = random.Random(hash(state.text)).randint(0, 0xffffff)
            ).set_footer(text=(
                f"react with a letter to add it to this message.\n"
                f"{NEWLINE_EMOJI} to start a new line, "
                f"{SPACE_EMOJI} for space, "
                f"{BACKSPACE_EMOJI} for backspace."
            ))
        }

    async def on_update(state):
        reacts = state.reacts | { React(state.bot.user_id, e) for e in (SPACE_EMOJI, BACKSPACE_EMOJI, NEWLINE_EMOJI) }
        text = state.text
        for r in reacts:
            if r.user_id == state.bot.user_id:
                continue

            if r.emoji in ALPHABET:
                text = text + chr(ord('a') + ALPHABET.index(r.emoji))
                reacts = reacts - { r }
            if r.emoji == SPACE_EMOJI:
                text = text + ' '
                reacts = reacts - { r }
            if r.emoji == BACKSPACE_EMOJI:
                text = EMPTY + text[:-1]
                reacts = reacts - { r }
            if r.emoji == NEWLINE_EMOJI:
                text = text + '\n'
                reacts = reacts - { r }

            print(f"{state.bot.get_user(r.user_id)}: {text}")
        yield replace(state, reacts=reacts, text=text)


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
            ).set_footer(text='React to this message to stop the dance.')
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
            if next_idx == 0:
                await asyncio.sleep(1)
            yield (state := replace(state, dance_idx=next_idx))

PASTA = \
"""
92% of people who see this will not
have the guts to repost it. When Goku
died in the explosion Cell tied to destroy Earth with, he did it for you and me. If you're not ashamed to love Goku, post this as your status and show everyone. Thank you, Goku. I lifted up my arms for the spirit bomb every time you asked for my energy.
"""

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
