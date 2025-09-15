# Standard Library
import asyncio
import logging

# Discord
import discord
from discord import SlashCommandGroup
from discord.commands import option
from discord.ext import commands, tasks

# Django
from django.utils import timezone

# Demolizzen
from demolizzen.cogs.ticket._staffview import RoleSelectView
from demolizzen.cogs.ticket._ticketview import TicketControlView
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen
from demolizzen.models.guild import (
    GuildTicket,
    GuildTicketSettings,
    GuildTicketTask,
)

logger = logging.getLogger(__name__)


class TicketSystemConfig(commands.Cog):
    """Ticket Configuration Cog"""

    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.title = "Ticket System Configuration"
        self.alias = "ticket_config"
        self.channel_update_worker.start()

    ticket_config = SlashCommandGroup(
        name="ticket_config",
        description="Ticket Configuration",
        contexts=[discord.InteractionContextType.guild],
        default_member_permissions=discord.Permissions(manage_guild=True),
    )

    def cog_unload(self):
        self.channel_update_worker.cancel()

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        guild_settings, created = await GuildTicketSettings.objects.aget_or_create(
            guild_id=ctx.guild.id,
        )
        ctx.guild_settings = guild_settings
        logger.debug(f"GuildSettings loaded for {ctx.guild}.")
        if created:
            logger.info(f"Created new GuildSettings for {ctx.guild}.")

    @tasks.loop(seconds=30)
    async def channel_update_worker(self):
        """Background task to process queued channel updates in parallel with timeout."""
        c_tasks = [
            ticket_task
            async for ticket_task in GuildTicketTask.objects.all().select_related(
                "ticket", "ticket__guild"
            )
        ]
        logger.debug(f"Running channel update worker... {len(c_tasks)} tasks found.")
        for task in c_tasks:
            try:
                guild = discord.utils.get(
                    self.bot.guilds, id=task.ticket.guild.guild_id
                )
                channel = discord.utils.get(guild.channels, id=task.ticket.channel_id)
                # Adding Task to queue
                if not task.is_queued:
                    task.is_queued = True
                    await task.asave()
                    self.bot.loop.create_task(
                        asyncio.wait_for(
                            self._process_channel_update(channel, task), timeout=300
                        )
                    )
                    continue
                # Task already being processed - skip
                if task.is_queued and not task.is_outdated:
                    logger.debug(f"{task} is already being processed.")
                    continue
                # Task is queued but outdated - reset one time
                if task.is_queued and task.is_outdated and not task.has_error:
                    logger.warning(f"{task} is outdated, try again.")
                    task.is_queued = False
                    task.has_error = True
                    task.created_at = timezone.now()
                    await task.asave()
                    continue
                # Task is queued, outdated and already had an error - delete task
                if task.is_queued and task.is_outdated and task.has_error:
                    logger.error(f"{task} has already failed once, deleting task.")
                    await task.adelete()
                    continue
                # Unknown state - log error and delete task
                logger.error(f"Unknown state for {task}.")
                await task.adelete()
                continue
            except Exception as e:
                logger.error(f"Error processing ticket task {task}: {e}")

    @channel_update_worker.before_loop
    async def before_channel_update_worker(self):
        """Wait until the bot is ready before starting the worker."""
        await self.bot.wait_until_ready()

    async def _process_channel_update(
        self, channel: discord.TextChannel, task: GuildTicketTask
    ):
        """Process a single channel update task."""
        try:
            if channel.topic != task.topic or channel.name != task.channel_name:
                logger.debug(f"Updating channel {task}")
                kwargs = {}

                if task.topic:
                    kwargs["topic"] = task.topic
                if task.channel_name:
                    kwargs["name"] = task.channel_name

                # Update the channel
                await channel.edit(**kwargs, reason="Ticket channel update task")
                logger.debug(f"Ticket {task} updated successfully.")
                await task.adelete()
            else:
                logger.debug(f"No update needed for channel {channel.id}")
                await task.adelete()
        except Exception as e:
            logger.error(f"Error in channel update worker: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        logger.debug("Loading persistent tickets...")
        tickets = [ticket async for ticket in GuildTicket.objects.all()]
        deleted_views = 0
        added_views = 0

        for ticket in tickets:
            guild = discord.utils.get(self.bot.guilds, id=ticket.guild_id)
            opener = discord.utils.get(guild.members, id=ticket.user_id)
            channel = discord.utils.get(opener.guild.channels, id=ticket.channel_id)
            # Ensure not adding views for deleted channels
            if not channel:
                deleted_views += 1
                await ticket.adelete()
                continue
            view = TicketControlView(channel, opener, ticket.ticket_number)
            added_views += 1
            self.bot.add_view(view)
        logger.info(
            f"Added {added_views} Persistent tickets, deleted missing {deleted_views} tickets."
        )

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
