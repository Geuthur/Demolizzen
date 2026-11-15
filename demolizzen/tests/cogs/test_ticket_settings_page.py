# Standard Library
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

# Discord
import discord

# Django
from django.test import TestCase

# Demolizzen
from demolizzen.cogs.panel._view import PanelView
from demolizzen.cogs.ticket._settings_page import (
    TicketSettingsView,
    build_settings_embed,
    ticket_settings_page,
)
from demolizzen.cogs.ticket._views import OpenTicketView
from demolizzen.core import settings_pages
from demolizzen.models import GuildTicketSettings
from demolizzen.services import cog_settings, tickets
from demolizzen.tests.cogs.ticket_fakes import (
    ARCHIVE_ID,
    CATEGORY_ID,
    GUILD_ID,
    LOG_ID,
    STAFF_ROLE_ID,
    FakeGuild,
    make_channel,
    make_role,
    said,
)


def labels(view) -> list[str]:
    return [
        getattr(item, "label", None) or getattr(item, "placeholder", None)
        for item in view.children
    ]


def field(embed, name: str) -> str:
    return next(f.value for f in embed.fields if f.name == name)


class SettingsPageTestCase(TestCase):
    def setUp(self):
        cog_settings.invalidate()
        self.fake = FakeGuild()
        self.back = AsyncMock()

    async def make_view(self, section="overview", **fields) -> TicketSettingsView:
        settings = await self.fake.configure(**fields)
        return TicketSettingsView(
            GUILD_ID, self.fake.admin.id, self.back, settings, section=section
        )

    def interaction(self, user=None):
        channel = make_channel(4000, "support", self.fake.guild)
        return self.fake.interaction(user or self.fake.admin, channel)

    async def stored(self) -> GuildTicketSettings:
        return await GuildTicketSettings.objects.aget(guild_id=GUILD_ID)


class PanelSettingsButtonTest(SettingsPageTestCase):
    def setUp(self):
        super().setUp()
        self.page = AsyncMock()
        settings_pages.register("ticket", self.page)
        self.addCleanup(settings_pages.unregister, "ticket")

    async def panel(self) -> PanelView:
        await self.fake.configure()
        return PanelView(
            GUILD_ID, "Alpha", self.fake.admin.id, await cog_settings.get_states(1)
        )

    async def test_settings_button_only_for_modules_with_page(self):
        view = await self.panel()

        await view.choose(self.interaction(), "ticket")
        self.assertIn("Settings", labels(view))

        await view.choose(self.interaction(), "games")
        self.assertNotIn("Settings", labels(view))

    async def test_no_settings_button_before_a_module_is_chosen(self):
        self.assertNotIn("Settings", labels(await self.panel()))

    async def test_settings_button_absent_when_module_disabled(self):
        view = await self.panel()
        await cog_settings.set_enabled(GUILD_ID, "ticket", False)

        await view.choose(self.interaction(), "ticket")

        self.assertNotIn("Settings", labels(view))

    async def test_settings_button_opens_page_and_back_returns(self):
        view = await self.panel()
        await view.choose(self.interaction(), "ticket")
        interaction = self.interaction()

        await view.open_settings(interaction)

        self.page.assert_awaited_once()
        self.assertIs(self.page.await_args.args[0], interaction)
        self.assertTrue(view.is_finished())

        back = self.page.await_args.args[1]
        returning = self.interaction()
        await back(returning)

        edit = returning.response.edit_message.await_args.kwargs
        self.assertIsInstance(edit["view"], PanelView)
        self.assertEqual(edit["view"].selected, "ticket")
        self.assertEqual(edit["embed"].title, "⚙️ Demolizzen Panel – Alpha")

    async def test_unknown_module_cannot_register_a_page(self):
        with self.assertRaises(Exception):
            settings_pages.register("nope", self.page)


class SettingsEmbedTest(SettingsPageTestCase):
    async def test_embed_marks_missing_category_and_roles(self):
        settings = await self.fake.configure(category_id=None, roles=[])

        embed = build_settings_embed(settings)

        self.assertEqual(field(embed, "Ticket category"), "⚠️ not set")
        self.assertEqual(field(embed, "Staff roles"), "⚠️ not set")
        self.assertEqual(field(embed, "Archive category"), "not set")
        self.assertEqual(field(embed, "Log channel"), "not set")

    async def test_embed_shows_current_values(self):
        settings = await self.fake.configure(
            archive_category_id=ARCHIVE_ID,
            log_channel_id=LOG_ID,
            allow_user_reopen=False,
            auto_archive_days=7,
            max_open_tickets=2,
        )

        embed = build_settings_embed(settings)

        self.assertEqual(field(embed, "Ticket category"), f"<#{CATEGORY_ID}>")
        self.assertEqual(field(embed, "Archive category"), f"<#{ARCHIVE_ID}>")
        self.assertEqual(field(embed, "Log channel"), f"<#{LOG_ID}>")
        self.assertEqual(field(embed, "Staff roles"), f"<@&{STAFF_ROLE_ID}>")
        self.assertEqual(field(embed, "Members may close"), "✅")
        self.assertEqual(field(embed, "Members may reopen"), "❌")
        self.assertEqual(field(embed, "Archive after"), "7 days")
        self.assertEqual(field(embed, "Open tickets per member"), "2")


class SettingsViewTest(SettingsPageTestCase):
    async def test_page_function_shows_overview(self):
        await self.fake.configure()
        interaction = self.interaction()

        await ticket_settings_page(interaction, self.back)

        edit = interaction.response.edit_message.await_args.kwargs
        self.assertIsInstance(edit["view"], TicketSettingsView)
        self.assertEqual(
            labels(edit["view"]),
            ["Channels", "Staff & permissions", "Limits", "Post ticket button", "Back"],
        )

    async def test_sections_offer_their_controls(self):
        expected = {
            "channels": [
                "Ticket category",
                "Archive category",
                "Log channel",
                "Clear archive category",
                "Clear log channel",
                "Back",
            ],
            "staff": [
                "Staff roles",
                "Members may close: On",
                "Members may reopen: On",
                "Back",
            ],
            "limits": ["Archive after … days", "Open tickets per member", "Back"],
        }
        for section, controls in expected.items():
            with self.subTest(section=section):
                view = await self.make_view(section)
                self.assertEqual(labels(view), controls)

    async def test_show_section_redraws(self):
        view = await self.make_view()
        interaction = self.interaction()

        await view.show_section(interaction, "limits")

        self.assertEqual(view.section, "limits")
        self.assertIs(interaction.response.edit_message.await_args.kwargs["view"], view)

    async def test_each_control_updates_its_setting(self):
        view = await self.make_view()
        cases = {
            "category_id": 4321,
            "archive_category_id": ARCHIVE_ID,
            "log_channel_id": LOG_ID,
            "roles": [901, 902],
            "auto_archive_days": 14,
            "max_open_tickets": 5,
        }
        for name, value in cases.items():
            with self.subTest(setting=name):
                interaction = self.interaction()

                await view.set_value(interaction, name, value)

                self.assertEqual(getattr(await self.stored(), name), value)
                interaction.response.edit_message.assert_awaited_once()

    async def test_clearing_optional_channels(self):
        view = await self.make_view(
            "channels", archive_category_id=ARCHIVE_ID, log_channel_id=LOG_ID
        )

        await view.set_value(self.interaction(), "archive_category_id", None)
        await view.set_value(self.interaction(), "log_channel_id", None)

        stored = await self.stored()
        self.assertIsNone(stored.archive_category_id)
        self.assertIsNone(stored.log_channel_id)

    async def test_toggle_flips_allow_user_close(self):
        view = await self.make_view("staff")

        await view.toggle(self.interaction(), "allow_user_close")

        self.assertFalse((await self.stored()).allow_user_close)
        self.assertIn("Members may close: Off", labels(view))

        await view.toggle(self.interaction(), "allow_user_close")
        self.assertTrue((await self.stored()).allow_user_close)

    async def test_select_controls_are_wired_to_their_settings(self):
        view = await self.make_view("channels")
        picked = MagicMock()
        picked.id = 4321
        select = view.children[0]

        with patch.object(
            type(select), "values", new_callable=PropertyMock, return_value=[picked]
        ):
            await select.callback(self.interaction())

        self.assertEqual((await self.stored()).category_id, 4321)

    async def test_role_select_stores_all_picked_roles(self):
        view = await self.make_view("staff")
        select = view.children[0]

        with patch.object(
            type(select),
            "values",
            new_callable=PropertyMock,
            return_value=[make_role(901), make_role(902)],
        ):
            await select.callback(self.interaction())

        self.assertEqual((await self.stored()).roles, [901, 902])

    async def test_limit_selects_store_numbers(self):
        view = await self.make_view("limits")
        days, per_member = view.children[0], view.children[1]

        with patch.object(
            type(days), "values", new_callable=PropertyMock, return_value=["14"]
        ):
            await days.callback(self.interaction())
        with patch.object(
            type(per_member), "values", new_callable=PropertyMock, return_value=["3"]
        ):
            await per_member.callback(self.interaction())

        stored = await self.stored()
        self.assertEqual(stored.auto_archive_days, 14)
        self.assertEqual(stored.max_open_tickets, 3)

    async def test_post_ticket_button_sends_open_view_to_channel(self):
        view = await self.make_view()
        interaction = self.interaction()

        await view.post_button(interaction)

        kwargs = interaction.channel.send.await_args.kwargs
        self.assertIsInstance(kwargs["view"], OpenTicketView)
        self.assertIn("Open a ticket", kwargs["embed"].description)
        self.assertIn("posted", said(interaction)[-1])

    async def test_post_ticket_button_without_permission(self):
        view = await self.make_view()
        interaction = self.interaction()
        response = MagicMock(status=403, reason="Forbidden")
        interaction.channel.send = AsyncMock(
            side_effect=discord.Forbidden(response, "nope")
        )

        await view.post_button(interaction)

        self.assertIn("cannot send", said(interaction)[-1])

    async def test_back_returns_to_the_panel(self):
        view = await self.make_view()
        interaction = self.interaction()

        await view.go_back(interaction)

        self.back.assert_awaited_once_with(interaction)
        self.assertTrue(view.is_finished())

    async def test_page_respects_panel_permission(self):
        view = await self.make_view()
        foreign = self.interaction(self.fake.staff)

        self.assertFalse(await view.interaction_check(foreign))
        self.assertEqual(said(foreign), ["You are not allowed to use this panel."])
        self.assertTrue(await view.interaction_check(self.interaction()))

    async def test_invalid_value_is_rejected_and_setting_kept(self):
        view = await self.make_view()
        await tickets.update_settings(GUILD_ID, max_open_tickets=2)

        await view.set_value(self.interaction(), "max_open_tickets", 99)

        self.assertEqual((await self.stored()).max_open_tickets, 2)
