# Discord
import discord
from discord.ext import commands

# Demolizzen
from demolizzen.cogs.panel._view import PanelView
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog
from demolizzen.services import cog_settings, guilds


class Panel(BaseCog):
    """Manage which modules are active on your server."""

    key = "panel"

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
        self.title = "Panel"
        self.alias = "panel"

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
