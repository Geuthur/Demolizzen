# Standard Library
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

# Third Party
from PIL import Image

# Discord
import discord

# Django
from django.test import SimpleTestCase, TestCase

# Demolizzen
from demolizzen import config
from demolizzen.cogs import levelsystem as levelsystem_package
from demolizzen.cogs.levelsystem._settings_page import (
    LevelSettingsView,
    build_level_settings_embed,
    level_settings_page,
)
from demolizzen.cogs.levelsystem.levelsystem import Levelsystem
from demolizzen.core import settings_pages
from demolizzen.core.bot import Demolizzen
from demolizzen.models import GuildProfile, UserProfile
from demolizzen.services import cog_settings, guilds, levels
from demolizzen.tests.cogs.level_fakes import FakeResponse, FakeSession, png
from demolizzen.tests.helpers import (
    make_ctx,
    make_guild,
    make_interaction,
    make_member,
)

MODULE = "demolizzen.cogs.levelsystem.levelsystem"


def make_text_channel(channel_id: int, can_send: bool = True):
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = channel_id
    channel.send = AsyncMock()
    channel.permissions_for = MagicMock(return_value=MagicMock(send_messages=can_send))
    return channel


class LevelCogTestCase(TestCase):
    def setUp(self):
        cog_settings.invalidate()
        self.guild = make_guild(1, "Alpha")
        self.guild.me = make_member(2, "bot", bot=True)
        self.main = make_text_channel(555)
        self.system = make_text_channel(556)
        self.channels = {555: self.main, 556: self.system}
        self.guild.get_channel = MagicMock(side_effect=self.channels.get)
        self.guild.system_channel = self.system
        self.alice = make_member(10, "alice", guild=self.guild)
        self.alice.mention = "<@10>"
        self.alice.display_avatar = MagicMock(url="https://cdn.example/avatar.png")
        self.bot = MagicMock()
        self.bot.session = FakeSession(default=png())
        self.cog = Levelsystem(self.bot)

    def message(self, author=None, guild="default", content="hello there"):
        message = MagicMock(spec=discord.Message)
        message.author = author or self.alice
        message.guild = self.guild if guild == "default" else guild
        message.content = content
        return message

    async def say(self, xp: int, **kwargs):
        with patch(f"{MODULE}.levels.message_xp", return_value=xp):
            await self.cog.on_message(self.message(**kwargs))

    async def profile(self) -> UserProfile:
        return await UserProfile.objects.aget(user_id=10, guild_id=1)


class MessageXpTest(LevelCogTestCase):
    async def test_bot_and_dm_messages_earn_nothing(self):
        robot = make_member(99, "robot", bot=True, guild=self.guild)

        await self.say(5, author=robot)
        await self.say(5, guild=None)

        self.assertEqual(await UserProfile.objects.acount(), 0)

    async def test_message_without_xp_touches_no_service(self):
        await guilds.ensure_guild(1, "Alpha")
        await cog_settings.is_enabled(1, "levelsystem")  # warm the switch cache
        with patch(f"{MODULE}.levels.add_xp", new_callable=AsyncMock) as add_xp:
            await self.say(0)

        add_xp.assert_not_awaited()
        self.assertEqual(await UserProfile.objects.acount(), 0)

    async def test_word_count_is_passed_to_the_rule(self):
        with patch(f"{MODULE}.levels.message_xp", return_value=0) as rule:
            await self.cog.on_message(self.message(content="one two  three"))

        self.assertEqual(rule.call_args.args[0], 3)

    async def test_message_adds_xp_and_creates_profile(self):
        await self.say(7)
        await self.say(5)

        profile = await self.profile()
        self.assertEqual(profile.experience, 12)
        self.assertEqual(profile.user_name, "alice")
        self.assertTrue(await GuildProfile.objects.filter(guild_id=1).aexists())

    async def test_disabled_module_earns_nothing(self):
        await guilds.ensure_guild(1, "Alpha")
        await cog_settings.set_enabled(1, "levelsystem", False)

        await self.say(7)

        self.assertEqual(await UserProfile.objects.acount(), 0)


class LevelUpTest(LevelCogTestCase):
    async def level_up(self):
        await self.say(99)
        await self.say(1)

    async def test_level_up_posts_card_to_main_channel(self):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.set_main_channel(1, 555)

        await self.level_up()

        kwargs = self.main.send.await_args.kwargs
        self.assertEqual(kwargs["file"].filename, "level_card.png")
        self.assertEqual(Image.open(kwargs["file"].fp).size, (900, 270))
        self.assertEqual(kwargs["content"], "<@10>,")
        self.system.send.assert_not_awaited()
        self.assertEqual((await self.profile()).level, 2)

    async def test_level_up_falls_back_to_the_system_channel(self):
        await self.level_up()

        self.system.send.assert_awaited_once()

    async def test_no_card_without_a_level_up(self):
        await self.say(5)

        self.system.send.assert_not_awaited()

    async def test_level_up_is_silent_when_announcements_are_off(self):
        await guilds.ensure_guild(1, "Alpha")
        await levels.set_announcements(1, False)

        await self.level_up()

        self.system.send.assert_not_awaited()
        self.assertEqual((await self.profile()).level, 2)

    async def test_level_up_without_channel_or_permission_is_silent(self):
        self.guild.system_channel = None
        await self.level_up()
        self.assertEqual((await self.profile()).level, 2)

        self.guild.system_channel = make_text_channel(557, can_send=False)
        await self.say(250)
        self.guild.system_channel.send.assert_not_awaited()
        self.assertEqual((await self.profile()).level, 3)

    async def test_failed_asset_download_keeps_the_xp(self):
        self.bot.session = FakeSession(default=None)

        with self.assertLogs(MODULE, "WARNING"):
            await self.level_up()

        self.system.send.assert_not_awaited()
        profile = await self.profile()
        self.assertEqual((profile.experience, profile.level), (100, 2))

    async def test_static_images_are_downloaded_once(self):
        await self.level_up()
        first = len(self.bot.session.calls)
        await self.say(250)

        # Only the avatar is fetched again for the second card.
        self.assertEqual(len(self.bot.session.calls) - first, 1)
        self.assertEqual(self.system.send.await_count, 2)


class RankCommandTest(LevelCogTestCase):
    async def rank(self, member):
        ctx = make_ctx(guild=self.guild, author=self.alice)
        await self.cog.rank.callback(self.cog, ctx, member)
        return ctx

    async def test_rank_sends_card(self):
        await self.say(150)

        ctx = await self.rank(self.alice)

        ctx.defer.assert_awaited_once()
        kwargs = ctx.respond.await_args.kwargs
        self.assertEqual(kwargs["file"].filename, "rank_card.png")
        self.assertEqual(Image.open(kwargs["file"].fp).size, (1050, 300))

    async def test_rank_for_unknown_member_tells_user(self):
        stranger = make_member(77, "stranger", guild=self.guild)
        stranger.display_name = "Stranger"

        ctx = await self.rank(stranger)

        embed = ctx.respond.await_args.kwargs["embed"]
        self.assertIn(
            "Stranger is not registered in the leveling system.", embed.description
        )

    async def test_rank_with_failing_images_reports_an_error(self):
        await self.say(150)
        self.bot.session = FakeSession({}, default=None)
        self.bot.session.responses["x"] = FakeResponse(status=500)

        with self.assertLogs(MODULE, "WARNING"):
            ctx = await self.rank(self.alice)

        embed = ctx.respond.await_args.kwargs["embed"]
        self.assertIn("Error generating rank card", embed.description)


class LeaderboardTest(LevelCogTestCase):
    async def test_leaderboard_lists_members_in_order(self):
        await levels.add_xp(1, "Alpha", 10, "alice", 150)
        await levels.add_xp(1, "Alpha", 11, "bob", 400)
        ctx = make_ctx(guild=self.guild, author=self.alice)
        ctx.guild.icon = None

        with patch(f"{MODULE}.Paginator") as paginator:
            paginator.return_value.respond = AsyncMock()
            await self.cog.leaderboard.callback(self.cog, ctx)

        pages = paginator.call_args.kwargs["pages"]
        self.assertEqual(len(pages), 1)
        lines = pages[0].description.splitlines()
        self.assertIn("bob", lines[0])
        self.assertIn("alice", lines[1])

    async def test_empty_leaderboard(self):
        ctx = make_ctx(guild=self.guild, author=self.alice)

        await self.cog.leaderboard.callback(self.cog, ctx)

        self.assertIn("❌", ctx.respond.await_args.kwargs["embed"].description)


class MainChannelRepairTest(LevelCogTestCase):
    async def test_deleted_main_channel_falls_back_to_system_channel(self):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.set_main_channel(1, 555)
        self.main.guild = self.guild

        with patch(f"{MODULE}.get_command_mention", return_value="/guild set_channel"):
            await self.cog.on_guild_channel_delete(self.main)

        self.assertEqual(await guilds.get_main_channel(1), 556)
        self.system.send.assert_awaited_once()

    async def test_other_deleted_channel_changes_nothing(self):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.set_main_channel(1, 555)
        other = make_text_channel(999)
        other.guild = self.guild

        await self.cog.on_guild_channel_delete(other)

        self.assertEqual(await guilds.get_main_channel(1), 555)


class LevelSettingsPageTest(TestCase):
    def setUp(self):
        cog_settings.invalidate()
        self.admin = make_member(10, "admin", manage_guild=True)
        self.guild = make_guild(
            1, "Alpha", members=[make_member(1, "boss"), self.admin]
        )
        self.back = AsyncMock()

    def interaction(self, user=None):
        return make_interaction(guild=self.guild, user=user or self.admin)

    async def make_view(self) -> LevelSettingsView:
        await guilds.ensure_guild(1, "Alpha")
        return LevelSettingsView(1, 10, self.back, await levels.get_announcement(1))

    @staticmethod
    def labels(view):
        return [
            getattr(item, "label", None) or getattr(item, "placeholder", None)
            for item in view.children
        ]

    async def test_controls_and_embed(self):
        view = await self.make_view()

        self.assertEqual(
            self.labels(view),
            ["Level up channel", "Level up posts: On", "Use system channel", "Back"],
        )
        embed = build_level_settings_embed(await levels.get_announcement(1))
        values = {field.name: field.value for field in embed.fields}
        self.assertEqual(values, {"Level up posts": "✅", "Channel": "System channel"})

    async def test_settings_page_toggles_announcements_and_sets_channel(self):
        view = await self.make_view()

        await view.toggle(self.interaction())
        self.assertFalse((await levels.get_announcement(1)).enabled)
        self.assertIn("Level up posts: Off", self.labels(view))

        await view.set_channel(self.interaction(), 555)
        self.assertEqual((await levels.get_announcement(1)).channel_id, 555)
        self.assertEqual(
            {f.name: f.value for f in view.embed().fields}["Channel"], "<#555>"
        )

        await view.set_channel(self.interaction(), None)
        self.assertIsNone((await levels.get_announcement(1)).channel_id)

    async def test_channel_select_is_wired(self):
        view = await self.make_view()
        select = view.children[0]
        picked = MagicMock()
        picked.id = 777

        with patch.object(
            type(select), "values", new_callable=PropertyMock, return_value=[picked]
        ):
            await select.callback(self.interaction())

        self.assertEqual((await levels.get_announcement(1)).channel_id, 777)

    async def test_permission_and_back(self):
        view = await self.make_view()

        self.assertFalse(
            await view.interaction_check(
                self.interaction(make_member(99, manage_guild=True))
            )
        )
        interaction = self.interaction()
        await view.go_back(interaction)
        self.back.assert_awaited_once_with(interaction)

    async def test_page_function(self):
        interaction = self.interaction()

        await level_settings_page(interaction, self.back)

        edit = interaction.response.edit_message.await_args.kwargs
        self.assertIsInstance(edit["view"], LevelSettingsView)
        self.assertEqual(edit["embed"].title, "📈 Levelsystem – Settings")


class LevelExtensionTest(TestCase):
    def setUp(self):
        with patch("discord.ext.tasks.Loop.start"):
            self.bot = Demolizzen()
            self.bot.preload_ext = ["levelsystem"]
            self.results = self.bot.load_preload_extensions()
        self.addCleanup(settings_pages.unregister, "levelsystem")

    def test_levelsystem_has_no_config_command_and_registers_page(self):
        names = {command.name for command in self.bot.pending_application_commands}

        self.assertIsNone(self.results["levelsystem"])
        self.assertNotIn("levelsystem_config", names)
        self.assertLessEqual({"rank", "leaderboard"}, names)
        self.assertIs(settings_pages.get("levelsystem"), level_settings_page)


class LevelSourceTest(SimpleTestCase):
    def test_levelsystem_does_not_import_requests(self):
        folder = Path(levelsystem_package.__file__).parent
        offenders = [
            path.name
            for path in sorted(folder.glob("*.py"))
            if "requests" in path.read_text()
        ]

        self.assertEqual(offenders, [])
        self.assertTrue(config.LEVEL_UP_BACKGROUND)
