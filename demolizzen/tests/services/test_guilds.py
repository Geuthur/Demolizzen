# Django
from django.test import TestCase

# Demolizzen
from demolizzen import config
from demolizzen.models import (
    GuildBankSettings,
    GuildProfile,
    GuildSettings,
    GuildTicketSettings,
    UserProfile,
    UserSettings,
)
from demolizzen.services import guilds
from demolizzen.services.errors import GuildNotRegistered


class EnsureGuildTest(TestCase):
    async def test_creates_profile_and_settings(self):
        profile, created = await guilds.ensure_guild(1, "Alpha")

        self.assertTrue(created)
        self.assertEqual(profile.guild_name, "Alpha")
        self.assertTrue(await GuildSettings.objects.filter(guild_id=1).aexists())
        self.assertTrue(await GuildBankSettings.objects.filter(guild_id=1).aexists())
        self.assertTrue(await GuildTicketSettings.objects.filter(guild_id=1).aexists())

    async def test_is_idempotent(self):
        await guilds.ensure_guild(1, "Alpha")

        _, created = await guilds.ensure_guild(1, "Alpha")

        self.assertFalse(created)
        self.assertEqual(await GuildProfile.objects.acount(), 1)
        self.assertEqual(await GuildSettings.objects.acount(), 1)

    async def test_existing_profile_without_settings_gets_them(self):
        await GuildProfile.objects.acreate(guild_id=1, guild_name="Alpha")

        _, created = await guilds.ensure_guild(1, "Alpha")

        self.assertFalse(created)
        self.assertTrue(await GuildSettings.objects.filter(guild_id=1).aexists())


class RenameGuildTest(TestCase):
    async def test_changed_name_is_saved(self):
        await guilds.ensure_guild(1, "Alpha")

        self.assertTrue(await guilds.rename_guild(1, "Beta"))
        self.assertEqual(
            (await GuildProfile.objects.aget(guild_id=1)).guild_name, "Beta"
        )

    async def test_same_name_is_no_change(self):
        await guilds.ensure_guild(1, "Alpha")

        self.assertFalse(await guilds.rename_guild(1, "Alpha"))

    async def test_unknown_guild_is_no_change(self):
        self.assertFalse(await guilds.rename_guild(99, "Ghost"))


class RemoveGuildTest(TestCase):
    async def test_remove_guild_deletes_profile_and_members(self):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.ensure_members(1, [(10, "a")])

        self.assertTrue(await guilds.remove_guild(1))
        self.assertEqual(await GuildProfile.objects.acount(), 0)
        self.assertEqual(await UserProfile.objects.acount(), 0)

    async def test_remove_unknown_guild(self):
        self.assertFalse(await guilds.remove_guild(99))

    async def test_remove_missing_guilds(self):
        for guild_id in (1, 2, 3):
            await guilds.ensure_guild(guild_id, f"G{guild_id}")
        await guilds.ensure_members(2, [(10, "a")])

        removed = await guilds.remove_missing_guilds([1, 3])

        self.assertEqual(removed, [2])
        self.assertEqual(
            sorted([g.guild_id async for g in GuildProfile.objects.all()]), [1, 3]
        )
        self.assertEqual(await UserProfile.objects.filter(guild_id=2).acount(), 0)

    async def test_remove_missing_guilds_with_nothing_missing(self):
        await guilds.ensure_guild(1, "Alpha")

        self.assertEqual(await guilds.remove_missing_guilds([1, 2]), [])


class EnsureMembersTest(TestCase):
    async def test_creates_profiles_with_default_settings(self):
        await guilds.ensure_guild(1, "Alpha")

        created = await guilds.ensure_members(1, [(10, "a"), (11, "b")])

        self.assertEqual(created, 2)
        settings = await UserSettings.objects.aget(user__user_id=10)
        self.assertEqual(settings.background, config.DEFAULT_BACKGROUND)
        self.assertEqual(settings.border, config.DEFAULT_BORDER)
        self.assertEqual(settings.xp_colour, config.DEFAULT_XP_COLOUR)
        self.assertEqual(settings.blur, 5)

    async def test_is_idempotent(self):
        await guilds.ensure_guild(1, "Alpha")

        self.assertEqual(await guilds.ensure_members(1, [(10, "a"), (11, "b")]), 2)
        self.assertEqual(await guilds.ensure_members(1, [(10, "a"), (12, "c")]), 1)
        self.assertEqual(await UserProfile.objects.filter(guild_id=1).acount(), 3)
        self.assertEqual(
            await UserSettings.objects.filter(user__guild_id=1).acount(), 3
        )

    async def test_duplicate_input_creates_one_profile(self):
        await guilds.ensure_guild(1, "Alpha")

        self.assertEqual(await guilds.ensure_members(1, [(10, "a"), (10, "a")]), 1)
        self.assertEqual(await UserProfile.objects.acount(), 1)

    async def test_same_user_in_two_guilds(self):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.ensure_guild(2, "Beta")
        await guilds.ensure_members(1, [(10, "a")])

        self.assertEqual(await guilds.ensure_members(2, [(10, "a")]), 1)

    async def test_empty_input(self):
        await guilds.ensure_guild(1, "Alpha")

        self.assertEqual(await guilds.ensure_members(1, []), 0)

    async def test_unknown_guild_raises(self):
        with self.assertRaises(GuildNotRegistered):
            await guilds.ensure_members(99, [(10, "a")])


class RenameMemberTest(TestCase):
    async def test_changed_name_is_saved(self):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.ensure_members(1, [(10, "old")])

        self.assertTrue(await guilds.rename_member(1, 10, "new"))
        self.assertEqual((await UserProfile.objects.aget(user_id=10)).user_name, "new")

    async def test_same_name_is_no_change(self):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.ensure_members(1, [(10, "old")])

        self.assertFalse(await guilds.rename_member(1, 10, "old"))

    async def test_unknown_member_is_no_change(self):
        await guilds.ensure_guild(1, "Alpha")

        self.assertFalse(await guilds.rename_member(1, 10, "new"))


class MainChannelTest(TestCase):
    async def test_set_and_unset(self):
        await guilds.ensure_guild(1, "Alpha")

        self.assertTrue(await guilds.set_main_channel(1, 555))
        self.assertEqual(
            (await GuildProfile.objects.aget(guild_id=1)).main_channel_id, 555
        )
        self.assertTrue(await guilds.set_main_channel(1, None))
        self.assertFalse(await guilds.set_main_channel(1, None))

    async def test_unknown_guild_raises(self):
        with self.assertRaises(GuildNotRegistered):
            await guilds.set_main_channel(99, 555)
