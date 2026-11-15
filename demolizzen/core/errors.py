"""Errors the bot reports to Discord users."""

# Discord
from discord.ext import commands


class CogDisabled(commands.CheckFailure):
    """The command belongs to a cog that is switched off in this guild.

    This derives from ``discord.ext.commands.CheckFailure`` on purpose: the bot's
    error handler shows that one to the user, while it silently drops
    ``discord.errors.CheckFailure``.
    """

    def __init__(self, key: str):
        self.key = key
        super().__init__("This module is disabled on this server.")
