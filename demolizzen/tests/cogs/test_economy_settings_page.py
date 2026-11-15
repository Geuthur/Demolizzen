# Standard Library
from unittest.mock import AsyncMock, PropertyMock, patch

# Discord
import discord

# Django
from django.test import TestCase

# Demolizzen
from demolizzen.cogs.economy._settings_page import (
    EconomySettingsView,
    economy_settings_page,
)
from demolizzen.core import settings_pages
from demolizzen.core.bot import Demolizzen
from demolizzen.services import cog_settings, guilds, missions
from demolizzen.services.missions import Event
from demolizzen.tests.helpers import make_guild, make_interaction, make_member


def labels(view) -> list[str]:
    return [item.label for item in view.children if isinstance(item, discord.ui.Button)]


class EconomySettingsPageTest(TestCase):
    def setUp(self):
        cog_settings.invalidate()
        self.admin = make_member(10, "admin", manage_guild=True)
        self.guild = make_guild(
            1, "Alpha", members=[make_member(1, "boss"), self.admin]
        )
        self.back = AsyncMock()

    def interaction(self, user=None):
        return make_interaction(guild=self.guild, user=user or self.admin)

    async def make_view(self, **event) -> EconomySettingsView:
        await guilds.ensure_guild(1, "Alpha")
        if event:
            await missions.set_event(1, **event)
        return EconomySettingsView(1, 10, self.back, await missions.get_event(1))

    async def test_embed_shows_state_and_factor(self):
        off = (await self.make_view()).embed()
        on = (await self.make_view(active=True, factor=4)).embed()

        self.assertEqual(off.title, "💰 Economy – Settings")
        self.assertEqual(
            [(field.name, field.value) for field in off.fields],
            [("Event", "❌"), ("Payout factor", "x2")],
        )
        self.assertEqual(
            [(field.name, field.value) for field in on.fields],
            [("Event", "✅"), ("Payout factor", "x4")],
        )

    async def test_controls(self):
        view = await self.make_view(factor=4)
        select = view.children[0]

        self.assertEqual(
            [option.value for option in select.options],
            [str(number) for number in range(1, 11)],
        )
        self.assertEqual(
            [option.value for option in select.options if option.default], ["4"]
        )
        self.assertEqual(labels(view), ["Event: Off", "Back"])

    async def test_toggle_switches_the_event(self):
        view = await self.make_view()
        interaction = self.interaction()

        await view.toggle(interaction)

        self.assertEqual(await missions.get_event(1), Event(True, 2))
        self.assertIn("Event: On", labels(view))
        edit = interaction.response.edit_message.await_args.kwargs
        self.assertEqual(edit["embed"].fields[0].value, "✅")
        self.assertIs(edit["view"], view)

        await view.toggle(self.interaction())
        self.assertEqual(await missions.get_event(1), Event(False, 2))

    async def test_factor_select_stores_the_factor(self):
        view = await self.make_view(active=True)
        select = view.children[0]

        with patch.object(
            type(select), "values", new_callable=PropertyMock, return_value=["7"]
        ):
            await select.callback(self.interaction())

        self.assertEqual(await missions.get_event(1), Event(True, 7))

    async def test_events_of_other_guilds_are_untouched(self):
        await guilds.ensure_guild(2, "Beta")
        view = await self.make_view()

        await view.toggle(self.interaction())
        await view.set_factor(self.interaction(), 9)

        self.assertEqual(await missions.get_event(2), Event(False, 2))

    async def test_page_respects_panel_permission(self):
        view = await self.make_view()
        foreign = self.interaction(make_member(99, manage_guild=True))

        self.assertFalse(await view.interaction_check(foreign))
        self.assertTrue(await view.interaction_check(self.interaction()))

    async def test_back_returns_to_panel(self):
        view = await self.make_view()
        interaction = self.interaction()

        await view.go_back(interaction)

        self.back.assert_awaited_once_with(interaction)
        self.assertTrue(view.is_finished())

    async def test_page_function_shows_settings(self):
        interaction = self.interaction()

        await economy_settings_page(interaction, self.back)

        edit = interaction.response.edit_message.await_args.kwargs
        self.assertIsInstance(edit["view"], EconomySettingsView)
        self.assertEqual(edit["embed"].title, "💰 Economy – Settings")


class EconomyExtensionTest(TestCase):
    def setUp(self):
        with patch("discord.ext.tasks.Loop.start"):
            self.bot = Demolizzen()
            self.bot.preload_ext = ["admin", "banksystem", "economy"]
            self.results = self.bot.load_preload_extensions()
        self.addCleanup(settings_pages.unregister, "economy")
        self.addCleanup(settings_pages.unregister, "banksystem")

    def test_economy_settings_page_is_registered(self):
        self.assertIsNone(self.results["economy"])
        self.assertIs(settings_pages.get("economy"), economy_settings_page)

    def test_admin_has_no_economy_commands(self):
        names = {command.name for command in self.bot.pending_application_commands}

        # A command group without commands cannot be used; it is gone as a whole.
        self.assertNotIn("admin", names)
        self.assertIn("moderation", names)
