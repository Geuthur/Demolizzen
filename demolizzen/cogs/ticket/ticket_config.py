# Standard Library
import logging

# Discord
import discord
from discord import SlashCommandGroup
from discord.commands import option
from discord.ext import commands

# Demolizzen
from demolizzen.cogs.ticket._staffview import RoleSelectView
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog
from demolizzen.models.guild import GuildTicketSettings

logger = logging.getLogger(__name__)


class TicketSystemConfig(BaseCog):
    """Ticket Configuration Cog"""

    key = "ticket"

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
        self.title = "Ticket System Configuration"
        self.alias = "ticket_config"

    ticket_config = SlashCommandGroup(
        name="ticket_config",
        description="Ticket Configuration",
        contexts=[discord.InteractionContextType.guild],
        default_member_permissions=discord.Permissions(manage_guild=True),
    )

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        guild_settings, created = await GuildTicketSettings.objects.aget_or_create(
            guild_id=ctx.guild.id,
        )
        ctx.guild_settings = guild_settings
        logger.debug(f"GuildSettings loaded for {ctx.guild}.")
        if created:
            logger.info(f"Created new GuildSettings for {ctx.guild}.")

    @ticket_config.command(name="set", help="Set the category channel for tickets")
    @commands.guild_only()
    @checks.is_guild_manager()
    @option(
        "category", description="The category to set as help category", required=True
    )
    @option(
        "category_type",
        description="Which category type to set",
        choices=["Help", "Archive"],
        required=True,
    )
    async def set_help_category(
        self,
        ctx: discord.ApplicationContext,
        category: discord.CategoryChannel,
        category_type: str,
    ):
        """Set the help category for tickets."""
        if category_type == "Help":
            ctx.guild_settings.category_id = category.id
        elif category_type == "Archive":
            ctx.guild_settings.archive_category_id = category.id
        else:
            return await ctx.respond(
                content="Invalid category type. Please choose either 'Help' or 'Archive'.",
                ephemeral=True,
            )

        await ctx.guild_settings.asave()
        await ctx.respond(
            content=f"{category_type} Category set to {category.mention}.",
            ephemeral=True,
        )

    @ticket_config.command(
        name="staff",
        help="Add staff roles for ticket management this roles will be mentioned on ticket creation",
    )
    @commands.guild_only()
    @checks.is_guild_manager()
    async def add_staff_role(self, ctx: discord.ApplicationContext):
        """Add one or more staff roles for ticket management via Select-View."""
        view = RoleSelectView(guild=ctx.guild)
        await ctx.respond("Please select the staff roles:", view=view, ephemeral=True)
        await view.wait()
        roles = view.selected_roles

        if not roles:
            await ctx.respond("No roles selected.", ephemeral=True)
            return

        role_ids = [role.id for role in roles]

        # Create or update GuildTicketSettings
        ctx.guild_settings.roles = role_ids
        await ctx.guild_settings.asave()
        mentions = ", ".join(role.mention for role in roles)
        await ctx.respond(content=f"Staff roles set to: {mentions}", ephemeral=True)
