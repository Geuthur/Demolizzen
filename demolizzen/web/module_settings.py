"""The settings pages of modules in the web panel.

A page knows how to load a module's settings for its form and how to save a
submitted form. Both go through the service layer, like the bot's own panel.
"""

# Standard Library
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

# Demolizzen
from demolizzen.core import registry
from demolizzen.services import bank, levels, missions
from demolizzen.services.errors import BankError, InvalidEventFactor, MissionError


class InvalidInput(Exception):
    """The form held a value the page does not offer. ``message`` is shown to the user."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class SettingsPage:
    key: str
    title: str
    template: str
    # async (guild_id) -> the values the form shows
    load: Callable[[int], Awaitable[dict]]
    # async (guild_id, submitted form) -> None; raises InvalidInput
    save: Callable[[int, dict], Awaitable[None]]


# ------------------------------------------------------------------------- bank


def _percent(interest_rate: float) -> float:
    return round(interest_rate * 100, 6)


async def _bank_load(guild_id: int) -> dict:
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


async def _bank_save(guild_id: int, data) -> None:
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


async def _levels_load(guild_id: int) -> dict:
    announcement = await levels.get_announcement(guild_id)
    return {"announce": announcement.enabled}


async def _levels_save(guild_id: int, data) -> None:
    await levels.set_announcements(guild_id, "announce" in data)


# ---------------------------------------------------------------------- economy


async def _economy_load(guild_id: int) -> dict:
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


async def _economy_save(guild_id: int, data) -> None:
    factor = data.get("factor", "")
    try:
        if not (factor.isascii() and factor.isdecimal()):
            raise InvalidEventFactor(
                missions.MIN_EVENT_FACTOR, missions.MAX_EVENT_FACTOR
            )
        await missions.set_event(guild_id, active="active" in data, factor=int(factor))
    except MissionError as error:
        raise InvalidInput(error.message) from error


def _page(key: str, load, save) -> SettingsPage:
    return SettingsPage(
        key=key,
        title=registry.get(key).title,
        template=f"web/settings_{key}.html",
        load=load,
        save=save,
    )


PAGES: dict[str, SettingsPage] = {
    page.key: page
    for page in (
        _page("banksystem", _bank_load, _bank_save),
        _page("levelsystem", _levels_load, _levels_save),
        _page("economy", _economy_load, _economy_save),
    )
}
