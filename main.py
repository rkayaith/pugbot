import importlib
import os
import sys

from discord.ext import commands

BOT_TOKEN  = os.environ['BOT_TOKEN']
MODULES    = ['src.states', 'src.utils']  # TODO: use sys.modules to generate this?
EXTENSIONS = ['src.bot_stuff', 'src.rewrite']


# from src import PRELOADED_MODULES
# print(f"i see {len(PRELOADED_MODULES)} preloaded modules")

if __name__ == '__main__':
    from src.bot_stuff import Bot
    bot = Bot(command_prefix=commands.when_mentioned)

    @bot.listen()
    async def on_ready():
        print(f'We have logged in as {bot.user}')

    @bot.command(aliases=['r'], hidden=True)
    @commands.is_owner()
    async def reload(ctx):
        await ctx.send('Reloading.')
        try:
            bot.reload_extension('main')
        except commands.ExtensionNotLoaded:
            bot.load_extension('main')

    bot.load_extension('main')
    bot.run(BOT_TOKEN)
    print(f"done with {bot.user}")


def setup(bot):
    for mod_name in MODULES:
        importlib.reload(importlib.import_module(mod_name))

    for ext in EXTENSIONS:
        try:
            bot.reload_extension(ext)
        except commands.ExtensionNotLoaded:
            bot.load_extension(ext)

    print()
    print('Reloaded modules:  ' + ', '.join(MODULES))
    print('Loaded extensions: ' + ', '.join(EXTENSIONS))
