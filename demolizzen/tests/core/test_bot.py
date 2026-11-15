# Standard Library
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

# Django
from django.test import SimpleTestCase, TestCase

# Demolizzen
from demolizzen.core.bot import Demolizzen
from demolizzen.models import GuildProfile
from demolizzen.services import guilds
from demolizzen.tests.helpers import make_guild

MODULE = "demolizzen.core.bot"


def _fake_session():
    session = MagicMock()
    session.close = AsyncMock()
    session.closed = False
    return session


def _fake_openapi():
    return MagicMock()


class BotConstructionTest(SimpleTestCase):
    def test_init_has_no_side_effects(self):
        with (
            patch(f"{MODULE}.aiohttp.ClientSession") as session,
            patch.object(Demolizzen, "load_extension") as load,
        ):
            bot = Demolizzen()

        session.assert_not_called()
        load.assert_not_called()
        self.assertIsNone(bot.session)
        self.assertIsNone(bot.esi_data)

    def test_load_preload_extensions_reports_failures(self):
        bot = Demolizzen()
        bot.preload_ext = ["core", "does_not_exist"]

        result = bot.load_preload_extensions()

        self.assertIsNone(result["core"])
        self.assertIsInstance(result["does_not_exist"], Exception)
        self.assertIn("Core", bot.cogs)


class BotStartTest(SimpleTestCase):
    async def test_start_without_token_raises(self):
        bot = Demolizzen()
        bot.token = None

        with self.assertRaisesMessage(RuntimeError, "Token must be set"):
            await bot.start()

    async def test_start_creates_resources_then_connects(self):
        bot = Demolizzen()
        bot.preload_ext = []
        with (
            patch(f"{MODULE}.aiohttp.ClientSession", return_value=_fake_session()),
            patch(f"{MODULE}.OpenAPI", return_value=_fake_openapi()),
            patch(
                "discord.ext.commands.Bot.start", new_callable=AsyncMock
            ) as parent_start,
        ):
            await bot.start("tok")

            self.assertIsNotNone(bot.session)
            self.assertIsNotNone(bot.esi_data)
            parent_start.assert_awaited_once_with("tok", reconnect=True)
            await bot.close()

    async def test_start_falls_back_to_configured_token(self):
        bot = Demolizzen()
        bot.preload_ext = []
        bot.token = "configured"
        with (
            patch(f"{MODULE}.aiohttp.ClientSession", return_value=_fake_session()),
            patch(f"{MODULE}.OpenAPI", return_value=_fake_openapi()),
            patch(
                "discord.ext.commands.Bot.start", new_callable=AsyncMock
            ) as parent_start,
        ):
            await bot.start()

            parent_start.assert_awaited_once_with("configured", reconnect=True)
            await bot.close()

    async def test_close_is_idempotent(self):
        bot = Demolizzen()
        bot.preload_ext = []
        session = _fake_session()
        with (
            patch(f"{MODULE}.aiohttp.ClientSession", return_value=session),
            patch(f"{MODULE}.OpenAPI", return_value=_fake_openapi()),
            patch("discord.ext.commands.Bot.start", new_callable=AsyncMock),
        ):
            await bot.start("tok")
            await bot.close()
            await bot.close()

        session.close.assert_awaited_once()
        self.assertIsNone(bot.session)
        self.assertIsNone(bot.esi_data)

    async def test_close_stops_the_esi_worker_threads(self):
        bot = Demolizzen()
        bot.preload_ext = []
        openapi = _fake_openapi()
        with (
            patch(f"{MODULE}.aiohttp.ClientSession", return_value=_fake_session()),
            patch(f"{MODULE}.OpenAPI", return_value=openapi),
            patch("discord.ext.commands.Bot.start", new_callable=AsyncMock),
        ):
            await bot.start("tok")
            await bot.close()

        openapi.close.assert_called_once()

    async def test_close_before_start_is_safe(self):
        bot = Demolizzen()

        await bot.close()

        self.assertIsNone(bot.session)


class BotReadyTest(TestCase):
    async def test_on_ready_updates_changed_guild_names(self):
        await guilds.ensure_guild(1, "Old Name")
        bot = Demolizzen()
        with (
            patch.object(
                Demolizzen,
                "guilds",
                new_callable=PropertyMock,
                return_value=[make_guild(1, "New Name")],
            ),
            patch.object(Demolizzen, "get_all_members", return_value=iter(())),
            patch.object(Demolizzen, "sync_commands", new_callable=AsyncMock),
            patch.object(Demolizzen, "change_presence", new_callable=AsyncMock),
        ):
            await bot.on_ready()

        self.assertEqual(
            (await GuildProfile.objects.aget(guild_id=1)).guild_name, "New Name"
        )


class BotConnectTest(SimpleTestCase):
    async def test_banner_is_printed_on_first_connect_only(self):
        bot = Demolizzen()
        with (
            patch.object(
                Demolizzen, "invite_url", new_callable=PropertyMock, return_value="url"
            ),
            patch("builtins.print") as printed,
        ):
            await bot.on_connect()
            first = [str(call.args[0]) for call in printed.call_args_list if call.args]
            printed.reset_mock()
            await bot.on_connect()
            second = [str(call.args[0]) for call in printed.call_args_list if call.args]

        self.assertTrue(any("Demolizzen - The Discord Bot" in line for line in first))
        self.assertEqual(second, ["Reconnected."])


class ModulesAreAlwaysLoadedTest(SimpleTestCase):
    """However the bot is started, it must not run without its modules.

    A bot without modules has no commands, and syncing "no commands" deletes
    every slash command registered with Discord.
    """

    def test_run_loads_the_modules_when_the_caller_did_not(self):
        bot = Demolizzen()
        bot.preload_ext = ["core", "games", "banksystem"]

        with (
            patch("discord.ext.tasks.Loop.start"),
            patch("discord.ext.commands.Bot.run") as parent_run,
        ):
            bot.run()

        parent_run.assert_called_once_with()
        self.assertIsNotNone(bot.get_cog("Core"))
        self.assertIsNotNone(bot.get_cog("Games"))
        self.assertTrue(bot.pending_application_commands)

    def test_run_does_not_load_the_modules_twice(self):
        bot = Demolizzen()
        bot.preload_ext = ["core"]
        with patch("discord.ext.tasks.Loop.start"):
            bot.load_preload_extensions()

        with (
            patch("discord.ext.commands.Bot.run"),
            patch.object(
                Demolizzen, "load_extension", side_effect=AssertionError("again")
            ),
        ):
            bot.run()

        self.assertIsNotNone(bot.get_cog("Core"))

    async def test_start_loads_the_modules_when_the_caller_did_not(self):
        bot = Demolizzen()
        bot.preload_ext = ["core"]

        with (
            patch("discord.ext.tasks.Loop.start"),
            patch(f"{MODULE}.aiohttp.ClientSession", return_value=_fake_session()),
            patch(f"{MODULE}.OpenAPI", return_value=_fake_openapi()),
            patch("discord.ext.commands.Bot.start", new_callable=AsyncMock),
        ):
            await bot.start("tok")
            await bot.close()

        self.assertIsNotNone(bot.get_cog("Core"))


class CommandSyncTest(TestCase):
    async def ready(self, bot):
        with (
            patch.object(
                Demolizzen, "guilds", new_callable=PropertyMock, return_value=[]
            ),
            patch.object(Demolizzen, "get_all_members", return_value=iter(())),
            patch.object(Demolizzen, "change_presence", new_callable=AsyncMock),
            patch.object(Demolizzen, "sync_commands", new_callable=AsyncMock) as sync,
            patch("builtins.print") as printed,
        ):
            await bot.on_ready()
        return sync, " ".join(
            str(call.args[0]) for call in printed.call_args_list if call.args
        )

    async def test_commands_are_synced_when_modules_are_loaded(self):
        bot = Demolizzen()
        bot.preload_ext = ["core"]
        with patch("discord.ext.tasks.Loop.start"):
            bot.load_preload_extensions()

        sync, _ = await self.ready(bot)

        sync.assert_awaited_once()

    async def test_an_empty_command_list_is_never_synced(self):
        bot = Demolizzen()

        with self.assertLogs(level="ERROR") as logs:
            sync, printed = await self.ready(bot)

        sync.assert_not_awaited()
        self.assertIn("NOT synced", printed)
        self.assertIn("left untouched", " ".join(logs.output))
