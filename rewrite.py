import asyncio
import contextlib
from dataclasses import dataclass, replace
from typing import Any, Dict, NamedTuple, FrozenSet, Union

from discord import Emoji

class React(NamedTuple):
    user_id: int
    emoji: Union[Emoji, str]

class ChanCtx:
    lock: asyncio.Lock
    msg_id_map: Dict[Any, int]
    reactions: FrozenSet[React]

@dataclass(frozen=True)
class State:
    reacts: FrozenSet[React]
    async def on_update(self, reacts: FrozenSet[React]):
        yield replace(self, reacts=reacts)

async def update_reacts(bot, ctx, chan_id, msg_id, update_fn):
    async with ctx.lock:
        # we only track reacts to the main message
        # TODO: track reacts to all messages?
        if msg_id != msg_id_map[main]:
            return
        ctx.reacts = (reacts := frozenset(update_fn(ctx.reacts)))
        prev_state = ctx.state

    async for next_state in prev_state.on_update(bot, reacts=reacts):
        async with ctx.lock:
            # if someone changed the state while we were getting the next one,
            # so we can stop here
            if ctx.state is not prev_state:
                return

            # apply changes to discord
            tasks = update_discord(bot, ctx, chan_id, prev_state, next_state)
            await asyncio.gather(tasks)
        prev_state = next_state
