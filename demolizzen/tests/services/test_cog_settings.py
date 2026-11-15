# Standard Library
from unittest.mock import patch

# Django
from django.test import TestCase

# Demolizzen
from demolizzen.models import GuildProfile, GuildSettings
from demolizzen.services import cog_settings, guilds
from demolizzen.services.errors import (
    CogNotToggleable,
    DependencyConflict,
    GuildNotRegistered,
    UnknownCog,
)


async def stored(guild_id: int = 1) -> GuildSettings:
    return await GuildSettings.objects.aget(guild_id=guild_id)


class CogSettingsTestCase(TestCase):
    def setUp(self):
        cog_settings.invalidate()


class DefaultsTest(CogSettingsTestCase):
    async def test_unregistered_guild_is_all_enabled_and_creates_no_rows(self):
        self.assertTrue(await cog_settings.is_enabled(99, "ticket"))
        self.assertEqual(await GuildProfile.objects.acount(), 0)
        self.assertEqual(await GuildSettings.objects.acount(), 0)

    async def test_null_fields_mean_enabled(self):
        await guilds.ensure_guild(1, "Alpha")

        self.assertIsNone((await stored()).disabled_cogs)
        self.assertTrue(await cog_settings.is_enabled(1, "games"))
        self.assertTrue(all((await cog_settings.get_states(1)).values()))

    async def test_get_states_lists_only_toggleable_cogs_in_order(self):
        states = await cog_settings.get_states(1)

        self.assertNotIn("core", states)
        self.assertNotIn("panel", states)
        self.assertEqual(list(states)[:3], ["admin", "general", "commands"])

    async def test_unknown_key_raises(self):
        with self.assertRaises(UnknownCog):
            await cog_settings.is_enabled(1, "nope")


class ToggleTest(CogSettingsTestCase):
    async def asetup(self):
        await guilds.ensure_guild(1, "Alpha")

    async def test_disable_and_enable_roundtrip(self):
        await self.asetup()

        await cog_settings.set_enabled(1, "games", False)
        self.assertFalse(await cog_settings.is_enabled(1, "games"))
        self.assertEqual((await stored()).disabled_cogs, ["games"])

        await cog_settings.set_enabled(1, "games", True)
        self.assertTrue(await cog_settings.is_enabled(1, "games"))
        self.assertEqual((await stored()).disabled_cogs, [])

    async def test_set_enabled_returns_changed_keys(self):
        await self.asetup()

        self.assertEqual(await cog_settings.set_enabled(1, "ticket", False), ["ticket"])

    async def test_other_guild_is_unaffected(self):
        await self.asetup()
        await guilds.ensure_guild(2, "Beta")

        await cog_settings.set_enabled(1, "games", False)

        self.assertTrue(await cog_settings.is_enabled(2, "games"))

    async def test_fixed_cog_cannot_be_disabled(self):
        await self.asetup()

        with self.assertRaises(CogNotToggleable):
            await cog_settings.set_enabled(1, "core", False)

    async def test_unknown_cog_cannot_be_set(self):
        await self.asetup()

        with self.assertRaises(UnknownCog):
            await cog_settings.set_enabled(1, "nope", False)

    async def test_set_enabled_unregistered_guild_raises(self):
        with self.assertRaises(GuildNotRegistered):
            await cog_settings.set_enabled(99, "games", False)

    async def test_profile_without_settings_row_gets_one(self):
        await GuildProfile.objects.acreate(guild_id=5, guild_name="Bare")

        await cog_settings.set_enabled(5, "games", False)

        self.assertEqual((await stored(5)).disabled_cogs, ["games"])

    async def test_sequential_toggles_keep_both(self):
        await self.asetup()
        await cog_settings.set_enabled(1, "games", False)
        # Another process (the future web panel) writes past this process' cache.
        await GuildSettings.objects.filter(guild_id=1).aupdate(
            disabled_cogs=["games", "shop"]
        )

        await cog_settings.set_enabled(1, "killmail", False)

        self.assertEqual(
            sorted((await stored()).disabled_cogs), ["games", "killmail", "shop"]
        )


class StoredDataTest(CogSettingsTestCase):
    async def test_fixed_cog_in_db_list_stays_enabled(self):
        await guilds.ensure_guild(1, "Alpha")
        await GuildSettings.objects.filter(guild_id=1).aupdate(disabled_cogs=["core"])

        self.assertTrue(await cog_settings.is_enabled(1, "core"))

    async def test_garbage_in_json_is_ignored(self):
        await guilds.ensure_guild(1, "Alpha")
        for garbage in ({"x": 1}, ["removed_cog", 5, None], "games", 7):
            with self.subTest(garbage=garbage):
                await GuildSettings.objects.filter(guild_id=1).aupdate(
                    disabled_cogs=garbage, enabled_cogs=garbage
                )
                cog_settings.invalidate()

                self.assertTrue(all((await cog_settings.get_states(1)).values()))

    async def test_enabled_list_overrides_disabled_list(self):
        await guilds.ensure_guild(1, "Alpha")
        await GuildSettings.objects.filter(guild_id=1).aupdate(
            disabled_cogs=["ticket"], enabled_cogs=["ticket"]
        )

        self.assertTrue(await cog_settings.is_enabled(1, "ticket"))


class CacheTest(CogSettingsTestCase):
    async def test_external_change_visible_after_ttl(self):
        await guilds.ensure_guild(1, "Alpha")
        with patch.object(cog_settings, "_clock", return_value=1000.0):
            self.assertTrue(await cog_settings.is_enabled(1, "games"))
            await GuildSettings.objects.filter(guild_id=1).aupdate(
                disabled_cogs=["games"]
            )
            self.assertTrue(await cog_settings.is_enabled(1, "games"))

        with patch.object(
            cog_settings, "_clock", return_value=1000.0 + cog_settings.CACHE_TTL_SECONDS + 1
        ):
            self.assertFalse(await cog_settings.is_enabled(1, "games"))

    async def test_ttl_is_sixty_seconds(self):
        self.assertEqual(cog_settings.CACHE_TTL_SECONDS, 60)

    async def test_invalidate_single_guild(self):
        await guilds.ensure_guild(1, "Alpha")
        self.assertTrue(await cog_settings.is_enabled(1, "games"))
        await GuildSettings.objects.filter(guild_id=1).aupdate(disabled_cogs=["games"])

        cog_settings.invalidate(1)

        self.assertFalse(await cog_settings.is_enabled(1, "games"))

    async def test_enabled_guild_ids(self):
        for guild_id in (1, 2, 3):
            await guilds.ensure_guild(guild_id, f"G{guild_id}")
        await cog_settings.set_enabled(2, "killmail", False)

        self.assertEqual(
            await cog_settings.enabled_guild_ids("killmail", [1, 2, 3, 99]), {1, 3, 99}
        )


class DependencyTest(CogSettingsTestCase):
    async def asetup(self):
        await guilds.ensure_guild(1, "Alpha")

    async def test_disable_with_active_dependents_raises(self):
        await self.asetup()

        with self.assertRaises(DependencyConflict) as cm:
            await cog_settings.set_enabled(1, "banksystem", False)

        self.assertEqual(cm.exception.key, "banksystem")
        self.assertFalse(cm.exception.enabled)
        self.assertEqual(cm.exception.affected, ["economy", "shop", "games"])
        self.assertTrue(await cog_settings.is_enabled(1, "banksystem"))

    async def test_disable_cascade_disables_dependents(self):
        await self.asetup()

        changed = await cog_settings.set_enabled(1, "banksystem", False, cascade=True)

        self.assertEqual(changed, ["banksystem", "economy", "shop", "games"])
        for key in changed:
            self.assertFalse(await cog_settings.is_enabled(1, key), key)

    async def test_disable_only_lists_active_dependents(self):
        await self.asetup()
        await cog_settings.set_enabled(1, "games", False)

        with self.assertRaises(DependencyConflict) as cm:
            await cog_settings.set_enabled(1, "banksystem", False)

        self.assertEqual(cm.exception.affected, ["economy", "shop"])

    async def test_disable_without_active_dependents_needs_no_cascade(self):
        await self.asetup()
        for key in ("economy", "shop", "games"):
            await cog_settings.set_enabled(1, key, False)

        self.assertEqual(
            await cog_settings.set_enabled(1, "banksystem", False), ["banksystem"]
        )

    async def test_enable_with_disabled_requirement_raises(self):
        await self.asetup()
        await cog_settings.set_enabled(1, "banksystem", False, cascade=True)

        with self.assertRaises(DependencyConflict) as cm:
            await cog_settings.set_enabled(1, "games", True)

        self.assertTrue(cm.exception.enabled)
        self.assertEqual(cm.exception.affected, ["banksystem"])
        self.assertFalse(await cog_settings.is_enabled(1, "games"))

    async def test_enable_cascade_enables_requirement(self):
        await self.asetup()
        await cog_settings.set_enabled(1, "banksystem", False, cascade=True)

        changed = await cog_settings.set_enabled(1, "games", True, cascade=True)

        self.assertEqual(changed, ["games", "banksystem"])
        self.assertTrue(await cog_settings.is_enabled(1, "banksystem"))
        self.assertFalse(await cog_settings.is_enabled(1, "shop"))
