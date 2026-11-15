"""Experience and levels."""

# Standard Library
import random
from dataclasses import dataclass

# Third Party
from asgiref.sync import sync_to_async

# Django
from django.db import transaction
from django.db.models import F, Q

# Demolizzen
from demolizzen import config
from demolizzen.models import GuildProfile, UserProfile, UserSettings
from demolizzen.services import guilds
from demolizzen.services.errors import GuildNotRegistered


@dataclass(frozen=True)
class Progress:
    """Where a member stands inside their level."""

    level: int
    into_level: int
    needed: int
    percent: int


@dataclass(frozen=True)
class XpResult:
    """The member's state after experience was added."""

    experience: int
    level: int
    previous_level: int
    leveled_up: bool


@dataclass(frozen=True)
class CardData:
    """Everything a rank or level-up card shows about a member."""

    user_name: str
    experience: int
    level: int
    rank: int
    background: str
    border: str
    xp_colour: str
    blur: int


@dataclass(frozen=True)
class Announcement:
    """Whether and where a guild announces level-ups."""

    enabled: bool
    channel_id: int | None


# ---------------------------------------------------------------------- formula


def xp_for_level(level: int) -> int:
    """The experience at which ``level`` begins."""
    return int(config.XP_PER_LEVEL / 2 * (level - 1) * level)


def level_for(xp: int) -> int:
    """The level a member with ``xp`` experience has. Levels start at 1."""
    level = 1
    while xp >= xp_for_level(level + 1):
        level += 1
    return level


def progress(xp: int) -> Progress:
    """Level and progress towards the next one."""
    level = level_for(xp)
    into_level = xp - xp_for_level(level)
    needed = int(config.XP_PER_LEVEL * level)
    return Progress(level, into_level, needed, int(into_level / needed * 100))


def message_xp(word_count: int, rng=random) -> int:
    """How much experience a message earns; 0 when the chance roll misses."""
    if config.XP_CHANCE is True:
        if rng.randint(1, config.XP_CHANCE_RATE) != config.XP_CHANCE_RATE:
            return 0
    xp_type = str(config.XP_TYPE).lower()
    if xp_type == "normal":
        return config.XP_NORMAL_AMOUNT
    if xp_type == "words":
        return word_count
    if xp_type == "ranrange":
        return rng.randint(config.XP_RANRANGE_MIN, config.XP_RANRANGE_MAX)
    return 0


# ---------------------------------------------------------------------- booking


def _add_xp_sync(guild_id: int, user_id: int, user_name: str, amount: int):
    with transaction.atomic():
        profiles = UserProfile.objects.filter(guild_id=guild_id, user_id=user_id)
        # One UPDATE on the stored value: messages in quick succession add up.
        if not profiles.update(experience=F("experience") + amount):
            return None
        profile = profiles.select_for_update().order_by("pk").first()
        previous = profile.level
        level = level_for(profile.experience)
        changed = []
        if level != previous:
            profile.level = level
            changed.append("level")
        if user_name and profile.user_name != user_name:
            profile.user_name = user_name
            changed.append("user_name")
        if changed:
            profile.save(update_fields=changed)
    return XpResult(profile.experience, level, previous, level > previous)


async def add_xp(
    guild_id: int, guild_name: str, user_id: int, user_name: str, amount: int
) -> XpResult:
    """Add experience to a member and report whether they reached a new level.

    Guild and profile are only created when the member has none yet.
    """
    result = await sync_to_async(_add_xp_sync)(guild_id, user_id, user_name, amount)
    if result is None:
        await guilds.ensure_guild(guild_id, guild_name)
        await guilds.ensure_members(guild_id, [(user_id, user_name)])
        result = await sync_to_async(_add_xp_sync)(guild_id, user_id, user_name, amount)
    return result


# ---------------------------------------------------------------------- reading


async def get_card_data(guild_id: int, user_id: int) -> CardData | None:
    """Return what a card shows about the member, or None without a profile."""
    profile = (
        await UserProfile.objects.filter(guild_id=guild_id, user_id=user_id)
        .order_by("pk")
        .afirst()
    )
    if profile is None:
        return None
    settings, _ = await UserSettings.objects.aget_or_create(
        user=profile,
        defaults={
            "background": config.DEFAULT_BACKGROUND,
            "border": config.DEFAULT_BORDER,
            "xp_colour": config.DEFAULT_XP_COLOUR,
            "blur": 5,
        },
    )
    ahead = await UserProfile.objects.filter(
        Q(level__gt=profile.level)
        | Q(level=profile.level, experience__gt=profile.experience),
        guild_id=guild_id,
    ).acount()
    return CardData(
        user_name=profile.user_name,
        experience=profile.experience,
        level=level_for(profile.experience),
        rank=ahead + 1,
        background=str(settings.background),
        border=str(settings.border),
        xp_colour=str(settings.xp_colour),
        blur=int(settings.blur),
    )


async def leaderboard(guild_id: int) -> list[tuple[str, int, int]]:
    """Name, level and experience of the guild's members, best first."""
    return [
        (profile.user_name, profile.level, profile.experience)
        async for profile in UserProfile.objects.filter(guild_id=guild_id).order_by(
            "-level", "-experience", "pk"
        )
    ]


# ---------------------------------------------------------------------- settings


async def get_announcement(guild_id: int) -> Announcement:
    """Whether the guild announces level-ups and in which channel."""
    profile = await GuildProfile.objects.filter(guild_id=guild_id).afirst()
    if profile is None:
        return Announcement(enabled=True, channel_id=None)
    return Announcement(enabled=profile.mention, channel_id=profile.main_channel_id)


async def set_announcements(guild_id: int, enabled: bool) -> None:
    """Switch level-up announcements for the guild."""
    updated = await GuildProfile.objects.filter(guild_id=guild_id).aupdate(
        mention=bool(enabled)
    )
    if not updated:
        raise GuildNotRegistered(guild_id)
