# Discord
import discord

# Demolizzen
from demolizzen.cogs.commands import _base, _economy, _help
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog
from demolizzen.services import bank, guilds


class Commands(
    _base.CommandsBase, _help.CommandsHelp, _economy.CommandsEconomy, BaseCog
):
    """A list of commands that can help you."""

    key = "commands"

    def __init__(self, bot: Demolizzen, *args, **kwargs):
        super().__init__(bot, *args, **kwargs)
        self.bot = bot
        self.title = "Commands"
        self.alias = "commands"

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        # Members need no registration: profile and bank account are created on demand.
        await guilds.ensure_guild(ctx.guild.id, ctx.guild.name)
        await bank.ensure_account(ctx.guild.id, ctx.author.id, ctx.author.display_name)
