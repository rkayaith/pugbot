import asyncio
from itertools import repeat

fset = frozenset

async def alist(async_gen):
    # like list() but async
    return [e async for e in async_gen]

def first(iterable):
    return next(iter(iterable), None)

def create_index(iterable, index_fn):
    """
    Return an index of 'iterable' using 'index_fn', i.e.
        index[i] = { the set of elements with index_fn(elem) == i }
    """
    index = {}
    for elem in iterable:
        index.setdefault(index_fn(elem), set()).add(elem)
    return index

def invert_dict(d):
    """
    Returns the inverse of dictionary 'd', i.e.
        inv[val] = { the set of keys in 'd' that map to 'val' }
    """
    vals = iter(d.values())
    return create_index(d, lambda _: next(vals))

def as_fut(obj):
    fut = asyncio.Future()
    fut.set_result(obj)
    return fut

def retval_as_fut(coro):
    """
    Returns a future that holds the eventual result of 'coro', and a new
    coroutine that should be awaited instead of 'coro'.
    """
    fut = asyncio.Future()
    async def wrapped_coro():
        fut.set_result(await coro)
    return fut, wrapped_coro()

def user_set(reacts):
    return fset(r.user_id for r in reacts)

def rs(user_ids, emojis):
    if isinstance(user_ids, int):
        user_ids = repeat(user_ids)
    if isinstance(user_ids, str):
        emojis = repeat(emojis)
    return fset(map(React, user_ids, emojis))




