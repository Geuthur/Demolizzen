"""The settings pages of modules in the web panel.

A page knows how to load a module's settings for its form and how to save a
submitted form. Both go through the service layer, like the bot's own panel.
"""

# Standard Library
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

# Demolizzen
from demolizzen.core import registry
from demolizzen.services import bank, guilds, killmails, levels, missions, tickets
from demolizzen.services.errors import (
    BankError,
    InvalidEventFactor,
    KillmailError,
    MissionError,
    TicketError,
)
from demolizzen.web import eve_names
from demolizzen.web.directory import Choice, Directory


class InvalidInput(Exception):
    """The form held a value the page does not offer. ``message`` is shown to the user."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class SettingsPage:
    """One module's settings form.

    ``load`` and ``save`` receive the server's channels and roles when the page
    asks for them with ``needs_directory`` – or ``None`` when Discord could not
    be asked. A page then leaves its channel and role settings untouched.
    """

    key: str
    title: str
    template: str
    # async (guild_id, directory) -> the values the form shows
    load: Callable[[int, Directory | None], Awaitable[dict]]
    # async (guild_id, submitted form, directory) -> the notice to show, or
    # None for "<title> settings saved."; raises InvalidInput. A page with
    # ``needs_user`` is also given ``user``, the signed-in ``{"id", "name"}``.
    save: Callable[..., Awaitable[str | None]]
    needs_directory: bool = False
    needs_user: bool = False


NOT_ON_SERVER = (
    "That channel or role is not on this server. Reload the page and choose again."
)
NOT_LISTED = "Choose one of the listed values."


def _options(
    choices: list[Choice], current: int | None, none_label: str, deleted_label: str
) -> list[dict]:
    """The options of a channel picker: "none", what Discord listed, and the
    stored choice if Discord no longer lists it."""
    options = [{"value": "", "label": none_label, "selected": current is None}]
    options += [
        {"value": choice.id, "label": choice.name, "selected": choice.id == current}
        for choice in choices
    ]
    if current is not None and all(choice.id != current for choice in choices):
        options.append(
            {
                "value": current,
                "label": f"{deleted_label} ({current})",
                "selected": True,
            }
        )
    return options


def _id(raw: str, allowed: set[int]) -> int:
    """The submitted id, if it is one of the allowed ones."""
    if not (raw.isascii() and raw.isdecimal()) or int(raw) not in allowed:
        raise InvalidInput(NOT_ON_SERVER)
    return int(raw)


def _chosen(data, name: str, choices: list[Choice], current: int | None) -> int | None:
    """The channel picked in the form: one Discord listed for this server, the
    one already stored, or none."""
    raw = data.get(name, "")
    if raw == "":
        return None
    allowed = {choice.id for choice in choices}
    if current is not None:
        allowed.add(current)
    return _id(raw, allowed)


def _numbers(choices: tuple[int, ...], current: int, unit: str = "") -> list[dict]:
    return [
        {"value": number, "label": f"{number}{unit}", "selected": number == current}
        for number in sorted({*choices, current})
    ]


def _number(data, name: str, choices: tuple[int, ...], current: int) -> int:
    raw = data.get(name, "")
    if not (raw.isascii() and raw.isdecimal()) or int(raw) not in {*choices, current}:
        raise InvalidInput(NOT_LISTED)
    return int(raw)


# ------------------------------------------------------------------------- bank


def _percent(interest_rate: float) -> float:
    return round(interest_rate * 100, 6)


async def _bank_load(guild_id: int, _directory=None) -> dict:
    settings = await bank.get_settings(guild_id)
    current = _percent(settings.interest_rate)
    # A rate set some other way stays selectable, so saving does not change it.
    percents = sorted({*bank.INTEREST_CHOICES, current})
    return {
        "choices": [
            {
                "value": f"{percent:g}",
                "label": f"{percent:g}%",
                "selected": percent == current,
            }
            for percent in percents
        ],
        "allow_deposits": settings.allow_deposits,
        "allow_withdrawals": settings.allow_withdrawals,
    }


async def _bank_save(guild_id: int, data, _directory=None) -> None:
    settings = await bank.get_settings(guild_id)
    current = _percent(settings.interest_rate)
    offered = {f"{percent:g}": percent for percent in (*bank.INTEREST_CHOICES, current)}
    chosen = data.get("interest", "")
    if chosen not in offered:
        raise InvalidInput("Choose one of the listed interest rates.")

    fields = {
        "allow_deposits": "allow_deposits" in data,
        "allow_withdrawals": "allow_withdrawals" in data,
    }
    if offered[chosen] != current:
        fields["interest_rate"] = offered[chosen] / 100
    try:
        await bank.update_settings(guild_id, **fields)
    except BankError as error:
        raise InvalidInput(error.message) from error


# ----------------------------------------------------------------- level system


async def _levels_load(guild_id: int, directory: Directory | None = None) -> dict:
    announcement = await levels.get_announcement(guild_id)
    values = {"announce": announcement.enabled, "has_directory": directory is not None}
    if directory is not None:
        values["channels"] = _options(
            directory.text_channels,
            await guilds.get_main_channel(guild_id),
            "System channel",
            "Deleted channel",
        )
    return values


async def _levels_save(guild_id: int, data, directory: Directory | None = None) -> None:
    # Check the channel first, so a refused form changes nothing at all.
    if directory is not None:
        channel_id = _chosen(
            data,
            "channel",
            directory.text_channels,
            await guilds.get_main_channel(guild_id),
        )
    await levels.set_announcements(guild_id, "announce" in data)
    if directory is not None:
        await guilds.set_main_channel(guild_id, channel_id)


# ---------------------------------------------------------------------- tickets


def _role_options(directory: Directory, stored: list[int]) -> list[dict]:
    options = [
        {"value": role.id, "label": role.name, "checked": role.id in stored}
        for role in directory.roles
    ]
    listed = {role.id for role in directory.roles}
    options += [
        {"value": role_id, "label": f"Deleted role ({role_id})", "checked": True}
        for role_id in stored
        if role_id not in listed
    ]
    return options


async def _ticket_load(guild_id: int, directory: Directory | None = None) -> dict:
    settings = await tickets.get_settings(guild_id)
    stored_roles = tickets.staff_role_ids(settings)
    values = {
        "allow_user_close": settings.allow_user_close,
        "allow_user_reopen": settings.allow_user_reopen,
        "archive_days": _numbers(
            tickets.ARCHIVE_DAY_CHOICES, settings.auto_archive_days
        ),
        "open_tickets": _numbers(
            tickets.OPEN_TICKET_CHOICES, settings.max_open_tickets
        ),
        # What members need before they can open a ticket.
        "ready": bool(settings.category_id and stored_roles),
        "has_directory": directory is not None,
    }
    if directory is not None:
        values.update(
            categories=_options(
                directory.categories,
                settings.category_id,
                "Not set",
                "Deleted category",
            ),
            archive_categories=_options(
                directory.categories,
                settings.archive_category_id,
                "None",
                "Deleted category",
            ),
            log_channels=_options(
                directory.text_channels,
                settings.log_channel_id,
                "None",
                "Deleted channel",
            ),
            roles=_role_options(directory, stored_roles),
        )
    return values


def _chosen_roles(data, directory: Directory, stored: list[int]) -> list[int]:
    allowed = {role.id for role in directory.roles} | set(stored)
    chosen = {_id(raw, allowed) for raw in data.getlist("roles")}
    if len(chosen) > tickets.MAX_STAFF_ROLES:
        raise InvalidInput(f"Choose at most {tickets.MAX_STAFF_ROLES} staff roles.")
    # In the order of the form: Discord's roles first, then deleted ones.
    order = [role.id for role in directory.roles] + stored
    return [role_id for role_id in dict.fromkeys(order) if role_id in chosen]


async def _ticket_save(guild_id: int, data, directory: Directory | None = None) -> None:
    settings = await tickets.get_settings(guild_id)
    fields = {
        "allow_user_close": "allow_user_close" in data,
        "allow_user_reopen": "allow_user_reopen" in data,
        "auto_archive_days": _number(
            data,
            "auto_archive_days",
            tickets.ARCHIVE_DAY_CHOICES,
            settings.auto_archive_days,
        ),
        "max_open_tickets": _number(
            data,
            "max_open_tickets",
            tickets.OPEN_TICKET_CHOICES,
            settings.max_open_tickets,
        ),
    }
    if directory is not None:
        fields.update(
            category_id=_chosen(
                data, "category", directory.categories, settings.category_id
            ),
            archive_category_id=_chosen(
                data,
                "archive_category",
                directory.categories,
                settings.archive_category_id,
            ),
            log_channel_id=_chosen(
                data, "log_channel", directory.text_channels, settings.log_channel_id
            ),
            roles=_chosen_roles(data, directory, tickets.staff_role_ids(settings)),
        )
    try:
        await tickets.update_settings(guild_id, **fields)
    except TicketError as error:
        raise InvalidInput(error.message) from error


# ---------------------------------------------------------------------- economy


async def _economy_load(guild_id: int, _directory=None) -> dict:
    event = await missions.get_event(guild_id)
    return {
        "active": event.active,
        "factors": [
            {"value": factor, "selected": factor == event.factor}
            for factor in range(
                missions.MIN_EVENT_FACTOR, missions.MAX_EVENT_FACTOR + 1
            )
        ],
    }


async def _economy_save(guild_id: int, data, _directory=None) -> None:
    factor = data.get("factor", "")
    try:
        if not (factor.isascii() and factor.isdecimal()):
            raise InvalidEventFactor(
                missions.MIN_EVENT_FACTOR, missions.MAX_EVENT_FACTOR
            )
        await missions.set_event(guild_id, active="active" in data, factor=int(factor))
    except MissionError as error:
        raise InvalidInput(error.message) from error


# -------------------------------------------------------------------- killmails

NO_SUBSCRIPTION = "That subscription no longer exists. Reload the page."
NO_CHANNEL_LIST = (
    "Channels could not be loaded from Discord, so nothing can be added right now."
)
BAD_GROUP = (
    "Enter the id to follow as a whole number: an alliance, corporation, "
    "character, region or system id."
)
BAD_THRESHOLD = "The ISK threshold must be a whole number of at least 0."
# EVE ids have ten digits today.
_GROUP_DIGITS = 12
_THRESHOLD_DIGITS = len(str(killmails.MAX_THRESHOLD))


def _digits(raw: str, limit: int) -> int | None:
    """A plain non-negative whole number of at most ``limit`` digits."""
    if raw.isascii() and raw.isdecimal() and len(raw) <= limit:
        return int(raw)
    return None


def _threshold(data) -> int:
    raw = data.get("threshold", "").strip()
    if raw == "":
        return killmails.DEFAULT_THRESHOLD
    threshold = _digits(raw, _THRESHOLD_DIGITS)
    if threshold is None:
        raise InvalidInput(BAD_THRESHOLD)
    return threshold


def _channel_options(choices: list[Choice], current: int) -> list[dict]:
    """The channels a subscription can post to: what Discord listed, and its
    own channel if Discord no longer lists it."""
    options = [
        {"value": choice.id, "label": choice.name, "selected": choice.id == current}
        for choice in choices
    ]
    if all(choice.id != current for choice in choices):
        options.append(
            {
                "value": current,
                "label": f"Deleted channel ({current})",
                "selected": True,
            }
        )
    return options


# How the panel names ESI's categories, and which of them a killmail is ever
# matched by (see services.killmails.matches).
KIND_LABELS = {
    "alliance": "Alliance",
    "corporation": "Corporation",
    "character": "Character",
    "solar_system": "System",
    "region": "Region",
}


def _kind_label(kind: str) -> str:
    return KIND_LABELS.get(kind) or kind.replace("_", " ").capitalize()


async def _killmail_load(guild_id: int, directory: Directory | None = None) -> dict:
    rules = await killmails.rules_for_guild(guild_id)
    channels = directory.text_channels if directory is not None else None
    # What each followed id stands for; empty when EVE's API cannot say.
    names = await eve_names.lookup([rule.group_id for rule in rules if rule.group_id])
    known = {rule.id: names.get(rule.group_id) for rule in rules}
    return {
        "has_directory": directory is not None,
        "subscriptions": [
            {
                "id": rule.id,
                "follows": str(rule.group_id) if rule.group_id else "Every killmail",
                "kind": _kind_label(known[rule.id].kind) if known[rule.id] else None,
                "name": known[rule.id].name if known[rule.id] else None,
                # False for a kind of id no killmail is matched by.
                "matched": known[rule.id] is None or known[rule.id].kind in KIND_LABELS,
                "threshold": rule.threshold,
                "losses": rule.losses,
                "channel_id": rule.channel_id,
                "channels": (
                    _channel_options(channels, rule.channel_id)
                    if channels is not None
                    else None
                ),
            }
            for rule in rules
        ],
        "channels": channels,
    }


async def _killmail_add(guild_id: int, data, directory: Directory | None, user) -> str:
    if directory is None:
        raise InvalidInput(NO_CHANNEL_LIST)
    channel_id = _id(
        data.get("channel", ""), {choice.id for choice in directory.text_channels}
    )
    group_id = _digits(data.get("group", "").strip(), _GROUP_DIGITS)
    if not group_id:
        raise InvalidInput(BAD_GROUP)
    _, created = await killmails.add_subscription(
        guild_id,
        user["id"],
        user["name"],
        channel_id,
        group_id,
        threshold=_threshold(data),
        losses="losses" in data,
    )
    if not created:
        raise InvalidInput("That channel already follows this id.")
    return "Subscription added."


async def _killmail_change(
    guild_id: int, data, directory: Directory | None, action: str
) -> str:
    subscription_id = _digits(data.get("subscription", ""), _GROUP_DIGITS)
    # Only a subscription of this server can be named.
    rule = next(
        (
            rule
            for rule in await killmails.rules_for_guild(guild_id)
            if rule.id == subscription_id
        ),
        None,
    )
    if rule is None:
        raise InvalidInput(NO_SUBSCRIPTION)
    if action == "remove":
        if not await killmails.remove_subscription(rule.id, guild_id):
            raise InvalidInput(NO_SUBSCRIPTION)
        return "Subscription removed."

    channel_id = None  # without the channel list the channel stays
    if directory is not None:
        allowed = {choice.id for choice in directory.text_channels} | {rule.channel_id}
        channel_id = _id(data.get("channel", ""), allowed)
    await killmails.update_subscription(
        rule.id,
        guild_id,
        channel_id=channel_id,
        threshold=_threshold(data),
        losses="losses" in data,
    )
    return "Subscription saved."


async def _killmail_save(
    guild_id: int, data, directory: Directory | None = None, user=None
) -> str:
    """One page, three forms: ``action`` says which one was sent."""
    action = data.get("action", "")
    try:
        if action == "add":
            return await _killmail_add(guild_id, data, directory, user)
        if action in ("update", "remove"):
            return await _killmail_change(guild_id, data, directory, action)
    except KillmailError as error:
        raise InvalidInput(error.message) from error
    raise InvalidInput("That did not work. Reload the page and try again.")


def _page(
    key: str, load, save, needs_directory: bool = False, needs_user: bool = False
) -> SettingsPage:
    return SettingsPage(
        key=key,
        title=registry.get(key).title,
        template=f"web/settings_{key}.html",
        load=load,
        save=save,
        needs_directory=needs_directory,
        needs_user=needs_user,
    )


PAGES: dict[str, SettingsPage] = {
    page.key: page
    for page in (
        _page("banksystem", _bank_load, _bank_save),
        _page("levelsystem", _levels_load, _levels_save, needs_directory=True),
        _page("economy", _economy_load, _economy_save),
        _page("ticket", _ticket_load, _ticket_save, needs_directory=True),
        _page(
            "killmail",
            _killmail_load,
            _killmail_save,
            needs_directory=True,
            needs_user=True,
        ),
    )
}
