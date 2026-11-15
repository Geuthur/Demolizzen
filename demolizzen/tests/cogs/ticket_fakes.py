"""A small fake Discord guild for ticket tests."""

# Standard Library
from unittest.mock import AsyncMock, MagicMock

# Discord
import discord

# Demolizzen
from demolizzen.services import cog_settings, guilds, tickets
from demolizzen.tests.helpers import make_guild, make_member

GUILD_ID = 1
CATEGORY_ID = 500
ARCHIVE_ID = 600
LOG_ID = 700
STAFF_ROLE_ID = 900
OWNER_ID = 10
STAFF_ID = 20
ADMIN_ID = 30


def make_role(role_id: int):
    role = MagicMock(spec=discord.Role)
    role.id = role_id
    role.mention = f"<@&{role_id}>"
    return role


def make_category(category_id: int, channel_count: int = 0):
    category = MagicMock(spec=discord.CategoryChannel)
    category.id = category_id
    category.channels = [MagicMock() for _ in range(channel_count)]
    return category


def make_channel(channel_id: int, name: str, guild=None, category=None):
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = channel_id
    channel.name = name
    channel.guild = guild
    channel.category = category
    channel.mention = f"<#{channel_id}>"

    async def edit(**kwargs):
        for key, value in kwargs.items():
            if key != "reason":
                setattr(channel, key, value)

    channel.edit = AsyncMock(side_effect=edit)
    channel.delete = AsyncMock()
    channel.set_permissions = AsyncMock()
    channel.overwrites_for = MagicMock(return_value=discord.PermissionOverwrite())
    sent = MagicMock()
    sent.id = channel_id + 1
    channel.send = AsyncMock(return_value=sent)
    return channel


class FakeGuild:
    """Builds a guild with owner, staff, admin, categories and one ticket channel."""

    def __init__(self):
        self.staff_role = make_role(STAFF_ROLE_ID)
        self.owner = make_member(OWNER_ID, "Max Mustermann")
        self.staff = make_member(STAFF_ID, "mod")
        self.admin = make_member(ADMIN_ID, "admin", manage_guild=True)
        self.stranger = make_member(40, "stranger")
        self.owner.roles = []
        self.stranger.roles = []
        self.admin.roles = []
        self.staff.roles = [self.staff_role]
        self.guild = make_guild(
            GUILD_ID, "Alpha", members=[make_member(1, "boss"), self.owner]
        )
        for member in (self.owner, self.staff, self.admin, self.stranger):
            member.guild = self.guild
            member.mention = f"<@{member.id}>"
        self.category = make_category(CATEGORY_ID)
        self.archive = make_category(ARCHIVE_ID)
        self.log_channel = make_channel(LOG_ID, "ticket-log", self.guild)
        self.channels = {
            CATEGORY_ID: self.category,
            ARCHIVE_ID: self.archive,
            LOG_ID: self.log_channel,
        }
        self.members = {
            member.id: member for member in (self.owner, self.staff, self.admin)
        }
        self.guild.get_channel = MagicMock(side_effect=self.channels.get)
        self.guild.get_member = MagicMock(side_effect=self.members.get)
        self.guild.get_role = MagicMock(
            side_effect={STAFF_ROLE_ID: self.staff_role}.get
        )
        self.guild.default_role = make_role(GUILD_ID)
        self.guild.me = make_member(2, "bot", bot=True)
        self.created = []

        async def create_text_channel(name, **kwargs):
            channel = make_channel(
                1000 + len(self.created), name, self.guild, kwargs.get("category")
            )
            channel.overwrites = kwargs.get("overwrites")
            self.created.append(channel)
            self.channels[channel.id] = channel
            return channel

        self.guild.create_text_channel = AsyncMock(side_effect=create_text_channel)

    async def configure(self, **fields):
        cog_settings.invalidate()
        await guilds.ensure_guild(GUILD_ID, "Alpha")
        defaults = {"category_id": CATEGORY_ID, "roles": [STAFF_ROLE_ID]}
        defaults.update(fields)
        return await tickets.update_settings(GUILD_ID, **defaults)

    async def make_ticket(self, number: int = 1, channel_id: int = 100, **fields):
        """Create a stored ticket of the owner together with its channel."""
        # Demolizzen
        from demolizzen.models import GuildTicket

        closed = fields.get("is_closed", False)
        channel = make_channel(
            channel_id,
            tickets.channel_name(number, self.owner.name, closed),
            self.guild,
            self.archive if fields.get("is_archived") else self.category,
        )
        self.channels[channel_id] = channel
        ticket = await tickets.create_ticket(
            GUILD_ID, number, channel_id, OWNER_ID, "Login problem", channel_id + 1
        )
        if fields:
            await GuildTicket.objects.filter(pk=ticket.pk).aupdate(**fields)
        return channel

    def interaction(self, user, channel=None, message_id=None):
        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = self.guild
        interaction.guild_id = self.guild.id
        interaction.user = user
        interaction.channel = channel
        interaction.message = MagicMock()
        interaction.message.id = (
            message_id
            if message_id is not None
            else (channel.id + 1 if channel is not None else 1)
        )
        interaction.message.edit = AsyncMock()
        done = {"value": False}

        async def finish(*args, **kwargs):
            done["value"] = True

        interaction.response = MagicMock()
        interaction.response.is_done = MagicMock(side_effect=lambda: done["value"])
        for name in ("send_message", "send_modal", "defer", "edit_message"):
            setattr(interaction.response, name, AsyncMock(side_effect=finish))
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        interaction.edit_original_response = AsyncMock()
        return interaction


def said(interaction) -> list[str]:
    """Everything the bot told the user through this interaction."""
    texts = []
    calls = (
        interaction.response.send_message.await_args_list
        + interaction.response.edit_message.await_args_list
        + interaction.followup.send.await_args_list
        + interaction.edit_original_response.await_args_list
    )
    for call in calls:
        text = call.args[0] if call.args else call.kwargs.get("content")
        if text:
            texts.append(text)
    return texts
