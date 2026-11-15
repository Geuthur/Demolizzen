# Standard Library
import logging

# Discord
import discord
from discord.ext import commands, tasks

# Demolizzen
from demolizzen.cogs.panel._view import PanelView
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog
from demolizzen.services import cog_settings, guilds

logger = logging.getLogger(__name__)

# How often switches made outside the bot (the web panel) are looked for.
WATCH_SECONDS = 60


class Panel(BaseCog):
    """Manage which modules are active on your server."""

    key = "panel"

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
        self.title = "Panel"
        self.alias = "panel"
        self.watch_modules.start()

    def cog_unload(self):
        self.watch_modules.cancel()

    @tasks.loop(seconds=WATCH_SECONDS)
    async def watch_modules(self):
        """Show or hide slash commands after a module was switched elsewhere.

        The web panel runs in another process and only writes to the database.
        Looking costs one query; Discord is asked only for servers that changed.
        """
        try:
            await self.bot.command_scope.refresh()
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Following the module switches failed")

    @watch_modules.before_loop
    async def before_watch_modules(self):
        await self.bot.wait_until_ready()

    @commands.slash_command(
        name="panel",
        description="Manage the modules of this server.",
        contexts=[discord.InteractionContextType.guild],
        default_member_permissions=discord.Permissions(manage_guild=True),
    )
    @checks.is_admin()
    async def panel(self, ctx: discord.ApplicationContext):
        """Show the server panel."""
        await guilds.ensure_guild(ctx.guild.id, ctx.guild.name)
        states = await cog_settings.get_states(ctx.guild.id)
        view = PanelView(ctx.guild.id, ctx.guild.name, ctx.author.id, states)
        await ctx.respond(embed=view.embed(), view=view, ephemeral=True)
