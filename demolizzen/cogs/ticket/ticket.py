# Standard Library
import asyncio
import logging
import re

# Discord
import discord
from discord import SlashCommandGroup
from discord.ext import commands, tasks

# Demolizzen
from demolizzen.cogs.ticket._actions import CATEGORY_LIMIT, TicketActions
from demolizzen.cogs.ticket._renamer import ChannelRenamer
from demolizzen.cogs.ticket._views import (
    OpenTicketView,
    TicketControlView,
    build_status_embed,
)
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog
from demolizzen.services import cog_settings, tickets
from demolizzen.services.tickets import Action

logger = logging.getLogger(__name__)

# Button ids of tickets created before the rebuild: "<action>:<guild>:<number>".
LEGACY_BUTTON_ID = re.compile(r"^(claim|close|reopen|delete):\d+:\d+$")


class TicketSystem(BaseCog):
    """Private help tickets between members and the staff team."""

    key = "ticket"

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
        self.title = "Ticket System"
        self.alias = "ticket"
        self.renamer = ChannelRenamer()
        self.actions = TicketActions(bot, self.renamer, self.is_enabled)
        self._views_registered = False
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass  # loaded before the bot runs; on_ready registers the views
        else:
            self._register_views()
        self.maintenance.start()

    def _register_views(self) -> None:
        """Register the button handlers once.

        The buttons carry fixed ids, so these two views serve every ticket
        message; nothing has to be loaded from the database at startup.
        py-cord views can only be created while the event loop is running.
        """
        if self._views_registered:
            return
        self.bot.add_view(TicketControlView(handler=self.actions.handle))
        self.bot.add_view(OpenTicketView(handler=self.actions.start_open))
        self._views_registered = True

    @commands.Cog.listener()
    async def on_ready(self):
        self._register_views()

    ticket = SlashCommandGroup(
        name="ticket",
        description="Ticket System",
        contexts=[discord.InteractionContextType.guild],
    )

    def cog_unload(self):
        self.maintenance.cancel()
        self.renamer.cancel_all()

    @ticket.command(name="open", description="Open a help ticket")
    @commands.guild_only()
    async def open_ticket(self, ctx: discord.ApplicationContext):
        """Open a private ticket to contact the server staff."""
        await self.actions.start_open(ctx.interaction)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Serve the buttons of tickets created before the rebuild."""
        if interaction.type is not discord.InteractionType.component:
            return
        custom_id = (interaction.data or {}).get("custom_id") or ""
        match = LEGACY_BUTTON_ID.match(custom_id)
        if match is None:
            return
        # Handling the click replaces the message's buttons with the current ones.
        await self.actions.handle(interaction, Action(match.group(1)))

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        """Forget the ticket of a channel that was deleted by hand."""
        if await tickets.remove_by_channel(channel.id):
            logger.info("Removed ticket of deleted channel %s", channel.id)

    @tasks.loop(hours=1)
    async def maintenance(self):
        """Hourly: archive old closed tickets and repair channel names."""
        try:
            await self.run_maintenance()
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Ticket maintenance failed")

    @maintenance.before_loop
    async def before_maintenance(self):
        await self.bot.wait_until_ready()

    async def run_maintenance(self) -> None:
        """Archive due tickets, drop tickets without a channel, sync channel names."""
        guild_ids = await cog_settings.enabled_guild_ids(
            self.key, [guild.id for guild in self.bot.guilds]
        )
        for ticket in await tickets.due_for_archive():
            if ticket.guild_id in guild_ids:
                await self._archive(ticket)

        for ticket in await tickets.active_tickets(guild_ids):
            guild = self.bot.get_guild(ticket.guild_id)
            if guild is None:
                continue
            channel = guild.get_channel(ticket.channel_id)
            if channel is None:
                await tickets.remove_by_channel(ticket.channel_id)
                logger.info(
                    "Removed ticket #%s of guild %s without a channel",
                    ticket.ticket_number,
                    ticket.guild_id,
                )
                continue
            owner = guild.get_member(ticket.user_id)
            self.renamer.request(
                channel,
                tickets.channel_name(
                    ticket.ticket_number,
                    self.actions._owner_name(channel, owner),
                    ticket.is_closed,
                ),
            )

    async def _archive(self, ticket) -> None:
        """Move a closed ticket to the archive category if there is room."""
        guild = self.bot.get_guild(ticket.guild_id)
        channel = guild.get_channel(ticket.channel_id) if guild else None
        if channel is None:
            return
        settings = await tickets.get_settings(ticket.guild_id)
        archive = guild.get_channel(settings.archive_category_id)
        if (
            not isinstance(archive, discord.CategoryChannel)
            or len(archive.channels) >= CATEGORY_LIMIT
        ):
            return
        try:
            await channel.edit(category=archive, reason="Ticket archived")
        except discord.HTTPException:
            logger.exception("Could not archive ticket channel %s", channel.id)
            return
        await tickets.mark_archived(ticket.pk)
        ticket.is_archived = True
        if ticket.control_message_id:
            try:
                await channel.get_partial_message(ticket.control_message_id).edit(
                    embed=build_status_embed(ticket), view=TicketControlView(ticket)
                )
            except discord.HTTPException:
                logger.warning(
                    "Could not update status message of ticket #%s of guild %s",
                    ticket.ticket_number,
                    ticket.guild_id,
                )
