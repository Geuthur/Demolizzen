# Discord
import discord
from discord.ext import commands

# Demolizzen
from demolizzen import models
from demolizzen.cogs.commands import _base, _economy, _help
from demolizzen.core.bot import Demolizzen
from demolizzen.utils.functions import get_command_mention


class Commands(
    _base.CommandsBase, _help.CommandsHelp, _economy.CommandsEconomy, commands.Cog
):
    """A list of commands that can help you."""

    def __init__(self, bot: Demolizzen, *args, **kwargs):
        super().__init__(bot, *args, **kwargs)
        self.bot = bot
        self.title = "Commands"
        self.alias = "commands"

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        try:
            user = await models.UserProfile.objects.select_related(
                "bank_account", "bags"
            ).aget(user_id=ctx.author.id, guild_id=ctx.guild.id)
            ctx.user_profile = user
            self.bot.logger.debug(f"UserProfile loaded for {ctx.author}.")
        except models.UserProfile.DoesNotExist as exc:
            app_command = get_command_mention(
                bot=self.bot,
                cog="Core",
                slash_command="auth",
                slash_command_group="register",
            )
            raise commands.CheckFailure(
                f"UserProfile does not exist. Please register first. Use {app_command} to register."
            ) from exc
