import os
from discord.ext import commands

BOT_TOKEN = os.environ['BOT_TOKEN']
EXT_PATH = 'pug'

bot = commands.Bot(command_prefix=commands.when_mentioned)

@bot.listen()
async def on_ready():
    print(f'We have logged in as {bot.user}')

@bot.command(aliases=['r'], hidden=True)
@commands.is_owner()
async def reload(ctx):
    bot.reload_extension(EXT_PATH)
    await ctx.send('\N{OK hand sign}')

bot.load_extension(EXT_PATH)
bot.run(BOT_TOKEN)
