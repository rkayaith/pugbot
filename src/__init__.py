import importlib
import os
import sys

import discord
import discord.ext.commands

PRELOADED_MODULES = frozenset(sys.modules.values())
print(f"preloaded {len(PRELOADED_MODULES)} modules")
