import importlib
import os
import sys

from discord.ext import commands

PRELOADED_MODULES = frozenset(sys.modules.values())

BOT_TOKEN  = os.environ['BOT_TOKEN']
# MODULES    = ['bot_stuff', 'states', 'utils']
EXTENSIONS = ['rewrite']


if __name__ == '__main__':
    from bot_stuff import Bot
    bot = Bot(command_prefix=commands.when_mentioned)
    bot.load_extension('main')
    bot.run(BOT_TOKEN)
    print(f"done with {bot.user}")


def setup(bot):
    @bot.listen()
    async def on_ready():
        print(f'We have logged in as {bot.user}')

    @bot.command(aliases=['r'], hidden=True)
    @commands.is_owner()
    async def reload(ctx):
        await ctx.send('Reloading.')
        bot.reload_extension('main')

    print(f"preloaded: {PRELOADED_MODULES}")
    modules_to_reload = set(sys.modules.values()) - PRELOADED_MODULES
    for module in modules_to_reload:
        importlib.reload(module)
    print('Reloaded modules: ' + ', '.join(m.__name__ for m in modules_to_reload))

    for ext in EXTENSIONS:
        try:
            bot.reload_extension(ext)
        except commands.ExtensionNotLoaded:
            bot.load_extension(ext)
    print(f"Loaded extensions: {', '.join(EXTENSIONS)}")
