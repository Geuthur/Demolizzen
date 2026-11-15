"""Tickets: settings, permissions and state changes."""

# Demolizzen
from demolizzen.models import GuildProfile, GuildTicketSettings
from demolizzen.services.errors import GuildNotRegistered, InvalidTicketSetting

SETTING_FIELDS = (
    "category_id",
    "archive_category_id",
    "log_channel_id",
    "roles",
    "auto_archive_days",
    "max_open_tickets",
    "allow_user_close",
    "allow_user_reopen",
)

_ID_FIELDS = ("category_id", "archive_category_id", "log_channel_id")
_FLAG_FIELDS = ("allow_user_close", "allow_user_reopen")
_RANGES = {"auto_archive_days": (1, 365), "max_open_tickets": (1, 10)}


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_setting(field: str, value) -> None:
    if field not in SETTING_FIELDS:
        raise InvalidTicketSetting(f"Unknown ticket setting '{field}'.")
    if field in _ID_FIELDS:
        valid = value is None or (_is_int(value) and value > 0)
    elif field in _FLAG_FIELDS:
        valid = isinstance(value, bool)
    elif field == "roles":
        valid = isinstance(value, list) and all(_is_int(role) for role in value)
    else:
        low, high = _RANGES[field]
        valid = _is_int(value) and low <= value <= high
    if not valid:
        raise InvalidTicketSetting(f"Invalid value for ticket setting '{field}'.")


async def get_settings(guild_id: int) -> GuildTicketSettings:
    """Return the guild's ticket settings, creating the row when it is missing."""
    if not await GuildProfile.objects.filter(guild_id=guild_id).aexists():
        raise GuildNotRegistered(guild_id)
    settings, _ = await GuildTicketSettings.objects.aget_or_create(guild_id=guild_id)
    return settings


async def update_settings(guild_id: int, **fields) -> GuildTicketSettings:
    """Change ticket settings. Nothing is saved unless every value is valid."""
    for field, value in fields.items():
        _validate_setting(field, value)
    settings = await get_settings(guild_id)
    for field, value in fields.items():
        setattr(settings, field, value)
    if fields:
        await settings.asave(update_fields=list(fields))
    return settings


def staff_role_ids(settings: GuildTicketSettings) -> list[int]:
    """The configured staff role ids, ignoring anything that is not a role id."""
    if not isinstance(settings.roles, list):
        return []
    return [role for role in settings.roles if _is_int(role)]
