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
        self.persisted_views = self.bot.loop.create_task(self.load_persistent_tickets())
        self.channel_update_worker.start()

    def cog_unload(self):
        self.channel_update_worker.cancel()
        self.persisted_views.cancel()

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

    async def load_persistent_tickets(self):
        await self.bot.wait_until_ready()
        logger.debug("Loading persistent tickets...")
        tickets = [ticket async for ticket in GuildTicket.objects.all()]
        logger.info(f"Loaded {len(tickets)} persistent tickets.")
        for ticket in tickets:
            guild = discord.utils.get(self.bot.guilds, id=ticket.guild_id)
            opener = discord.utils.get(guild.members, id=ticket.user_id)
            channel = discord.utils.get(opener.guild.channels, id=ticket.channel_id)
            # Ensure not adding views for deleted channels
            if not channel:
                logger.info(
                    f"Channel {ticket.channel_id} not found, deleting ticket {ticket.ticket_number}"
                )
                await ticket.adelete()
                continue
            view = TicketControlView(channel, opener, ticket.ticket_number)
            logger.debug(
                f"Adding view for ticket {ticket.ticket_number} in channel {ticket.channel_id}, user {ticket.user_id}"
            )
            self.bot.add_view(view)

    def queue_channel_update(self, channel: discord.TextChannel, topic: str, name: str):
        """Queue a channel update to be processed by the worker."""
        self.queue.append((channel, topic, name))

    ticket = SlashCommandGroup(
        "ticket", "Ticket System", contexts=[discord.InteractionContextType.guild]
    )

    @ticket.command(name="open", help="Open a help ticket")
    @commands.guild_only()
    async def open_ticket(
        self,
        ctx: discord.ApplicationContext,
    ):
        """Ticket system to contact Server staff."""
        try:
            guild_settings = await GuildTicketSettings.objects.aget(
                guild_id=ctx.guild.id,
            )
            category_id = guild_settings.category_id
            ticket_number = guild_settings.ticket_count
            category = discord.utils.get(ctx.guild.categories, id=category_id)
        except GuildTicketSettings.DoesNotExist:
            try:
                category = await ctx.guild.create_category(
                    name="Ticket System", reason="Help Ticket Category"
                )
                archived_category = await ctx.guild.create_category(
                    name="Archived Tickets", reason="Help Ticket Archive Category"
                )
                guild_settings = await GuildTicketSettings.objects.acreate(
                    guild_id=ctx.guild.id,
                    category_id=category.id,
                    archive_category_id=archived_category.id,
                    ticket_count=1,
                )
            except discord.Forbidden:
                return await ctx.respond(
                    content="I do not have permission to create the help ticket category. Please inform the admins.",
                )

        # Channel-Name generieren
        channel_name_ticket = (
            f"ticket{guild_settings.ticket_count}-unclaimed-{ctx.user.name}"
        )
        # Channel erstellen mit Sichtbarkeit nur für User und ggf. Staff
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        }

        # Set Permnissions for Channel

        # Staff Members
        staff_role_ids = getattr(guild_settings, "roles", None)
        if staff_role_ids:
            for staff_role_id in staff_role_ids:
                role = ctx.guild.get_role(staff_role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True, read_message_history=True
                    )
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
                category=category,
                overwrites=overwrites,
            )
            guild_settings.ticket_count += 1
            await guild_settings.asave()
        except discord.Forbidden:
            return await ctx.respond(
                content="I do not have permission to create ticket channels. Please inform the admins.",
            )

        ticket_view = TicketControlView(ticket_channel, ctx.user, ticket_number)
        await ticket_channel.send(
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
    async def set_help_category(
        self,
        ctx: discord.ApplicationContext,
        category: discord.CategoryChannel,
    ):
        """Set the help category for tickets."""
        guild_settings, created = await GuildTicketSettings.objects.aget_or_create(
            guild_id=ctx.guild.id,
            defaults={"category_id": category.id, "ticket_count": 1},
        )
        if not created:
            guild_settings.category_id = category.id
            await guild_settings.asave()
        await ctx.respond(
            content=f"Help Category set to {category.mention}.",
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
        guild_settings, created = await GuildTicketSettings.objects.aget_or_create(
            guild_id=ctx.guild.id,
            defaults={"roles": role_ids, "ticket_count": 1},
        )

        if not created:
            guild_settings.roles = role_ids
            await guild_settings.asave()
        mentions = ", ".join(role.mention for role in roles)
        await ctx.respond(content=f"Staff roles set to: {mentions}", ephemeral=True)
