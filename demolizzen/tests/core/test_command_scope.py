# Standard Library
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

# Discord
import discord

# Django
from django.test import SimpleTestCase, TestCase

# Demolizzen
from demolizzen.core import command_scope
from demolizzen.core.bot import Demolizzen
from demolizzen.core.command_scope import module_key
from demolizzen.models import GuildSettings
from demolizzen.services import cog_settings, guilds
from demolizzen.tests.core.command_fakes import FakeCommandStore

# One of the servers the Voices of War module declares for its own commands.
ALPHA = 476405195585355776
BRAVO = 2000
CHARLIE = 3000

# core and panel are always on; eveonline and ticket can be switched; vow is a
# single-server module with servers of its own.
MODULES = ["core", "panel", "eveonline", "ticket", "vow"]
GLOBAL = ["bot", "panel"]
SWITCHABLE = ["eve", "ticket"]
VOW = ["create_ticket_button", "transport"]
# Modules outside the registry that belong to single servers.
SINGLE_SERVER = ("geuthur/", "vow/", "automod/", "token/")
DECLARED_SERVERS = re.compile(r"guild_ids\s*=\s*\[")


def load(modules) -> Demolizzen:
    bot = Demolizzen()
    bot.preload_ext = list(modules)
    with patch("discord.ext.tasks.Loop.start"), patch("builtins.print"):
        bot.load_preload_extensions()
    return bot


def command(bot: Demolizzen, name: str):
    return next(cmd for cmd in bot.pending_application_commands if cmd.name == name)


class ScopeTestCase(TestCase):
    modules = MODULES

    def setUp(self):
        cog_settings.invalidate()
        self.now = 1000.0
        self.enterContext(patch.object(command_scope, "_clock", lambda: self.now))
        self.servers = [MagicMock(id=ALPHA), MagicMock(id=BRAVO)]
        self.enterContext(
            patch.object(
                Demolizzen,
                "guilds",
                new_callable=PropertyMock,
                return_value=self.servers,
            )
        )
        self.enterContext(
            patch.object(
                Demolizzen,
                "user",
                new_callable=PropertyMock,
                return_value=MagicMock(id=990),
            )
        )
        self.bot = load(self.modules)
        self.store = FakeCommandStore()
        self.bot.http = self.store
        self.scope = self.bot.command_scope

    async def switch_elsewhere(self, guild_id: int, *off: str) -> None:
        """Change the modules of a server the way the web panel does: in the
        database, without this process hearing of it."""
        await guilds.ensure_guild(guild_id, f"Server {guild_id}")
        await GuildSettings.objects.filter(guild_id=guild_id).aupdate(
            disabled_cogs=list(off)
        )

    async def click(self, name: str, guild_id: int, command_id: str):
        interaction = MagicMock()
        interaction.type = discord.InteractionType.application_command
        interaction.data = {"id": command_id, "name": name, "guild_id": str(guild_id)}
        interaction.command = None
        with (
            patch.object(self.bot, "get_application_context", AsyncMock()),
            patch.object(self.bot, "invoke_application_command", AsyncMock()),
        ):
            await self.bot.process_application_commands(interaction)
        return interaction.command


class StartTest(ScopeTestCase):
    async def test_always_on_modules_are_global_switchable_ones_per_server(self):
        failed = await self.scope.sync_all()

        self.assertEqual(failed, [])
        self.assertEqual(self.store.names(), GLOBAL)
        self.assertEqual(self.store.names(BRAVO), SWITCHABLE)
        # The single-server module keeps the servers it declares.
        self.assertEqual(self.store.names(ALPHA), sorted(SWITCHABLE + VOW))

    async def test_switched_off_module_is_missing_on_that_server_only(self):
        await self.switch_elsewhere(BRAVO, "ticket")

        await self.scope.sync_all()

        self.assertEqual(self.store.names(BRAVO), ["eve"])
        self.assertIn("ticket", self.store.names(ALPHA))

    async def test_servers_are_registered_before_the_global_list(self):
        # The first start after the change would otherwise leave servers
        # without commands while their turn comes.
        await self.scope.sync_all()

        self.assertEqual(self.store.writes()[-1], None)
        self.assertEqual(set(self.store.writes()[:-1]), {ALPHA, BRAVO})

    async def test_full_sync_is_one_overwrite_per_scope(self):
        await self.scope.sync_all()

        self.assertEqual(
            sorted(self.store.requests, key=str),
            sorted([("put", ALPHA), ("put", BRAVO), ("put", None)], key=str),
        )

    async def test_server_commands_are_sent_without_the_fields_only_global_ones_take(
        self,
    ):
        # Discord refuses "contexts" on a guild command; py-cord leaves it out
        # once the command names servers.
        await self.scope.sync_all()

        self.assertIn("contexts", self.store.commands[None][0])
        for entry in self.store.commands[BRAVO]:
            self.assertNotIn("contexts", entry)
            self.assertNotIn("integration_types", entry)

    async def test_sync_commands_of_the_bot_goes_through_the_scope(self):
        await self.bot.sync_commands()

        self.assertEqual(self.store.names(BRAVO), SWITCHABLE)
        self.assertEqual(self.store.names(), GLOBAL)


class NothingLoadedTest(ScopeTestCase):
    modules = []

    async def test_without_commands_discord_is_left_untouched(self):
        self.store.commands[None] = [{"name": "bot", "id": "1", "type": 1}]
        self.store.commands[BRAVO] = [{"name": "eve", "id": "2", "type": 1}]

        with self.assertLogs(level="ERROR"):
            await self.scope.sync_all()

        self.assertEqual(self.store.requests, [])


class OnlySwitchableLoadedTest(ScopeTestCase):
    modules = ["eveonline"]

    async def test_an_empty_global_list_is_never_sent(self):
        self.store.commands[None] = [{"name": "bot", "id": "1", "type": 1}]

        with self.assertLogs(level="ERROR"):
            await self.scope.sync_all()

        self.assertNotIn(None, self.store.writes())
        self.assertEqual(self.store.names(), ["bot"])
        self.assertEqual(self.store.names(BRAVO), ["eve"])


class RefreshTest(ScopeTestCase):
    async def test_nothing_is_asked_of_discord_while_nothing_changes(self):
        await self.scope.sync_all()
        self.store.requests.clear()

        changed = await self.scope.refresh()

        self.assertEqual(changed, [])
        self.assertEqual(self.store.requests, [])

    async def test_switch_made_elsewhere_reaches_only_that_server(self):
        await self.scope.sync_all()
        self.store.requests.clear()
        await self.switch_elsewhere(BRAVO, "ticket")

        changed = await self.scope.refresh()

        self.assertEqual(changed, [BRAVO])
        self.assertEqual(self.store.names(BRAVO), ["eve"])
        self.assertEqual(self.store.writes(), [BRAVO])
        self.assertIn("ticket", self.store.names(ALPHA))

    async def test_switching_back_on_brings_the_commands_back(self):
        await self.switch_elsewhere(BRAVO, "ticket", "eveonline")
        await self.scope.sync_all()
        self.assertEqual(self.store.names(BRAVO), [])

        await self.switch_elsewhere(BRAVO)
        await self.scope.refresh()

        self.assertEqual(self.store.names(BRAVO), SWITCHABLE)

    async def test_refresh_waits_for_the_first_full_sync(self):
        # The watcher may fire before on_ready has registered everything.
        changed = await self.scope.refresh()

        self.assertEqual(changed, [])
        self.assertEqual(self.store.requests, [])

    async def test_joined_server_gets_its_commands(self):
        await self.scope.sync_all()
        self.servers.append(MagicMock(id=CHARLIE))

        changed = await self.scope.refresh()

        self.assertEqual(changed, [CHARLIE])
        self.assertEqual(self.store.names(CHARLIE), SWITCHABLE)

    async def test_server_that_left_and_came_back_is_registered_again(self):
        await self.scope.sync_all()
        bravo = self.servers.pop()
        await self.scope.refresh()
        self.store.commands.pop(BRAVO)  # Discord drops them with the bot
        self.servers.append(bravo)

        await self.scope.refresh()

        self.assertEqual(self.store.names(BRAVO), SWITCHABLE)

    async def test_sync_guild_registers_one_server_again(self):
        await self.scope.sync_all()
        self.store.commands[BRAVO] = []  # somebody removed them by hand
        self.store.requests.clear()

        done = await self.scope.sync_guild(BRAVO)

        self.assertTrue(done)
        self.assertEqual(self.store.names(BRAVO), SWITCHABLE)
        self.assertEqual(self.store.writes(), [BRAVO])

    async def test_sync_guild_of_an_unknown_server_does_nothing(self):
        await self.scope.sync_all()
        self.store.requests.clear()

        self.assertFalse(await self.scope.sync_guild(CHARLIE))
        self.assertEqual(self.store.requests, [])


class FailureTest(ScopeTestCase):
    async def test_refusing_server_does_not_cost_the_others_their_commands(self):
        self.store.refused = {ALPHA}

        with self.assertLogs(level="WARNING") as logs:
            failed = await self.scope.sync_all()

        self.assertEqual(failed, [ALPHA])
        self.assertEqual(self.store.names(BRAVO), SWITCHABLE)
        self.assertEqual(self.store.names(), GLOBAL)
        # The log says which server and how to repair it.
        self.assertIn(str(ALPHA), " ".join(logs.output))
        self.assertIn("applications.commands", " ".join(logs.output))

    async def test_console_says_when_servers_were_left_out(self):
        self.store.refused = {ALPHA}

        with self.assertLogs(level="WARNING"), patch("builtins.print") as printed:
            await self.bot.sync_commands()

        (line,) = (str(call.args[0]) for call in printed.call_args_list)
        self.assertIn("1 server", line)

    async def test_console_stays_quiet_when_every_server_took_its_commands(self):
        with patch("builtins.print") as printed:
            await self.bot.sync_commands()

        printed.assert_not_called()

    async def test_refused_server_is_tried_again_after_an_hour_not_before(self):
        self.store.refused = {ALPHA}
        with self.assertLogs(level="WARNING"):
            await self.scope.sync_all()
        self.store.refused = set()
        self.store.requests.clear()

        self.now += command_scope.REFUSED_RETRY_SECONDS - 1
        self.assertEqual(await self.scope.refresh(), [])
        self.assertEqual(self.store.requests, [])

        self.now += 2
        self.assertEqual(await self.scope.refresh(), [ALPHA])
        self.assertEqual(self.store.names(ALPHA), sorted(SWITCHABLE + VOW))

    async def test_failing_server_is_tried_again_at_the_next_refresh(self):
        self.store.broken = {BRAVO}
        with self.assertLogs(level="ERROR"):
            failed = await self.scope.sync_all()
        self.assertEqual(failed, [BRAVO])
        self.assertEqual(self.store.names(ALPHA), sorted(SWITCHABLE + VOW))

        self.store.broken = set()
        changed = await self.scope.refresh()

        self.assertEqual(changed, [BRAVO])
        self.assertEqual(self.store.names(BRAVO), SWITCHABLE)

    async def test_server_still_failing_is_not_reported_as_registered(self):
        await self.scope.sync_all()
        await self.switch_elsewhere(BRAVO, "ticket")
        self.store.broken = {BRAVO}

        with self.assertLogs(level="ERROR"):
            changed = await self.scope.refresh()

        self.assertEqual(changed, [])

    async def test_global_list_that_failed_is_sent_again_at_the_next_refresh(self):
        self.store.broken = {None}
        with self.assertLogs(level="ERROR"):
            await self.scope.sync_all()
        self.assertEqual(self.store.names(), [])
        self.assertEqual(self.store.names(BRAVO), SWITCHABLE)

        self.store.broken = set()
        await self.scope.refresh()

        self.assertEqual(self.store.names(), GLOBAL)

    async def test_global_list_is_not_sent_again_once_it_arrived(self):
        await self.scope.sync_all()
        self.store.requests.clear()
        await self.switch_elsewhere(BRAVO, "ticket")

        await self.scope.refresh()

        self.assertEqual(self.store.writes(), [BRAVO])


class RoutingTest(ScopeTestCase):
    async def test_a_command_is_found_under_each_servers_own_id(self):
        await self.scope.sync_all()
        alpha_id = self.store.command_id("eve", ALPHA)
        bravo_id = self.store.command_id("eve", BRAVO)
        self.assertNotEqual(alpha_id, bravo_id)
        eve = command(self.bot, "eve")

        self.assertIs(await self.click("eve", ALPHA, alpha_id), eve)
        self.assertIs(await self.click("eve", BRAVO, bravo_id), eve)

    async def test_command_id_is_the_one_of_the_server_it_is_asked_for(self):
        await self.scope.sync_all()
        eve, panel = command(self.bot, "eve"), command(self.bot, "panel")

        self.assertEqual(
            self.scope.command_id(eve, ALPHA), int(self.store.command_id("eve", ALPHA))
        )
        self.assertEqual(
            self.scope.command_id(eve, BRAVO), int(self.store.command_id("eve", BRAVO))
        )
        # A global command has one id everywhere.
        self.assertEqual(
            self.scope.command_id(panel, BRAVO), int(self.store.command_id("panel"))
        )

    async def test_command_has_no_id_where_its_module_is_off(self):
        await self.switch_elsewhere(BRAVO, "eveonline")
        await self.scope.sync_all()

        self.assertIsNone(self.scope.command_id(command(self.bot, "eve"), BRAVO))
        self.assertIsNone(self.scope.command_id(command(self.bot, "eve"), None))

    async def test_reloaded_module_leaves_no_route_to_its_old_commands(self):
        await self.scope.sync_all()
        old = command(self.bot, "eve")
        bravo_id = self.store.command_id("eve", BRAVO)
        with patch("discord.ext.tasks.Loop.start"):
            self.bot.reload_extension("demolizzen.cogs.eveonline")
        # This server cannot be registered again right now, so nothing
        # overwrites its route.
        self.store.broken = {BRAVO}
        with self.assertLogs(level="ERROR"):
            await self.scope.sync_all()

        found = await self.click("eve", BRAVO, bravo_id)

        self.assertIsNot(found, old)
        self.assertIs(found, command(self.bot, "eve"))


class StaleEntryTest(ScopeTestCase):
    """A Discord client can still list a command that is registered no more:
    the global entry from before commands went per server, or one of a module
    that was just switched off. Its click arrives under an id the bot has no
    route for."""

    def stale_click(self, name: str, guild_id: int | None = BRAVO):
        interaction = MagicMock()
        interaction.type = discord.InteractionType.application_command
        # A global entry: Discord sends no guild_id inside the data.
        interaction.data = {"id": "1", "name": name}
        interaction.guild_id = guild_id
        interaction.command = None
        interaction.response.send_message = AsyncMock()
        return interaction

    async def handle(self, interaction):
        with (
            patch.object(self.bot, "get_application_context", AsyncMock()) as context,
            patch.object(self.bot, "invoke_application_command", AsyncMock()) as run,
        ):
            await self.bot.on_unknown_application_command(interaction)
        return context, run

    async def test_py_cord_has_no_route_for_the_old_global_entry(self):
        await self.scope.sync_all()
        interaction = self.stale_click("eve")

        with patch.object(self.bot, "dispatch") as dispatch:
            await self.bot.process_application_commands(interaction)

        dispatch.assert_called_once_with("unknown_application_command", interaction)

    async def test_old_entry_of_a_per_server_command_still_runs_it(self):
        await self.scope.sync_all()
        interaction = self.stale_click("eve")

        context, run = await self.handle(interaction)

        self.assertIs(interaction.command, command(self.bot, "eve"))
        run.assert_awaited_once_with(context.return_value)
        interaction.response.send_message.assert_not_awaited()

    async def test_old_entry_of_a_switched_off_module_reaches_its_refusal(self):
        # Running it is what answers "this module is switched off": the cog
        # check refuses. Silence would be "The application did not respond".
        await self.switch_elsewhere(BRAVO, "eveonline")
        await self.scope.sync_all()
        interaction = self.stale_click("eve")

        _, run = await self.handle(interaction)

        self.assertIs(interaction.command, command(self.bot, "eve"))
        run.assert_awaited_once()

    async def test_command_nobody_knows_is_answered_not_ignored(self):
        await self.scope.sync_all()
        interaction = self.stale_click("gone")

        _, run = await self.handle(interaction)

        run.assert_not_awaited()
        text = interaction.response.send_message.await_args.args[0]
        self.assertIn("not available", text)
        self.assertTrue(
            interaction.response.send_message.await_args.kwargs["ephemeral"]
        )

    async def test_single_server_command_is_not_run_on_another_server(self):
        await self.scope.sync_all()
        interaction = self.stale_click("transport", BRAVO)

        _, run = await self.handle(interaction)

        run.assert_not_awaited()
        interaction.response.send_message.assert_awaited_once()

    async def test_per_server_command_is_not_run_outside_a_server(self):
        await self.scope.sync_all()
        interaction = self.stale_click("eve", None)

        _, run = await self.handle(interaction)

        run.assert_not_awaited()
        interaction.response.send_message.assert_awaited_once()

    async def test_suggestions_of_an_old_entry_keep_working(self):
        await self.scope.sync_all()
        interaction = self.stale_click("eve")
        interaction.type = discord.InteractionType.auto_complete

        with patch.object(self.bot, "dispatch") as dispatch:
            _, run = await self.handle(interaction)

        run.assert_not_awaited()
        dispatch.assert_called_once_with(
            "application_command_auto_complete", interaction, command(self.bot, "eve")
        )

    async def test_suggestions_of_an_unknown_command_are_left_alone(self):
        # A text answer is not allowed while the member is still typing.
        await self.scope.sync_all()
        interaction = self.stale_click("gone")
        interaction.type = discord.InteractionType.auto_complete

        await self.handle(interaction)

        interaction.response.send_message.assert_not_awaited()


class ManagedCommandsTest(SimpleTestCase):
    def test_only_commands_of_switchable_modules_are_managed(self):
        bot = load(MODULES)

        self.assertEqual(module_key(command(bot, "eve")), "eveonline")
        self.assertEqual(module_key(command(bot, "ticket")), "ticket")
        self.assertIsNone(module_key(command(bot, "panel")))
        self.assertIsNone(module_key(command(bot, "bot")))
        self.assertIsNone(module_key(command(bot, "transport")))

    def test_no_switchable_module_declares_servers_of_its_own(self):
        # The scope overwrites guild_ids of managed commands; a declared list
        # would be lost without a word. Only the single-server modules, which
        # are not in the registry, may name servers.
        cogs = Path(command_scope.__file__).resolve().parents[1] / "cogs"
        found = [
            path.relative_to(cogs).as_posix()
            for path in sorted(cogs.rglob("*.py"))
            if not path.relative_to(cogs).as_posix().startswith(SINGLE_SERVER)
            and DECLARED_SERVERS.search(path.read_text("utf-8"))
        ]

        self.assertEqual(found, [])
