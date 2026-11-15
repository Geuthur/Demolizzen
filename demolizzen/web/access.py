"""Who may manage a server in the web panel."""

# Demolizzen
from demolizzen.services import guilds

# Discord permission bits.
ADMINISTRATOR = 0x8
MANAGE_GUILD = 0x20


def can_manage(guild) -> bool:
    """Whether the signed-in user may manage this server.

    ``guild`` is an entry of Discord's list of the user's servers: its owner,
    or a member with *Administrator* or *Manage Server*, may manage it.
    Anything that cannot be read counts as no.
    """
    if not isinstance(guild, dict):
        return False
    if guild.get("owner") is True:
        return True
    permissions = guild.get("permissions")
    if isinstance(permissions, str) and permissions.isdecimal():
        return bool(int(permissions) & (ADMINISTRATOR | MANAGE_GUILD))
    return False


def _guild_id(guild) -> int | None:
    value = guild.get("id") if isinstance(guild, dict) else None
    return int(value) if isinstance(value, str) and value.isdecimal() else None


async def manageable_guild_ids(discord_guilds) -> list[int]:
    """The servers the user may manage and the bot is registered in, sorted."""
    if not isinstance(discord_guilds, list):
        return []
    wanted = {
        guild_id
        for guild in discord_guilds
        if can_manage(guild) and (guild_id := _guild_id(guild)) is not None
    }
    return sorted(guild_id for guild_id, _ in await guilds.known_guilds(wanted))
