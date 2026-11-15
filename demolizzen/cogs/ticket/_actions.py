"""Carries ticket actions out in Discord.

Every decision (who may do what, in which state) is taken by
``demolizzen.services.tickets``. This module turns the outcome into Discord
changes: status message, channel permissions, channel name and category.
"""

# Standard Library
import io
import logging
import re

# Discord
import discord

# Demolizzen
from demolizzen.cogs.ticket._renamer import ChannelRenamer
from demolizzen.cogs.ticket._transcript import MAX_MESSAGES, render_transcript
from demolizzen.cogs.ticket._views import (
    DELETE_QUESTION,
    ConfirmDeleteView,
    OpenTicketModal,
    TicketControlView,
    build_status_embed,
)
from demolizzen.models import GuildTicket, GuildTicketSettings
from demolizzen.services import tickets
from demolizzen.services.errors import GuildNotRegistered, TicketError, TicketNotFound
from demolizzen.services.tickets import Action, Actor

logger = logging.getLogger(__name__)

# Discord allows this many channels in one category.
CATEGORY_LIMIT = 50

MODULE_DISABLED = "This module is disabled on this server."
NOT_SET_UP = (
    "The ticket system is not set up yet. "
    "Please ask an admin to configure it with /panel."
)
CATEGORY_GONE = (
    "The configured ticket category no longer exists. "
    "Please ask an admin to set it in /panel."
)
CATEGORY_FULL = (
    "The ticket category is full. "
    "Please ask the staff to close or delete old tickets."
)
STAFF_GONE = (
    "The configured staff roles no longer exist. "
    "Please ask an admin to set them in /panel."
)

_VERBS = {Action.CLAIM: "claimed", Action.CLOSE: "closed", Action.REOPEN: "reopened"}
_TRANSITIONS = {
    Action.CLAIM: tickets.claim,
    Action.CLOSE: tickets.close,
    Action.REOPEN: tickets.reopen,
}
_NAME_PATTERN = re.compile(r"^(?:ticket|closed)-\d+-(.+)$")


class TicketActions:
    """Opens tickets and applies button clicks."""

    def __init__(self, bot, renamer: ChannelRenamer, is_enabled):
        self.bot = bot
        self.renamer = renamer
        self._is_enabled = is_enabled

    # ------------------------------------------------------------------ helpers

    @staticmethod
    async def _reply(interaction: discord.Interaction, text: str) -> None:
        """Tell only the acting user something."""
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)

    async def _module_active(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False
        if await self._is_enabled(interaction.guild.id):
            return True
        await self._reply(interaction, MODULE_DISABLED)
        return False

    @staticmethod
    def actor_for(member, settings: GuildTicketSettings) -> Actor:
        """Describe a guild member in the terms the rights table uses."""
        staff_ids = set(tickets.staff_role_ids(settings))
        is_admin = (
            member.id == member.guild.owner_id or member.guild_permissions.manage_guild
        )
        is_staff = any(role.id in staff_ids for role in getattr(member, "roles", []))
        return Actor(user_id=member.id, is_staff=is_staff, is_admin=is_admin)

    @staticmethod
    def _category(guild, category_id):
        """Return the category, or the message that explains why it is unusable."""
        category = guild.get_channel(category_id) if category_id else None
        if not isinstance(category, discord.CategoryChannel):
            return None, CATEGORY_GONE
        if len(category.channels) >= CATEGORY_LIMIT:
            return None, CATEGORY_FULL
        return category, None

    @staticmethod
    def _owner_name(channel, owner) -> str | None:
        """The name part of the channel name; kept when the owner has left."""
        if owner is not None:
            return owner.name
        match = _NAME_PATTERN.match(channel.name or "")
        return match.group(1) if match else None

    async def _open_requirements(self, interaction: discord.Interaction):
        """Check everything needed to open a ticket. Replies and returns None if not."""
        if not await self._module_active(interaction):
            return None
        guild = interaction.guild
        try:
            settings = await tickets.check_can_open(guild.id, interaction.user.id)
        except GuildNotRegistered:
            await self._reply(interaction, NOT_SET_UP)
            return None
        except TicketError as exc:
            await self._reply(interaction, exc.message)
            return None

        category, problem = self._category(guild, settings.category_id)
        if problem:
            await self._reply(interaction, problem)
            return None
        roles = [
            role
            for role in (
                guild.get_role(role_id) for role_id in tickets.staff_role_ids(settings)
            )
            if role is not None
        ]
        if not roles:
            await self._reply(interaction, STAFF_GONE)
            return None
        return settings, category, roles

    # ------------------------------------------------------------------ opening

    async def start_open(self, interaction: discord.Interaction) -> None:
        """Show the ticket form if the member may open a ticket right now."""
        if await self._open_requirements(interaction) is None:
            return
        await interaction.response.send_modal(OpenTicketModal(self.open))

    async def open(
        self, interaction: discord.Interaction, subject: str, description: str
    ) -> None:
        """Create the ticket channel, its status message and the ticket itself."""
        await interaction.response.defer(ephemeral=True)
        # Settings may have changed while the form was open.
        requirements = await self._open_requirements(interaction)
        if requirements is None:
            return
        _, category, roles = requirements
        guild, user = interaction.guild, interaction.user

        number = await tickets.allocate_number(guild.id)
        visible = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        )
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: visible,
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                mention_everyone=False,
            ),
        }
        for role in roles:
            overwrites[role] = visible

        try:
            channel = await guild.create_text_channel(
                name=tickets.channel_name(number, user.name, False),
                category=category,
                overwrites=overwrites,
                topic=subject,
                reason=f"Ticket opened by {user.name}",
            )
        except discord.Forbidden:
            await self._reply(
                interaction,
                "I do not have permission to create ticket channels. "
                "Please inform the admins.",
            )
            return
        except discord.HTTPException:
            logger.exception("Creating a ticket channel failed in guild %s", guild.id)
            await self._reply(
                interaction, "The ticket could not be created. Please try again later."
            )
            return

        try:
            ticket = await tickets.create_ticket(
                guild.id, number, channel.id, user.id, subject
            )
            message = await channel.send(
                content=" ".join(role.mention for role in roles),
                embed=build_status_embed(ticket),
                view=TicketControlView(ticket),
            )
            await tickets.set_control_message(channel.id, message.id)
            if description:
                await channel.send(
                    f"**{subject}**\n{description}",
                    allowed_mentions=discord.AllowedMentions.none(),
                )
        except Exception:  # pylint: disable=broad-exception-caught
            # Never leave a channel without a ticket or a ticket without a channel.
            logger.exception(
                "Setting up ticket %s failed in guild %s", number, guild.id
            )
            await tickets.remove_by_channel(channel.id)
            try:
                await channel.delete(reason="Ticket could not be set up")
            except discord.HTTPException:
                logger.exception("Could not remove half-created ticket channel")
            await self._reply(
                interaction, "The ticket could not be created. Please try again later."
            )
            return

        await self._reply(
            interaction, f"Your ticket has been created: {channel.mention}"
        )

    # ------------------------------------------------------------------ buttons

    async def handle(self, interaction: discord.Interaction, action: Action) -> None:
        """Apply a click on one of the ticket buttons."""
        if not await self._module_active(interaction):
            return
        if action is Action.DELETE:
            await self._ask_delete(interaction)
            return

        guild, channel = interaction.guild, interaction.channel
        try:
            settings = await tickets.get_settings(guild.id)
            actor = self.actor_for(interaction.user, settings)
            category = None
            if action is Action.REOPEN:
                current = await tickets.check_action(channel.id, action, actor)
                if current.is_archived:
                    category, problem = self._category(guild, settings.category_id)
                    if problem:
                        await self._reply(interaction, problem)
                        return
            ticket = await _TRANSITIONS[action](channel.id, actor)
        except GuildNotRegistered:
            await self._reply(interaction, "This channel is not a ticket.")
            return
        except TicketError as exc:
            await self._reply(interaction, exc.message)
            return

        await self._show(interaction, ticket)
        if action in (Action.CLOSE, Action.REOPEN):
            await self._apply_to_channel(channel, ticket, category)
        await interaction.followup.send(
            f"{interaction.user.mention} {_VERBS[action]} the ticket.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def _show(
        self, interaction: discord.Interaction, ticket: GuildTicket
    ) -> None:
        """Bring the clicked message in line with the ticket."""
        message = interaction.message
        if message is not None and ticket.control_message_id != message.id:
            # Tickets from before the rebuild adopt the message that was clicked.
            await tickets.set_control_message(ticket.channel_id, message.id)
        await interaction.response.edit_message(
            embed=build_status_embed(ticket), view=TicketControlView(ticket)
        )

    async def _apply_to_channel(self, channel, ticket: GuildTicket, category) -> None:
        """Reflect open/closed in the owner's permission, the name and the category."""
        owner = channel.guild.get_member(ticket.user_id)
        try:
            if owner is not None:
                overwrite = channel.overwrites_for(owner)
                overwrite.send_messages = not ticket.is_closed
                await channel.set_permissions(owner, overwrite=overwrite)
            if category is not None:
                await channel.edit(
                    category=category, reason="Ticket reopened from the archive"
                )
        except discord.HTTPException:
            logger.exception("Could not update ticket channel %s", channel.id)
        self.renamer.request(
            channel,
            tickets.channel_name(
                ticket.ticket_number,
                self._owner_name(channel, owner),
                ticket.is_closed,
            ),
        )

    # ------------------------------------------------------------------ deleting

    async def _checked_for_delete(self, interaction: discord.Interaction):
        """Return (ticket, settings) if the user may delete it; reply otherwise."""
        try:
            settings = await tickets.get_settings(interaction.guild.id)
            actor = self.actor_for(interaction.user, settings)
            ticket = await tickets.check_action(
                interaction.channel.id, Action.DELETE, actor
            )
        except GuildNotRegistered:
            await self._reply(interaction, "This channel is not a ticket.")
            return None
        except TicketError as exc:
            await self._reply(interaction, exc.message)
            return None
        return ticket, settings, actor

    async def _ask_delete(self, interaction: discord.Interaction) -> None:
        if await self._checked_for_delete(interaction) is None:
            return
        await interaction.response.send_message(
            DELETE_QUESTION, view=ConfirmDeleteView(self.delete), ephemeral=True
        )

    async def delete(self, interaction: discord.Interaction) -> None:
        """Delete the ticket channel and then the ticket."""
        if not await self._module_active(interaction):
            return
        checked = await self._checked_for_delete(interaction)
        if checked is None:
            return
        ticket, settings, actor = checked
        channel = interaction.channel

        await interaction.response.edit_message(content="Deleting ticket…", view=None)
        await self._before_delete(interaction, ticket, settings)
        try:
            await channel.delete(reason=f"Ticket deleted by {interaction.user.name}")
        except discord.NotFound:
            pass
        except discord.HTTPException:
            logger.exception("Could not delete ticket channel %s", channel.id)
            await self._reply(
                interaction, "I do not have permission to delete this channel."
            )
            return
        try:
            await tickets.delete(channel.id, actor)
        except TicketNotFound:
            pass  # already removed when the channel went away

    async def _before_delete(
        self,
        interaction: discord.Interaction,
        ticket: GuildTicket,
        settings: GuildTicketSettings,
    ) -> None:
        """Post the transcript to the log channel, if one is set.

        A failing transcript never keeps the ticket from being deleted.
        """
        if not settings.log_channel_id:
            return
        log_channel = interaction.guild.get_channel(settings.log_channel_id)
        if log_channel is None:
            return
        try:
            messages = [
                message
                async for message in interaction.channel.history(
                    limit=MAX_MESSAGES, oldest_first=True
                )
            ]
            text = render_transcript(ticket, messages, deleted_by=interaction.user.name)
            number = f"{ticket.ticket_number:04d}"
            embed = discord.Embed(
                title=f"🗑️ Ticket #{number} deleted",
                description=(
                    f"Subject: {ticket.subject or '–'}\n"
                    f"Created by: <@{ticket.user_id}>\n"
                    f"Deleted by: {interaction.user.mention}\n"
                    f"Messages: {len(messages)}"
                ),
            )
            await log_channel.send(
                embed=embed,
                file=discord.File(
                    io.BytesIO(text.encode("utf-8")), filename=f"ticket-{number}.txt"
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception(
                "Could not write transcript of ticket #%s of guild %s",
                ticket.ticket_number,
                ticket.guild_id,
            )
