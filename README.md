# Contributing
Follow [these instructions](https://discordpy.readthedocs.io/en/latest/discord.html) to create a bot and invite it to a server you'll use for testing. Then start a local instance:
```bash
# install dependencies
$ pipenv sync
# create an environment file
$ echo "BOT_TOKEN=<YOUR_BOT_TOKEN>" > .env
# start the bot
$ pipenv run python main.py
```
Use the `@pugbot reload` command in Discord to hot-reload when you've made changes instead of restarting the bot.
