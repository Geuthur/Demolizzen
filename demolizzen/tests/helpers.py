"""Stand-ins for Discord objects used across the test suite."""

# Standard Library
from unittest.mock import AsyncMock, MagicMock

# Discord
import discord


def make_member(
    user_id: int = 10,
    name: str = "tester",
    *,
    bot: bool = False,
    manage_guild: bool = False,
    guild=None,
) -> MagicMock:
    """Build a guild member stand-in."""
    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.name = name
    member.display_name = name
    member.bot = bot
    member.guild = guild
    member.guild_permissions = MagicMock(manage_guild=manage_guild)
    return member


def make_guild(
    guild_id: int = 1, name: str = "Test Guild", members: list | None = None
) -> MagicMock:
    """Build a guild stand-in. The first member (or a default one) is the owner."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = guild_id
    guild.name = name
    guild.members = members if members is not None else []
    guild.owner = guild.members[0] if guild.members else make_member(1, "owner")
    for member in guild.members:
        member.guild = guild
    return guild


def make_ctx(guild=None, author=None) -> MagicMock:
    """Build an application context stand-in. ``guild=None`` models a DM."""
    ctx = MagicMock(spec=discord.ApplicationContext)
    ctx.guild = guild
    ctx.author = author if author is not None else make_member(guild=guild)
    ctx.user = ctx.author
    ctx.respond = AsyncMock()
    ctx.defer = AsyncMock()
    ctx.followup = MagicMock()
    ctx.followup.send = AsyncMock()
    return ctx


def make_interaction(guild=None, user=None) -> MagicMock:
    """Build a component interaction stand-in."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = guild
    interaction.guild_id = guild.id if guild is not None else None
    interaction.user = user if user is not None else make_member(guild=guild)
    interaction.response = MagicMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.send_message = AsyncMock()
    return interaction
