# Standard Library
import asyncio
import logging

# Discord
import discord
from discord import Embed, SlashCommandGroup
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

THREAD_EMBED = Embed(
    title="Private Channel Guide",
    description=(
        "This Channel is private between you and the staff team.\n"
        "Use the buttons below to manage your ticket.\n"
        "Please be patient while waiting for a response from the staff."
    ),
)

logger = logging.getLogger(__name__)


class TicketSystem(commands.Cog):
    """Help Ticket Cog Things"""

    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.title = "Ticket System"
        self.alias = "ticket"
        self.channel_update_worker.start()

    ticket = SlashCommandGroup(
        "ticket", "Ticket System", contexts=[discord.InteractionContextType.guild]
    )

    def cog_unload(self):
        self.channel_update_worker.cancel()

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

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        guild_settings, created = await GuildTicketSettings.objects.aget_or_create(
            guild_id=ctx.guild.id,
        )
        ctx.guild_settings = guild_settings
        logger.debug(f"GuildSettings loaded for {ctx.guild}.")
        if created:
            logger.info(f"Created new GuildSettings for {ctx.guild}.")

    @ticket.command(name="open", help="Open a help ticket")
    @commands.guild_only()
    async def open_ticket(
        self,
        ctx: discord.ApplicationContext,
    ):
        """Ticket system to contact Server staff."""
        if not ctx.guild_settings.category_id:
            return await ctx.respond(
                content="No help category is set for this server. Please inform the admins to set a help category using `/ticket set` command.",
                ephemeral=True,
            )

        ticket_number = ctx.guild_settings.ticket_count
        category_channel = discord.utils.get(
            ctx.guild.categories, id=ctx.guild_settings.category_id
        )

        if not category_channel:
            return await ctx.respond(
                content="The configured help category does not exist anymore. Please inform the admins to set a new help category using `/ticket set` command.",
                ephemeral=True,
            )

        # Channel-Name generieren
        channel_name_ticket = f"ticket{ticket_number}-unclaimed-{ctx.user.name}"
        # Channel erstellen mit Sichtbarkeit nur für User und ggf. Staff
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        }

        # Set Permnissions for Channel
        # Staff Members
        staff_role_ids = getattr(ctx.guild_settings, "roles", None)
        if staff_role_ids:
            for staff_role_id in staff_role_ids:
                role = ctx.guild.get_role(staff_role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True, read_message_history=True
                    )
            # Staff-Rollen erwähnen
            staff_mentions = ""
            staff_roles = [
                ctx.guild.get_role(rid)
                for rid in staff_role_ids
                if ctx.guild.get_role(rid)
            ]
            staff_mentions = " ".join(role.mention for role in staff_roles)
        else:
            return await ctx.respond(
                content="No staff roles are set for this server. Please inform the admins to set at least one staff role using `/ticket staff` command.",
                ephemeral=True,
            )
        # Bot
        overwrites[ctx.guild.me] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        )
        # Ticket-Ersteller
        overwrites[ctx.user] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            mention_everyone=False,  # block @everyone/@here
        )

        # Create Channel
        try:
            ticket_channel = await ctx.guild.create_text_channel(
                name=channel_name_ticket,
                topic=f"Type: 📩 **OPEN TICKET** - Created by: {ctx.user.mention}",
                category=category_channel,
                overwrites=overwrites,
            )
            ctx.guild_settings.ticket_count += 1
            await ctx.guild_settings.asave()
        except discord.Forbidden:
            return await ctx.respond(
                content="I do not have permission to create ticket channels. Please inform the admins.",
            )

        ticket_view = TicketControlView(ticket_channel, ctx.user, ticket_number)
        await ticket_channel.send(
            content=staff_mentions if staff_mentions else None,
            embed=THREAD_EMBED,
            view=ticket_view,
        )
        # Create GuildTicket entry
        await GuildTicket.objects.acreate(
            guild_id=ctx.guild.id,
            ticket_number=ticket_number,
            channel_id=ticket_channel.id,
            user_id=ctx.user.id,
        )
        return await ctx.respond(
            content=f"Check the ticket channel created! {ticket_channel.mention}!",
            ephemeral=True,
        )

    @ticket.command(name="set", help="Set the Category channel for tickets")
    @commands.guild_only()
    @checks.is_admin()
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

    @ticket.command(name="staff", help="Add staff roles for ticket management")
    @commands.guild_only()
    @checks.is_admin()
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
