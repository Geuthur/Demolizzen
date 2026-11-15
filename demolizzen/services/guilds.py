"""Guild and member bookkeeping."""

# Standard Library
from collections.abc import Iterable

# Third Party
from asgiref.sync import sync_to_async

# Demolizzen
from demolizzen import config
from demolizzen.models import GuildProfile, UserProfile, UserSettings
from demolizzen.services.errors import GuildNotRegistered

MEMBER_BATCH_SIZE = 1000


async def ensure_guild(guild_id: int, name: str) -> tuple[GuildProfile, bool]:
    """Make sure the guild has a profile and its settings rows.

    Returns the profile and whether it was created by this call.
    """
    profile, created = await GuildProfile.objects.aget_or_create(
        guild_id=guild_id, defaults={"guild_name": name}
    )
    await sync_to_async(profile.create_settings)()
    return profile, created


async def rename_guild(guild_id: int, name: str) -> bool:
    """Store a new guild name. Returns True only when the name changed."""
    updated = (
        await GuildProfile.objects.filter(guild_id=guild_id)
        .exclude(guild_name=name)
        .aupdate(guild_name=name)
    )
    return updated > 0


async def remove_guild(guild_id: int) -> bool:
    """Delete the guild and everything that belongs to it."""
    deleted, _ = await GuildProfile.objects.filter(guild_id=guild_id).adelete()
    return deleted > 0


async def remove_missing_guilds(present_ids: Iterable[int]) -> list[int]:
    """Delete all guilds that are not in ``present_ids`` and return their ids."""
    missing = GuildProfile.objects.exclude(guild_id__in=list(present_ids))
    removed = sorted([guild.guild_id async for guild in missing])
    if removed:
        await GuildProfile.objects.filter(guild_id__in=removed).adelete()
    return removed


async def ensure_members(guild_id: int, members: Iterable[tuple[int, str]]) -> int:
    """Create profiles and default settings for members that have none yet.

    ``members`` are ``(user_id, name)`` pairs. Returns the number of created profiles.
    """
    if not await GuildProfile.objects.filter(guild_id=guild_id).aexists():
        raise GuildNotRegistered(guild_id)

    wanted = dict(members)
    user_ids = list(wanted)
    created = 0
    # Large guilds are handled in batches to keep the IN lists bounded.
    for start in range(0, len(user_ids), MEMBER_BATCH_SIZE):
        batch = user_ids[start : start + MEMBER_BATCH_SIZE]
        created += await _ensure_member_batch(
            guild_id, {uid: wanted[uid] for uid in batch}
        )
    return created


async def _ensure_member_batch(guild_id: int, wanted: dict[int, str]) -> int:
    existing = {
        profile.user_id
        async for profile in UserProfile.objects.filter(
            guild_id=guild_id, user_id__in=list(wanted)
        )
    }
    new_ids = [user_id for user_id in wanted if user_id not in existing]
    if not new_ids:
        return 0

    await UserProfile.objects.abulk_create(
        [
            UserProfile(user_id=user_id, guild_id=guild_id, user_name=wanted[user_id])
            for user_id in new_ids
        ]
    )
    # bulk_create does not return primary keys on every backend, so read them back.
    created = [
        profile
        async for profile in UserProfile.objects.filter(
            guild_id=guild_id, user_id__in=new_ids
        )
    ]
    await UserSettings.objects.abulk_create(
        [
            UserSettings(
                user=profile,
                background=config.DEFAULT_BACKGROUND,
                border=config.DEFAULT_BORDER,
                xp_colour=config.DEFAULT_XP_COLOUR,
                blur=5,
            )
            for profile in created
        ]
    )
    return len(created)


async def rename_member(guild_id: int, user_id: int, name: str) -> bool:
    """Store a new member name. Returns True only when the name changed."""
    updated = (
        await UserProfile.objects.filter(guild_id=guild_id, user_id=user_id)
        .exclude(user_name=name)
        .aupdate(user_name=name)
    )
    return updated > 0


async def get_main_channel(guild_id: int) -> int | None:
    """Return the id of the guild's main channel, if one is set."""
    profile = await GuildProfile.objects.filter(guild_id=guild_id).afirst()
    return profile.main_channel_id if profile is not None else None


async def set_main_channel(guild_id: int, channel_id: int | None) -> bool:
    """Set or clear the guild's main channel. Returns True only when it changed."""
    try:
        profile = await GuildProfile.objects.aget(guild_id=guild_id)
    except GuildProfile.DoesNotExist as exc:
        raise GuildNotRegistered(guild_id) from exc

    if profile.main_channel_id == channel_id:
        return False
    profile.main_channel_id = channel_id
    await profile.asave(update_fields=["main_channel_id"])
    return True
