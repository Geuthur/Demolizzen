"""Tickets: settings, permissions and state changes."""

# Standard Library
import enum
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

# Third Party
from asgiref.sync import sync_to_async

# Django
from django.db import transaction
from django.utils import timezone

# Demolizzen
from demolizzen.models import GuildProfile, GuildTicket, GuildTicketSettings
from demolizzen.services.errors import (
    GuildNotRegistered,
    InvalidTicketSetting,
    TicketLimitReached,
    TicketNotConfigured,
    TicketNotFound,
    TicketPermissionDenied,
    TicketStateError,
)

MAX_SUBJECT_LENGTH = 100
MAX_CHANNEL_NAME_LENGTH = 100

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


class Action(enum.Enum):
    """What can be done with an existing ticket."""

    CLAIM = "claim"
    CLOSE = "close"
    REOPEN = "reopen"
    DELETE = "delete"


@dataclass(frozen=True)
class Actor:
    """Who wants to act on a ticket. Admins count as staff."""

    user_id: int
    is_staff: bool = False
    is_admin: bool = False


def is_allowed(
    action: Action, actor: Actor, ticket: GuildTicket, settings: GuildTicketSettings
) -> bool:
    """The rights table: may ``actor`` perform ``action`` on ``ticket``?"""
    staff = actor.is_staff or actor.is_admin
    owner = actor.user_id == ticket.user_id
    if action is Action.DELETE:
        return actor.is_admin
    if action is Action.CLAIM:
        return staff and not owner
    if action is Action.CLOSE:
        return staff or (owner and settings.allow_user_close)
    if action is Action.REOPEN:
        return staff or (owner and settings.allow_user_reopen)
    return False


def _denied_message(action: Action, actor: Actor, ticket: GuildTicket) -> str:
    if action is Action.CLAIM and actor.user_id == ticket.user_id:
        return "You cannot claim your own ticket."
    return {
        Action.CLAIM: "Only staff can claim a ticket.",
        Action.CLOSE: "You are not allowed to close this ticket.",
        Action.REOPEN: "You are not allowed to reopen this ticket.",
        Action.DELETE: "Only admins can delete a ticket.",
    }[action]


def _check_state(action: Action, ticket: GuildTicket) -> None:
    if action is Action.CLAIM:
        if ticket.is_closed:
            raise TicketStateError("This ticket is closed.")
        if ticket.claimed_by is not None:
            raise TicketStateError("This ticket is already claimed.")
    elif action is Action.CLOSE and ticket.is_closed:
        raise TicketStateError("This ticket is already closed.")
    elif action is Action.REOPEN and not ticket.is_closed:
        raise TicketStateError("This ticket is not closed.")


def _apply(action: Action, actor: Actor, ticket: GuildTicket) -> None:
    if action is Action.DELETE:
        ticket.delete()
        return
    if action is Action.CLAIM:
        ticket.claimed_by = actor.user_id
    elif action is Action.CLOSE:
        ticket.is_closed = True
        ticket.closed_by = actor.user_id
        ticket.closed_at = timezone.now()
    elif action is Action.REOPEN:
        ticket.is_closed = False
        ticket.is_archived = False
        ticket.closed_by = None
        ticket.closed_at = None
        ticket.claimed_by = None
    ticket.save()


def _transition_sync(
    channel_id: int, action: Action, actor: Actor, apply: bool
) -> GuildTicket:
    # The row is locked so two clicks at the same time cannot both succeed.
    with transaction.atomic():
        ticket = (
            GuildTicket.objects.select_for_update()
            .filter(channel_id=channel_id)
            .first()
        )
        if ticket is None:
            raise TicketNotFound("This channel is not a ticket.")
        settings, _ = GuildTicketSettings.objects.get_or_create(
            guild_id=ticket.guild_id
        )
        if not is_allowed(action, actor, ticket, settings):
            raise TicketPermissionDenied(_denied_message(action, actor, ticket))
        _check_state(action, ticket)
        if apply:
            _apply(action, actor, ticket)
    return ticket


async def check_action(channel_id: int, action: Action, actor: Actor) -> GuildTicket:
    """Check permission and state for an action without changing the ticket."""
    return await sync_to_async(_transition_sync)(channel_id, action, actor, False)


async def claim(channel_id: int, actor: Actor) -> GuildTicket:
    """Assign the ticket to a staff member."""
    return await sync_to_async(_transition_sync)(channel_id, Action.CLAIM, actor, True)


async def close(channel_id: int, actor: Actor) -> GuildTicket:
    """Close the ticket."""
    return await sync_to_async(_transition_sync)(channel_id, Action.CLOSE, actor, True)


async def reopen(channel_id: int, actor: Actor) -> GuildTicket:
    """Reopen a closed ticket. It starts over unclaimed and leaves the archive."""
    return await sync_to_async(_transition_sync)(channel_id, Action.REOPEN, actor, True)


async def delete(channel_id: int, actor: Actor) -> GuildTicket:
    """Delete the ticket and return what it was."""
    return await sync_to_async(_transition_sync)(channel_id, Action.DELETE, actor, True)


def channel_name(number: int, owner_name: str | None, closed: bool) -> str:
    """The name a ticket channel should have for its state."""
    slug = re.sub(r"[^a-z0-9]+", "-", (owner_name or "").lower()).strip("-") or "user"
    prefix = f"{'closed' if closed else 'ticket'}-{number:04d}-"
    return prefix + slug[: MAX_CHANNEL_NAME_LENGTH - len(prefix)].rstrip("-")


async def check_can_open(guild_id: int, user_id: int) -> GuildTicketSettings:
    """Make sure the guild is set up and the member is below their ticket limit."""
    settings = await get_settings(guild_id)
    if not settings.category_id or not staff_role_ids(settings):
        raise TicketNotConfigured(
            "The ticket system is not set up yet. "
            "Please ask an admin to configure it with /panel."
        )
    open_tickets = await GuildTicket.objects.filter(
        guild_id=guild_id, user_id=user_id, is_closed=False
    ).acount()
    if open_tickets >= settings.max_open_tickets:
        raise TicketLimitReached(
            f"You already have {open_tickets} open ticket(s). "
            "Please use your existing ticket."
        )
    return settings


def _allocate_number_sync(guild_id: int) -> int:
    with transaction.atomic():
        GuildTicketSettings.objects.get_or_create(guild_id=guild_id)
        settings = GuildTicketSettings.objects.select_for_update().get(
            guild_id=guild_id
        )
        number = settings.ticket_count
        settings.ticket_count = number + 1
        settings.save(update_fields=["ticket_count"])
    return number


async def allocate_number(guild_id: int) -> int:
    """Hand out the next ticket number. No number is handed out twice."""
    return await sync_to_async(_allocate_number_sync)(guild_id)


async def create_ticket(
    guild_id: int,
    number: int,
    channel_id: int,
    user_id: int,
    subject: str,
    control_message_id: int | None = None,
) -> GuildTicket:
    """Store a ticket whose channel already exists."""
    return await GuildTicket.objects.acreate(
        guild_id=guild_id,
        ticket_number=number,
        channel_id=channel_id,
        user_id=user_id,
        subject=(subject or "")[:MAX_SUBJECT_LENGTH],
        control_message_id=control_message_id,
    )


async def get_by_channel(channel_id: int) -> GuildTicket:
    """Return the ticket that lives in the channel."""
    ticket = await GuildTicket.objects.filter(channel_id=channel_id).afirst()
    if ticket is None:
        raise TicketNotFound("This channel is not a ticket.")
    return ticket


async def set_control_message(channel_id: int, message_id: int) -> None:
    """Remember which message shows the ticket's status and buttons."""
    await GuildTicket.objects.filter(channel_id=channel_id).aupdate(
        control_message_id=message_id
    )


async def remove_by_channel(channel_id: int) -> bool:
    """Forget the ticket of a channel that no longer exists."""
    deleted, _ = await GuildTicket.objects.filter(channel_id=channel_id).adelete()
    return deleted > 0


async def active_tickets(guild_ids: Iterable[int]) -> list[GuildTicket]:
    """All tickets of the guilds that are not archived."""
    return [
        ticket
        async for ticket in GuildTicket.objects.filter(
            guild_id__in=list(guild_ids), is_archived=False
        ).order_by("pk")
    ]


async def due_for_archive(now: datetime | None = None) -> list[GuildTicket]:
    """Closed tickets whose guild's archive delay has passed."""
    now = now or timezone.now()
    candidates = GuildTicket.objects.filter(
        is_closed=True, is_archived=False, closed_at__isnull=False
    ).order_by("pk")
    settings_by_guild = {
        settings.guild_id: settings
        async for settings in GuildTicketSettings.objects.filter(
            archive_category_id__isnull=False
        )
    }
    due = []
    async for ticket in candidates:
        settings = settings_by_guild.get(ticket.guild_id)
        if settings is None:
            continue
        if ticket.closed_at + timedelta(days=settings.auto_archive_days) < now:
            due.append(ticket)
    return due


async def mark_archived(ticket_id: int) -> None:
    """Record that the ticket's channel was moved to the archive."""
    await GuildTicket.objects.filter(pk=ticket_id).aupdate(is_archived=True)
