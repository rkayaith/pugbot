import os
import sys

from discord.ext import commands

BOT_TOKEN  = os.environ['BOT_TOKEN']
MODULES    = ['src.bot_stuff', 'src.states', 'src.utils']  # TODO: use sys.modules to generate this?
EXTENSIONS = ['src.rewrite', 'src.eggs']


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
    print()

    # invalidate the module cache so that modules will be re-executed when the
    # extensions are loaded.
    for path in MODULES:
        sys.modules.pop(path, None)

    for ext in EXTENSIONS:
        try:
            bot.reload_extension(ext)
        except commands.ExtensionNotLoaded:
            bot.load_extension(ext)

    print('Reloaded modules:  ' + ', '.join(MODULES))
    print('Loaded extensions: ' + ', '.join(EXTENSIONS))
