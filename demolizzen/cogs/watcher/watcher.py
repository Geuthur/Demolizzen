# Discord
from discord.ext import commands

# Demolizzen
from demolizzen.core.bot import Demolizzen


class Watcher(commands.Cog):
    """Monitor and manage server events and activities."""

    def __init__(self, bot: Demolizzen):
        self.bot = bot
