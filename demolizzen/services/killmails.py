"""Killmail subscriptions and the rules that decide who gets a killmail."""

# Standard Library
from dataclasses import dataclass

# Demolizzen
from demolizzen.models import UserProfile, ZKillboard
from demolizzen.services import guilds

# Subscriptions stored with this group id follow every killmail.
GLOBAL_GROUP_ID = 6
DEFAULT_THRESHOLD = 1


@dataclass(frozen=True)
class SubscriptionRule:
    """One subscription: which killmails a channel wants.

    ``group_id`` is an alliance, corporation, character, region or system id;
    ``None`` follows every killmail.
    """

    id: int
    guild_id: int
    channel_id: int
    group_id: int | None
    threshold: int | None
    losses: bool


@dataclass(frozen=True)
class KillFacts:
    """What the rules need to know about a killmail."""

    killmail_id: int
    total_value: float
    solar_system_id: int | None
    region_id: int | None
    victim_corporation_id: int | None
    victim_alliance_id: int | None
    attacker_corporation_ids: frozenset
    attacker_alliance_ids: frozenset
    attacker_character_ids: frozenset


def matches(rule: SubscriptionRule, facts: KillFacts) -> bool:
    """Whether the subscription wants this killmail."""
    if facts.total_value and rule.threshold and facts.total_value < rule.threshold:
        return False
    group = rule.group_id
    if not group:
        return True
    if group == facts.solar_system_id:
        return True
    # The victim's side only counts when the subscription asked for losses.
    if rule.losses and group in (
        facts.victim_corporation_id,
        facts.victim_alliance_id,
    ):
        return True
    if group in facts.attacker_corporation_ids or group in facts.attacker_alliance_ids:
        return True
    if facts.region_id and group == facts.region_id:
        return True
    return group in facts.attacker_character_ids


def is_loss(rule: SubscriptionRule, facts: KillFacts) -> bool:
    """Whether the killmail is a loss of the subscribed corporation or alliance."""
    return bool(rule.group_id) and rule.group_id in (
        facts.victim_corporation_id,
        facts.victim_alliance_id,
    )


def _rule(row: ZKillboard) -> SubscriptionRule:
    group_id = row.group_id if row.group_id != GLOBAL_GROUP_ID else None
    return SubscriptionRule(
        id=row.pk,
        guild_id=row.guild_id,
        channel_id=row.channel_id,
        group_id=group_id or None,
        threshold=row.threshold,
        losses=row.losses,
    )


async def load_rules() -> list[SubscriptionRule]:
    """All subscriptions of all guilds."""
    return [_rule(row) async for row in ZKillboard.objects.order_by("pk")]


async def rules_for_guild(guild_id: int) -> list[SubscriptionRule]:
    """The subscriptions of one guild."""
    return [
        _rule(row)
        async for row in ZKillboard.objects.filter(guild_id=guild_id).order_by("pk")
    ]


async def add_subscription(
    guild_id: int,
    owner_user_id: int,
    owner_name: str,
    channel_id: int,
    group_id: int,
    threshold: int | None = None,
    losses: bool = False,
) -> tuple[SubscriptionRule, bool]:
    """Subscribe a channel to a group's killmails.

    A channel follows a group at most once: an existing subscription is
    returned unchanged with ``False``.
    """
    existing = await ZKillboard.objects.filter(
        channel_id=channel_id, group_id=group_id
    ).afirst()
    if existing is not None:
        return _rule(existing), False

    await guilds.ensure_members(guild_id, [(owner_user_id, owner_name)])
    owner = (
        await UserProfile.objects.filter(guild_id=guild_id, user_id=owner_user_id)
        .order_by("pk")
        .afirst()
    )
    row = await ZKillboard.objects.acreate(
        channel_id=channel_id,
        group_id=group_id,
        guild_id=guild_id,
        owner=owner,
        losses=bool(losses),
        threshold=threshold if threshold is not None else DEFAULT_THRESHOLD,
    )
    return _rule(row), True


async def remove_subscription(subscription_id: int, guild_id: int) -> bool:
    """Remove one subscription if it belongs to the guild."""
    deleted, _ = await ZKillboard.objects.filter(
        pk=subscription_id, guild_id=guild_id
    ).adelete()
    return deleted > 0


async def _remove(queryset) -> list[int]:
    ids = [row.pk async for row in queryset.order_by("pk")]
    if ids:
        await ZKillboard.objects.filter(pk__in=ids).adelete()
    return ids


async def remove_for_channel(channel_id: int) -> list[int]:
    """Remove every subscription of a channel and return their ids."""
    return await _remove(ZKillboard.objects.filter(channel_id=channel_id))


async def remove_for_guild(guild_id: int) -> list[int]:
    """Remove every subscription of a guild and return their ids."""
    return await _remove(ZKillboard.objects.filter(guild_id=guild_id))
