"""Daily reward, work shifts and missions.

Each action checks its cooldown, changes its state and books money in one
transaction on locked rows. Nothing is paid twice, however many commands or
open messages race for it.

The random values and all texts come from the caller; this module only knows
the rules.
"""

# Standard Library
import enum
import math
from dataclasses import dataclass
from datetime import datetime, timedelta

# Third Party
from asgiref.sync import sync_to_async

# Django
from django.db import transaction
from django.utils import timezone

# Demolizzen
from demolizzen import config
from demolizzen.models import (
    EconomyShip,
    UserDailyReward,
    UserMiningMission,
    UserRaidMission,
    UserWorkMission,
)
from demolizzen.services import bank
from demolizzen.services.errors import (
    AlreadySettled,
    NoActiveMission,
    NoShip,
    OnCooldown,
    ShipAlreadyOwned,
    ShipNotFound,
)

DAILY_COOLDOWN = timedelta(days=1)
DAILY_STREAK_BONUS = 5


class Kind(enum.Enum):
    """The two kinds of missions."""

    MINING = "mining"
    RAIDING = "raiding"


_MODELS = {Kind.MINING: UserMiningMission, Kind.RAIDING: UserRaidMission}


@dataclass(frozen=True)
class DailyClaim:
    """A collected daily reward."""

    streak: int
    reward: int


@dataclass(frozen=True)
class WorkShift:
    """The result of going to work. The first shift only starts the clock."""

    first: bool
    paid: int
    duration: timedelta


@dataclass(frozen=True)
class Outcome:
    """How a mission ended. ``payout`` is negative when the ship was lost."""

    success: bool
    payout: int
    event_extra: int


# ---------------------------------------------------------------------- cooldowns


def cooldown_for(guild_id: int, user_id: int, duration: timedelta) -> timedelta:
    """The cooldown that applies to the member; test accounts may have a shorter one."""
    seconds = config.COOLDOWN_OVERRIDES.get(guild_id, {}).get(user_id)
    return timedelta(seconds=seconds) if seconds is not None else duration


def format_remaining(remaining: timedelta) -> str:
    """Render a remaining time as ``H:MM:SS``."""
    return str(remaining).split(".", maxsplit=1)[0]


def _remaining(last: datetime | None, duration: timedelta, now: datetime) -> timedelta:
    if last is None:
        return timedelta(0)
    return max(last + duration - now, timedelta(0))


def _check_cooldown(last: datetime | None, duration: timedelta, now: datetime) -> None:
    remaining = _remaining(last, duration, now)
    if remaining > timedelta(0):
        raise OnCooldown(remaining)


# ---------------------------------------------------------------------- daily


def _claim_daily_sync(
    guild_id: int, user_id: int, account_id: int, profile_id: int, base: int, now
) -> DailyClaim:
    with transaction.atomic():
        UserDailyReward.objects.get_or_create(user_id=profile_id)
        daily = UserDailyReward.objects.select_for_update().get(user_id=profile_id)
        _check_cooldown(
            daily.last_claim, cooldown_for(guild_id, user_id, DAILY_COOLDOWN), now
        )
        daily.streak = 1 if daily.last_claim is None else daily.streak + 1
        daily.last_claim = now
        daily.save(update_fields=["streak", "last_claim"])
        reward = base + daily.streak * DAILY_STREAK_BONUS
        if reward > 0:
            bank._credit_sync(account_id, "wallet", reward)
    return DailyClaim(streak=daily.streak, reward=reward)


async def claim_daily(
    guild_id: int, user_id: int, user_name: str, base_reward: int, now=None
) -> DailyClaim:
    """Collect the daily reward: ``base_reward`` plus a bonus for the streak."""
    account = await bank.ensure_account(guild_id, user_id, user_name)
    return await sync_to_async(_claim_daily_sync)(
        guild_id,
        user_id,
        account.pk,
        account.user_id,
        base_reward,
        now or timezone.now(),
    )


# ---------------------------------------------------------------------- work


def _work_sync(
    guild_id: int,
    user_id: int,
    account_id: int,
    profile_id: int,
    payout: int,
    chance: int,
    now,
) -> WorkShift:
    with transaction.atomic():
        UserWorkMission.objects.get_or_create(user_id=profile_id)
        shift = UserWorkMission.objects.select_for_update().get(user_id=profile_id)
        duration = cooldown_for(
            guild_id, user_id, timedelta(seconds=shift.job_duration)
        )
        _check_cooldown(shift.cooldown, duration, now)
        first = shift.salary is None
        paid = 0 if first else bank._adjust_sync(account_id, payout)
        shift.cooldown = now
        shift.chance = chance
        shift.salary = payout
        shift.save(update_fields=["cooldown", "chance", "salary"])
    return WorkShift(first=first, paid=paid, duration=duration)


async def work(
    guild_id: int, user_id: int, user_name: str, payout: int, chance: int, now=None
) -> WorkShift:
    """Go to work. Every shift after the first pays ``payout``."""
    account = await bank.ensure_account(guild_id, user_id, user_name)
    return await sync_to_async(_work_sync)(
        guild_id,
        user_id,
        account.pk,
        account.user_id,
        payout,
        chance,
        now or timezone.now(),
    )


# ---------------------------------------------------------------------- missions


def _locked_mission(kind: Kind, profile_id: int):
    model = _MODELS[kind]
    model.objects.get_or_create(user_id=profile_id)
    return model.objects.select_for_update().get(user_id=profile_id)


async def get_mission(guild_id: int, user_id: int, user_name: str, kind: Kind):
    """Return the member's mission of this kind with its ship loaded."""
    account = await bank.ensure_account(guild_id, user_id, user_name)
    mission, _ = await (
        _MODELS[kind]
        .objects.select_related("ship")
        .aget_or_create(user_id=account.user_id)
    )
    return mission


def _begin_sync(
    guild_id: int,
    user_id: int,
    profile_id: int,
    kind: Kind,
    salary: int,
    chance: int,
    now,
) -> bool:
    with transaction.atomic():
        mission = _locked_mission(kind, profile_id)
        ship = mission.ship
        if ship is None:
            raise NoShip("You don't have a ship yet.")
        duration = cooldown_for(guild_id, user_id, timedelta(seconds=ship.ship_speed))
        _check_cooldown(mission.cooldown, duration, now)
        if mission.salary is not None:
            return False
        mission.cooldown = now
        mission.chance = chance
        mission.salary = salary
        mission.active = True
        mission.save(update_fields=["cooldown", "chance", "salary", "active"])
    return True


async def begin(
    guild_id: int,
    user_id: int,
    user_name: str,
    kind: Kind,
    salary: int,
    chance: int,
    now=None,
) -> bool:
    """Start the first mission, or find that a returned mission awaits its report.

    Returns True when a mission was started with ``salary`` and ``chance``, and
    False when the previous mission is back and nothing was changed.
    """
    account = await bank.ensure_account(guild_id, user_id, user_name)
    return await sync_to_async(_begin_sync)(
        guild_id, user_id, account.user_id, kind, salary, chance, now or timezone.now()
    )


def resolve(
    roll: int,
    chance: int,
    payout: int,
    insurance: int,
    attack: bool,
    bonus_amount: int,
    event: bool,
    event_factor,
) -> Outcome:
    """Decide how a mission ended.

    The mission succeeds when ``roll`` does not exceed ``chance``. Attacking
    adds a bonus at low chances and costs a fifth of the payout otherwise. A
    lost ship costs the insurance, except during an event.
    """
    if roll > chance:
        return Outcome(success=False, payout=0 if event else -insurance, event_extra=0)

    if attack and chance <= 25:
        payout += bonus_amount
    event_extra = 0
    if event:
        boosted = math.ceil(payout * event_factor)
        event_extra = boosted - payout
        payout = boosted
    factor = 0.8 if attack and chance > 25 else 1.0
    return Outcome(success=True, payout=round(payout * factor), event_extra=event_extra)


def _settle_sync(
    account_id: int,
    profile_id: int,
    kind: Kind,
    started_at,
    payout: int,
    next_salary: int,
    next_chance: int,
    now,
) -> int:
    with transaction.atomic():
        mission = _locked_mission(kind, profile_id)
        # Every message that shows this mission carries its start time. Once one
        # of them has settled it, the stored start has moved on.
        if not mission.active or mission.cooldown != started_at:
            raise AlreadySettled("This mission has already been reported.")
        applied = bank._adjust_sync(account_id, payout) if payout else 0
        mission.salary = next_salary
        mission.chance = next_chance
        mission.cooldown = now
        mission.active = True
        mission.save(update_fields=["salary", "chance", "cooldown", "active"])
    return applied


async def settle(
    guild_id: int,
    user_id: int,
    user_name: str,
    kind: Kind,
    started_at,
    payout: int,
    next_salary: int,
    next_chance: int,
    now=None,
) -> int:
    """Book the result of the mission that started at ``started_at`` and start the next.

    Returns the amount that was booked; a loss takes at most what the wallet holds.
    """
    account = await bank.ensure_account(guild_id, user_id, user_name)
    return await sync_to_async(_settle_sync)(
        account.pk,
        account.user_id,
        kind,
        started_at,
        payout,
        next_salary,
        next_chance,
        now or timezone.now(),
    )


def _cancel_sync(profile_id: int, kind: Kind) -> None:
    with transaction.atomic():
        mission = _locked_mission(kind, profile_id)
        if not mission.active:
            raise NoActiveMission("You don't have an active mission to cancel.")
        mission.active = False
        mission.cooldown = None
        mission.chance = None
        mission.salary = None
        mission.save(update_fields=["active", "cooldown", "chance", "salary"])


async def cancel(guild_id: int, user_id: int, user_name: str, kind: Kind) -> None:
    """Abort the active mission without a payout."""
    account = await bank.ensure_account(guild_id, user_id, user_name)
    await sync_to_async(_cancel_sync)(account.user_id, kind)


def _buy_ship_sync(account_id: int, profile_id: int, kind: Kind, ship_name: str):
    # Paying and receiving the ship are one transaction.
    with transaction.atomic():
        ship = (
            EconomyShip.objects.filter(
                name__iexact=ship_name, category=kind.value, active=True
            )
            .order_by("pk")
            .first()
        )
        if ship is None:
            raise ShipNotFound(f"The item `{ship_name}` was not found!")
        mission = _locked_mission(kind, profile_id)
        if mission.ship_id == ship.pk:
            raise ShipAlreadyOwned(f"You already own the Ship **`{ship.name}`**")
        if ship.price > 0:
            bank._debit_sync(account_id, "wallet", ship.price, False)
        mission.ship = ship
        mission.save(update_fields=["ship"])
    return ship


async def buy_ship(
    guild_id: int, user_id: int, user_name: str, kind: Kind, ship_name: str
) -> EconomyShip:
    """Buy a ship for missions of this kind with money from the wallet."""
    account = await bank.ensure_account(guild_id, user_id, user_name)
    return await sync_to_async(_buy_ship_sync)(
        account.pk, account.user_id, kind, ship_name
    )
