# Standard Library
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import AsyncMock, MagicMock, patch

# Discord
import discord

# Django
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

# Demolizzen
from demolizzen.cogs.ticket import _transcript
from demolizzen.cogs.ticket._transcript import render_transcript
from demolizzen.cogs.ticket._views import OpenTicketView, TicketControlView
from demolizzen.cogs.ticket.ticket import TicketSystem
from demolizzen.models import GuildTicket
from demolizzen.services import cog_settings, tickets
from demolizzen.tests.cogs.ticket_fakes import (
    ARCHIVE_ID,
    GUILD_ID,
    LOG_ID,
    OWNER_ID,
    FakeGuild,
    make_message,
    said,
)

WHEN = datetime(2026, 11, 15, 9, 30, tzinfo=dt_timezone.utc)


class TicketCogTestCase(TestCase):
    def setUp(self):
        cog_settings.invalidate()
        self.fake = FakeGuild()
        self.bot = MagicMock()
        self.bot.guilds = [self.fake.guild]
        self.bot.get_guild = MagicMock(side_effect={GUILD_ID: self.fake.guild}.get)
        with patch("discord.ext.tasks.Loop.start"):
            self.cog = TicketSystem(self.bot)
        self.cog.renamer = MagicMock()
        self.cog.actions.renamer = self.cog.renamer

    def component_click(self, user, channel, custom_id):
        interaction = self.fake.interaction(user, channel)
        interaction.type = discord.InteractionType.component
        interaction.data = {"custom_id": custom_id, "component_type": 2}
        return interaction

    async def stored(self, channel_id=100) -> GuildTicket:
        return await GuildTicket.objects.aget(channel_id=channel_id)


class TicketCogSetupTest(TicketCogTestCase):
    def test_views_are_not_created_before_the_event_loop_runs(self):
        # py-cord views need a running loop; extensions load before there is one.
        self.bot.add_view.assert_not_called()

    async def test_cog_registers_persistent_views_once(self):
        await self.cog.on_ready()
        await self.cog.on_ready()

        views = [call.args[0] for call in self.bot.add_view.call_args_list]
        self.assertEqual(
            [type(view) for view in views], [TicketControlView, OpenTicketView]
        )
        self.assertTrue(all(view.is_persistent() for view in views))
        self.assertTrue(all(view.handler is not None for view in views))

    async def test_cog_loaded_while_running_registers_views_immediately(self):
        bot = MagicMock()
        with patch("discord.ext.tasks.Loop.start"):
            TicketSystem(bot)

        self.assertEqual(bot.add_view.call_count, 2)

    async def test_ticket_open_command_starts_open_flow(self):
        await self.fake.configure()
        ctx = MagicMock()
        ctx.interaction = self.fake.interaction(self.fake.owner)

        await self.cog.open_ticket.callback(self.cog, ctx)

        ctx.interaction.response.send_modal.assert_awaited_once()


class LegacyButtonTest(TicketCogTestCase):
    async def test_legacy_button_click_is_handled_and_migrated(self):
        await self.fake.configure()
        channel = await self.fake.make_ticket(number=7)
        await GuildTicket.objects.filter(channel_id=100).aupdate(
            control_message_id=None
        )
        interaction = self.component_click(self.fake.staff, channel, "close:1:7")

        await self.cog.on_interaction(interaction)

        ticket = await self.stored()
        self.assertTrue(ticket.is_closed)
        self.assertEqual(ticket.control_message_id, interaction.message.id)
        view = interaction.response.edit_message.await_args.kwargs["view"]
        self.assertIsInstance(view, TicketControlView)
        self.assertEqual(view.children[0].custom_id, "ticket:claim")

    async def test_every_legacy_action_is_recognised(self):
        await self.fake.configure()
        channel = await self.fake.make_ticket()
        self.cog.actions.handle = AsyncMock()

        for name in ("claim", "close", "reopen", "delete"):
            await self.cog.on_interaction(
                self.component_click(self.fake.staff, channel, f"{name}:1:1")
            )

        self.assertEqual(
            [call.args[1] for call in self.cog.actions.handle.await_args_list],
            [
                tickets.Action.CLAIM,
                tickets.Action.CLOSE,
                tickets.Action.REOPEN,
                tickets.Action.DELETE,
            ],
        )

    async def test_foreign_component_click_is_ignored(self):
        await self.fake.configure()
        channel = await self.fake.make_ticket()
        self.cog.actions.handle = AsyncMock()

        for custom_id in ("something:else", "ticket:close", "close:1", "xclose:1:1"):
            await self.cog.on_interaction(
                self.component_click(self.fake.staff, channel, custom_id)
            )
        command = self.fake.interaction(self.fake.staff, channel)
        command.type = discord.InteractionType.application_command
        command.data = {"name": "close:1:1"}
        await self.cog.on_interaction(command)

        self.cog.actions.handle.assert_not_awaited()


class ChannelDeleteTest(TicketCogTestCase):
    async def test_manual_channel_delete_removes_ticket(self):
        await self.fake.configure()
        channel = await self.fake.make_ticket()

        await self.cog.on_guild_channel_delete(channel)

        self.assertEqual(await GuildTicket.objects.acount(), 0)
        await tickets.check_can_open(GUILD_ID, OWNER_ID)

    async def test_other_channel_delete_is_harmless(self):
        await self.fake.configure()
        await self.fake.make_ticket()

        await self.cog.on_guild_channel_delete(self.fake.log_channel)

        self.assertEqual(await GuildTicket.objects.acount(), 1)


class MaintenanceTest(TicketCogTestCase):
    async def due_ticket(self, **settings):
        await self.fake.configure(
            archive_category_id=ARCHIVE_ID, auto_archive_days=3, **settings
        )
        return await self.fake.make_ticket(
            is_closed=True, closed_at=timezone.now() - timedelta(days=4), closed_by=20
        )

    async def test_maintenance_archives_due_tickets(self):
        channel = await self.due_ticket()

        await self.cog.run_maintenance()

        self.assertIs(channel.category, self.fake.archive)
        self.assertTrue((await self.stored()).is_archived)
        edit = channel.partial_message.edit.await_args.kwargs
        self.assertIn("📦 Archived", edit["embed"].description)

    async def test_maintenance_leaves_recently_closed_tickets(self):
        await self.fake.configure(archive_category_id=ARCHIVE_ID, auto_archive_days=3)
        channel = await self.fake.make_ticket(
            is_closed=True, closed_at=timezone.now() - timedelta(days=1)
        )

        await self.cog.run_maintenance()

        self.assertIs(channel.category, self.fake.category)
        self.assertFalse((await self.stored()).is_archived)

    async def test_maintenance_skips_full_or_missing_archive_category(self):
        channel = await self.due_ticket()
        self.fake.archive.channels = [MagicMock() for _ in range(50)]

        await self.cog.run_maintenance()
        self.assertFalse((await self.stored()).is_archived)

        del self.fake.channels[ARCHIVE_ID]
        await self.cog.run_maintenance()
        self.assertFalse((await self.stored()).is_archived)
        self.assertIs(channel.category, self.fake.category)

    async def test_maintenance_skips_guilds_with_module_disabled(self):
        channel = await self.due_ticket()
        await cog_settings.set_enabled(GUILD_ID, "ticket", False)

        await self.cog.run_maintenance()

        self.assertFalse((await self.stored()).is_archived)
        self.assertIs(channel.category, self.fake.category)
        self.cog.renamer.request.assert_not_called()

    async def test_maintenance_removes_tickets_without_channel(self):
        await self.fake.configure()
        await self.fake.make_ticket()
        del self.fake.channels[100]

        await self.cog.run_maintenance()

        self.assertEqual(await GuildTicket.objects.acount(), 0)

    async def test_removed_ticket_is_logged_by_number(self):
        await self.fake.configure()
        await self.fake.make_ticket(number=7)
        del self.fake.channels[100]

        with self.assertLogs("demolizzen.cogs.ticket.ticket", "INFO") as logs:
            await self.cog.run_maintenance()

        self.assertIn("ticket #7 of guild 1", logs.output[0])

    async def test_maintenance_keeps_tickets_of_guilds_it_cannot_see(self):
        await self.fake.configure()
        await self.fake.make_ticket()
        self.bot.get_guild = MagicMock(return_value=None)

        await self.cog.run_maintenance()

        self.assertEqual(await GuildTicket.objects.acount(), 1)

    async def test_maintenance_requests_expected_names(self):
        await self.fake.configure(max_open_tickets=5)
        open_channel = await self.fake.make_ticket(1, 100)
        closed_channel = await self.fake.make_ticket(2, 200, is_closed=True)
        open_channel.name = "ticket1-unclaimed-max"

        await self.cog.run_maintenance()

        self.cog.renamer.request.assert_any_call(
            open_channel, "ticket-0001-max-mustermann"
        )
        self.cog.renamer.request.assert_any_call(
            closed_channel, "closed-0002-max-mustermann"
        )


class TranscriptTest(SimpleTestCase):
    def test_render_transcript_contains_header_and_messages(self):
        ticket = GuildTicket(
            ticket_number=42,
            channel_id=100,
            user_id=10,
            subject="Login problem",
            closed_by=20,
        )
        messages = [
            make_message("max", "I cannot log in.", WHEN),
            make_message(
                "mod", "", WHEN + timedelta(minutes=5), ["https://cdn.example/a.png"]
            ),
        ]

        text = render_transcript(ticket, messages, deleted_by="admin")

        self.assertIn("Ticket #0042", text)
        self.assertIn("Subject: Login problem", text)
        self.assertIn("Created by: 10", text)
        self.assertIn("Closed by: 20", text)
        self.assertIn("Deleted by: admin", text)
        self.assertIn("[2026-11-15 09:30] max: I cannot log in.", text)
        self.assertIn("[2026-11-15 09:35] mod:", text)
        self.assertIn("https://cdn.example/a.png", text)

    def test_transcript_limit(self):
        self.assertEqual(_transcript.MAX_MESSAGES, 5000)


class DeleteTranscriptTest(TicketCogTestCase):
    async def delete(self, channel):
        interaction = self.fake.interaction(self.fake.admin, channel)
        await self.cog.actions.delete(interaction)
        return interaction

    async def test_delete_posts_transcript_to_log_channel(self):
        await self.fake.configure(log_channel_id=LOG_ID)
        channel = await self.fake.make_ticket()
        channel.messages = [make_message("max", "I cannot log in.", WHEN)]

        await self.delete(channel)

        kwargs = self.fake.log_channel.send.await_args.kwargs
        self.assertEqual(kwargs["file"].filename, "ticket-0001.txt")
        self.assertIn(b"I cannot log in.", kwargs["file"].fp.read())
        self.assertIn("Ticket #0001", kwargs["embed"].title)
        self.assertEqual(channel.history.call_args.kwargs["limit"], 5000)
        channel.delete.assert_awaited_once()
        self.assertEqual(await GuildTicket.objects.acount(), 0)

    async def test_delete_without_log_channel_just_deletes(self):
        await self.fake.configure()
        channel = await self.fake.make_ticket()

        await self.delete(channel)

        self.fake.log_channel.send.assert_not_awaited()
        channel.delete.assert_awaited_once()

    async def test_delete_continues_when_transcript_upload_fails(self):
        await self.fake.configure(log_channel_id=LOG_ID)
        channel = await self.fake.make_ticket()
        response = MagicMock(status=403, reason="Forbidden")
        self.fake.log_channel.send = AsyncMock(
            side_effect=discord.Forbidden(response, "nope")
        )

        interaction = await self.delete(channel)

        channel.delete.assert_awaited_once()
        self.assertEqual(await GuildTicket.objects.acount(), 0)
        self.assertNotIn("permission", " ".join(said(interaction)))
