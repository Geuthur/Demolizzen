# Standard Library
from unittest.mock import MagicMock, patch

# Django
from django.test import SimpleTestCase, TestCase

# Demolizzen
from demolizzen import config
from demolizzen.models import GuildProfile, UserProfile, UserSettings
from demolizzen.services import guilds, levels
from demolizzen.services.errors import GuildNotRegistered
from demolizzen.services.levels import Progress, XpResult


def dice(*values):
    rng = MagicMock()
    rng.randint = MagicMock(side_effect=list(values))
    return rng


class FormulaTest(SimpleTestCase):
    def test_level_for(self):
        cases = {0: 1, 99: 1, 100: 2, 299: 2, 300: 3, 599: 3, 600: 4, 100_000: 45}
        for xp, level in cases.items():
            with self.subTest(xp=xp):
                self.assertEqual(levels.level_for(xp), level)

    def test_xp_for_level(self):
        self.assertEqual(
            [levels.xp_for_level(level) for level in (1, 2, 3, 4)], [0, 100, 300, 600]
        )

    def test_level_boundaries_agree(self):
        for level in range(1, 60):
            start = levels.xp_for_level(level)
            self.assertEqual(levels.level_for(start), level)
            if start:
                self.assertEqual(levels.level_for(start - 1), level - 1)

    def test_progress(self):
        self.assertEqual(levels.progress(150), Progress(2, 50, 200, 25))
        self.assertEqual(levels.progress(0), Progress(1, 0, 100, 0))


class MessageXpTest(SimpleTestCase):
    def test_missed_chance_gives_nothing(self):
        with (
            patch.object(config, "XP_CHANCE", True),
            patch.object(config, "XP_CHANCE_RATE", 2),
        ):
            self.assertEqual(levels.message_xp(5, dice(1)), 0)

    def test_normal_gives_the_fixed_amount(self):
        with (
            patch.object(config, "XP_CHANCE", False),
            patch.object(config, "XP_TYPE", "normal"),
        ):
            self.assertEqual(levels.message_xp(5, dice()), config.XP_NORMAL_AMOUNT)

    def test_words_gives_the_word_count(self):
        with (
            patch.object(config, "XP_CHANCE", False),
            patch.object(config, "XP_TYPE", "Words"),
        ):
            self.assertEqual(levels.message_xp(7, dice()), 7)

    def test_ranrange_rolls_between_the_bounds(self):
        rng = dice(2, 6)
        with (
            patch.object(config, "XP_CHANCE", True),
            patch.object(config, "XP_CHANCE_RATE", 2),
            patch.object(config, "XP_TYPE", "ranrange"),
        ):
            self.assertEqual(levels.message_xp(5, rng), 6)

        self.assertEqual(
            rng.randint.call_args.args,
            (config.XP_RANRANGE_MIN, config.XP_RANRANGE_MAX),
        )

    def test_unknown_type_gives_nothing(self):
        with (
            patch.object(config, "XP_CHANCE", False),
            patch.object(config, "XP_TYPE", "nope"),
        ):
            self.assertEqual(levels.message_xp(5, dice()), 0)


class AddXpTest(TestCase):
    async def test_new_member_in_unregistered_guild(self):
        result = await levels.add_xp(1, "Alpha", 10, "alice", 7)

        self.assertEqual(result, XpResult(7, 1, 1, False))
        self.assertTrue(await GuildProfile.objects.filter(guild_id=1).aexists())
        profile = await UserProfile.objects.aget(user_id=10)
        self.assertEqual((profile.experience, profile.user_name), (7, "alice"))
        self.assertTrue(await UserSettings.objects.filter(user=profile).aexists())

    async def test_bookings_add_up_on_the_stored_value(self):
        await levels.add_xp(1, "Alpha", 10, "alice", 7)
        await UserProfile.objects.filter(user_id=10).aupdate(experience=50)

        result = await levels.add_xp(1, "Alpha", 10, "alice", 5)

        self.assertEqual(result.experience, 55)
        self.assertEqual((await UserProfile.objects.aget(user_id=10)).experience, 55)

    async def test_level_up_is_reported_once(self):
        await levels.add_xp(1, "Alpha", 10, "alice", 99)

        up = await levels.add_xp(1, "Alpha", 10, "alice", 1)
        after = await levels.add_xp(1, "Alpha", 10, "alice", 1)

        self.assertEqual(up, XpResult(100, 2, 1, True))
        self.assertEqual(after, XpResult(101, 2, 2, False))
        self.assertEqual((await UserProfile.objects.aget(user_id=10)).level, 2)

    async def test_several_levels_at_once(self):
        result = await levels.add_xp(1, "Alpha", 10, "alice", 650)

        self.assertEqual((result.level, result.previous_level), (4, 1))
        self.assertTrue(result.leveled_up)

    async def test_stored_name_follows_the_member(self):
        await levels.add_xp(1, "Alpha", 10, "alice", 1)

        await levels.add_xp(1, "Alpha", 10, "Alice Cooper", 1)

        self.assertEqual(
            (await UserProfile.objects.aget(user_id=10)).user_name, "Alice Cooper"
        )

    async def test_members_and_guilds_are_separate(self):
        await levels.add_xp(1, "Alpha", 10, "alice", 5)
        await levels.add_xp(1, "Alpha", 11, "bob", 9)
        await levels.add_xp(2, "Beta", 10, "alice", 3)

        self.assertEqual(
            (await UserProfile.objects.aget(user_id=10, guild_id=1)).experience, 5
        )
        self.assertEqual(
            (await UserProfile.objects.aget(user_id=10, guild_id=2)).experience, 3
        )


class CardDataTest(TestCase):
    async def test_unknown_member(self):
        await guilds.ensure_guild(1, "Alpha")

        self.assertIsNone(await levels.get_card_data(1, 10))

    async def test_card_data_with_rank(self):
        await levels.add_xp(1, "Alpha", 10, "alice", 150)
        await levels.add_xp(1, "Alpha", 11, "bob", 400)
        await levels.add_xp(1, "Alpha", 12, "carol", 120)
        await levels.add_xp(2, "Beta", 13, "dave", 9000)

        data = await levels.get_card_data(1, 10)

        self.assertEqual(
            (data.user_name, data.experience, data.level), ("alice", 150, 2)
        )
        self.assertEqual(data.rank, 2)
        self.assertEqual(data.background, config.DEFAULT_BACKGROUND)
        self.assertEqual(data.border, config.DEFAULT_BORDER)
        self.assertEqual(data.xp_colour, config.DEFAULT_XP_COLOUR)

    async def test_missing_settings_are_created(self):
        await guilds.ensure_guild(1, "Alpha")
        profile = await UserProfile.objects.acreate(
            guild_id=1, user_id=10, user_name="alice"
        )

        data = await levels.get_card_data(1, 10)

        self.assertEqual(data.blur, 5)
        self.assertTrue(await UserSettings.objects.filter(user=profile).aexists())


class LeaderboardTest(TestCase):
    async def test_order_and_scope(self):
        await levels.add_xp(1, "Alpha", 10, "alice", 150)
        await levels.add_xp(1, "Alpha", 11, "bob", 400)
        await levels.add_xp(1, "Alpha", 12, "carol", 120)
        await levels.add_xp(2, "Beta", 13, "dave", 9000)

        board = await levels.leaderboard(1)

        self.assertEqual(board, [("bob", 3, 400), ("alice", 2, 150), ("carol", 2, 120)])

    async def test_empty_guild(self):
        self.assertEqual(await levels.leaderboard(99), [])


class AnnouncementTest(TestCase):
    async def test_default_is_enabled_without_channel(self):
        await guilds.ensure_guild(1, "Alpha")

        self.assertEqual(
            await levels.get_announcement(1), levels.Announcement(True, None)
        )
        self.assertEqual(
            await levels.get_announcement(99), levels.Announcement(True, None)
        )

    async def test_switching_off_and_channel(self):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.set_main_channel(1, 555)

        await levels.set_announcements(1, False)

        self.assertEqual(
            await levels.get_announcement(1), levels.Announcement(False, 555)
        )

    async def test_unregistered_guild_cannot_be_switched(self):
        with self.assertRaises(GuildNotRegistered):
            await levels.set_announcements(99, False)
