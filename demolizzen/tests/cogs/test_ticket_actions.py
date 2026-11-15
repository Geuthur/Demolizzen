# Standard Library
from unittest.mock import AsyncMock, MagicMock

# Discord
import discord

# Django
from django.test import SimpleTestCase, TestCase

# Demolizzen
from demolizzen.cogs.ticket._actions import TicketActions
from demolizzen.cogs.ticket._views import (
    ConfirmDeleteView,
    OpenTicketModal,
    OpenTicketView,
    TicketControlView,
    build_status_embed,
)
from demolizzen.models import GuildTicket
from demolizzen.services import cog_settings, tickets
from demolizzen.services.tickets import Action
from demolizzen.tests.cogs.ticket_fakes import (
    ARCHIVE_ID,
    GUILD_ID,
    OWNER_ID,
    STAFF_ID,
    FakeGuild,
    make_category,
    said,
)


def enabled_labels(view) -> list[str]:
    return [item.label for item in view.children if not item.disabled]


class StatusEmbedTest(SimpleTestCase):
    def ticket(self, **fields):
        return GuildTicket(
            ticket_number=42, channel_id=100, user_id=10, subject="Login", **fields
        )

    def test_status_embed_for_open_ticket(self):
        embed = build_status_embed(self.ticket())

        self.assertEqual(embed.title, "🎫 Ticket #0042 – Login")
        self.assertIn("Status: 🟢 Open", embed.description)
        self.assertIn("Created by: <@10>", embed.description)
        self.assertNotIn("Claimed by", embed.description)

    def test_status_embed_for_claimed_ticket(self):
        embed = build_status_embed(self.ticket(claimed_by=20))

        self.assertIn("Claimed by: <@20>", embed.description)

    def test_status_embed_for_closed_and_archived_ticket(self):
        closed = build_status_embed(self.ticket(is_closed=True, closed_by=20))
        archived = build_status_embed(
            self.ticket(is_closed=True, is_archived=True, closed_by=20)
        )

        self.assertIn("Status: 🔒 Closed", closed.description)
        self.assertIn("Closed by: <@20>", closed.description)
        self.assertIn("Status: 📦 Archived", archived.description)

    def test_ticket_without_subject_shows_number_only(self):
        ticket = GuildTicket(ticket_number=7, channel_id=1, user_id=10)

        self.assertEqual(build_status_embed(ticket).title, "🎫 Ticket #0007")


class ControlViewTest(SimpleTestCase):
    async def test_control_view_buttons_follow_ticket_state(self):
        base = {"ticket_number": 1, "channel_id": 1, "user_id": 10}
        cases = [
            ({}, ["Claim", "Close", "Delete"]),
            ({"claimed_by": 20}, ["Close", "Delete"]),
            ({"is_closed": True}, ["Reopen", "Delete"]),
            ({"is_closed": True, "is_archived": True}, ["Reopen", "Delete"]),
        ]
        for fields, expected in cases:
            with self.subTest(fields=fields):
                view = TicketControlView(GuildTicket(**base, **fields))
                self.assertEqual(enabled_labels(view), expected)

    async def test_views_are_persistent(self):
        self.assertTrue(TicketControlView().is_persistent())
        self.assertTrue(OpenTicketView().is_persistent())
        self.assertEqual(
            [item.custom_id for item in TicketControlView().children],
            ["ticket:claim", "ticket:close", "ticket:reopen", "ticket:delete"],
        )
        self.assertEqual(OpenTicketView().children[0].custom_id, "ticket:open")

    async def test_control_view_calls_handler_with_action(self):
        handler = AsyncMock()
        view = TicketControlView(handler=handler)
        interaction = MagicMock()

        await view.children[1].callback(interaction)

        handler.assert_awaited_once_with(interaction, Action.CLOSE)


class ActionsTestCase(TestCase):
    def setUp(self):
        cog_settings.invalidate()
        self.fake = FakeGuild()
        self.renamer = MagicMock()
        self.actions = TicketActions(MagicMock(), self.renamer, cog_settings_enabled)

    async def stored(self, channel_id=100) -> GuildTicket:
        return await GuildTicket.objects.aget(channel_id=channel_id)


async def cog_settings_enabled(guild_id):
    return await cog_settings.is_enabled(guild_id, "ticket")


class StartOpenTest(ActionsTestCase):
    async def test_start_open_shows_modal(self):
        await self.fake.configure()
        interaction = self.fake.interaction(self.fake.owner)

        await self.actions.start_open(interaction)

        modal = interaction.response.send_modal.await_args.args[0]
        self.assertIsInstance(modal, OpenTicketModal)

    async def test_start_open_without_category_tells_user(self):
        await self.fake.configure(category_id=None)
        interaction = self.fake.interaction(self.fake.owner)

        await self.actions.start_open(interaction)

        interaction.response.send_modal.assert_not_awaited()
        self.assertIn("/panel", said(interaction)[0])

    async def test_start_open_with_deleted_category_tells_user(self):
        await self.fake.configure(category_id=555)
        interaction = self.fake.interaction(self.fake.owner)

        await self.actions.start_open(interaction)

        interaction.response.send_modal.assert_not_awaited()
        self.assertIn("no longer exists", said(interaction)[0])

    async def test_start_open_with_full_category_tells_user(self):
        await self.fake.configure()
        self.fake.category.channels = [MagicMock() for _ in range(50)]
        interaction = self.fake.interaction(self.fake.owner)

        await self.actions.start_open(interaction)

        interaction.response.send_modal.assert_not_awaited()
        self.assertIn("The ticket category is full.", said(interaction)[0])

    async def test_start_open_at_limit_tells_user(self):
        await self.fake.configure()
        await self.fake.make_ticket()
        interaction = self.fake.interaction(self.fake.owner)

        await self.actions.start_open(interaction)

        interaction.response.send_modal.assert_not_awaited()
        self.assertIn("already have 1 open ticket", said(interaction)[0])

    async def test_start_open_when_module_disabled(self):
        await self.fake.configure()
        await cog_settings.set_enabled(GUILD_ID, "ticket", False)
        interaction = self.fake.interaction(self.fake.owner)

        await self.actions.start_open(interaction)

        self.assertEqual(said(interaction), ["This module is disabled on this server."])


class OpenTest(ActionsTestCase):
    async def test_open_creates_channel_ticket_and_status_message(self):
        await self.fake.configure()
        interaction = self.fake.interaction(self.fake.owner)

        await self.actions.open(interaction, "Login problem", "I cannot log in.")

        channel = self.fake.created[0]
        self.assertEqual(channel.name, "ticket-0001-max-mustermann")
        self.assertIs(channel.category, self.fake.category)
        ticket = await self.stored(channel.id)
        self.assertEqual(ticket.subject, "Login problem")
        self.assertEqual(ticket.user_id, OWNER_ID)
        self.assertEqual(ticket.control_message_id, channel.id + 1)
        first = channel.send.await_args_list[0].kwargs
        self.assertIn("<@&900>", first["content"])
        self.assertEqual(first["embed"].title, "🎫 Ticket #0001 – Login problem")
        self.assertIsInstance(first["view"], TicketControlView)
        self.assertIn("I cannot log in.", str(channel.send.await_args_list[1]))
        self.assertIn("<#1000>", said(interaction)[-1])

    async def test_channel_is_private_to_owner_staff_and_bot(self):
        await self.fake.configure()

        await self.actions.open(self.fake.interaction(self.fake.owner), "Hi", "")

        overwrites = self.fake.created[0].overwrites
        self.assertFalse(overwrites[self.fake.guild.default_role].view_channel)
        self.assertTrue(overwrites[self.fake.staff_role].view_channel)
        self.assertTrue(overwrites[self.fake.guild.me].view_channel)
        self.assertTrue(overwrites[self.fake.owner].send_messages)
        self.assertFalse(overwrites[self.fake.owner].mention_everyone)

    async def test_description_cannot_ping(self):
        await self.fake.configure()

        await self.actions.open(
            self.fake.interaction(self.fake.owner), "Hi", "@everyone look"
        )

        second = self.fake.created[0].send.await_args_list[1].kwargs
        mentions = second["allowed_mentions"]
        self.assertFalse(mentions.everyone)
        self.assertFalse(mentions.roles)

    async def test_ticket_numbers_count_up(self):
        await self.fake.configure(max_open_tickets=2)

        await self.actions.open(self.fake.interaction(self.fake.owner), "One", "")
        await self.actions.open(self.fake.interaction(self.fake.owner), "Two", "")

        self.assertEqual(
            [channel.name for channel in self.fake.created],
            ["ticket-0001-max-mustermann", "ticket-0002-max-mustermann"],
        )

    async def test_open_failure_after_channel_creation_cleans_up(self):
        await self.fake.configure()
        response = MagicMock(status=500, reason="boom")
        original = self.fake.guild.create_text_channel.side_effect

        async def create_then_break(name, **kwargs):
            channel = await original(name, **kwargs)
            channel.send = AsyncMock(side_effect=discord.HTTPException(response, "x"))
            return channel

        self.fake.guild.create_text_channel.side_effect = create_then_break
        interaction = self.fake.interaction(self.fake.owner)

        await self.actions.open(interaction, "Login problem", "")

        self.fake.created[0].delete.assert_awaited_once()
        self.assertEqual(await GuildTicket.objects.acount(), 0)
        self.assertIn("could not be created", said(interaction)[-1])

    async def test_open_without_permission_tells_user(self):
        await self.fake.configure()
        response = MagicMock(status=403, reason="Forbidden")
        self.fake.guild.create_text_channel.side_effect = discord.Forbidden(
            response, "nope"
        )
        interaction = self.fake.interaction(self.fake.owner)

        await self.actions.open(interaction, "Login problem", "")

        self.assertEqual(await GuildTicket.objects.acount(), 0)
        self.assertIn("permission", said(interaction)[-1])

    async def test_open_rechecks_the_limit(self):
        await self.fake.configure()
        await self.fake.make_ticket()
        interaction = self.fake.interaction(self.fake.owner)

        await self.actions.open(interaction, "Again", "")

        self.assertEqual(self.fake.created, [])
        self.assertEqual(await GuildTicket.objects.acount(), 1)


class HandleTest(ActionsTestCase):
    async def test_claim_by_staff_updates_message_and_announces(self):
        await self.fake.configure()
        channel = await self.fake.make_ticket()
        interaction = self.fake.interaction(self.fake.staff, channel)

        await self.actions.handle(interaction, Action.CLAIM)

        self.assertEqual((await self.stored()).claimed_by, STAFF_ID)
        edit = interaction.response.edit_message.await_args.kwargs
        self.assertIn("Claimed by: <@20>", edit["embed"].description)
        self.assertEqual(enabled_labels(edit["view"]), ["Close", "Delete"])
        self.assertEqual(said(interaction)[-1], "<@20> claimed the ticket.")

    async def test_claim_by_owner_is_refused_ephemeral(self):
        await self.fake.configure()
        channel = await self.fake.make_ticket()
        interaction = self.fake.interaction(self.fake.owner, channel)

        await self.actions.handle(interaction, Action.CLAIM)

        self.assertIsNone((await self.stored()).claimed_by)
        call = interaction.response.send_message.await_args
        self.assertEqual(call.args[0], "You cannot claim your own ticket.")
        self.assertTrue(call.kwargs["ephemeral"])

    async def test_stranger_is_refused(self):
        await self.fake.configure()
        channel = await self.fake.make_ticket()
        interaction = self.fake.interaction(self.fake.stranger, channel)

        await self.actions.handle(interaction, Action.CLOSE)

        self.assertFalse((await self.stored()).is_closed)

    async def test_close_revokes_send_and_requests_rename(self):
        await self.fake.configure()
        channel = await self.fake.make_ticket()
        interaction = self.fake.interaction(self.fake.staff, channel)

        await self.actions.handle(interaction, Action.CLOSE)

        self.assertTrue((await self.stored()).is_closed)
        member, kwargs = (
            channel.set_permissions.await_args.args[0],
            channel.set_permissions.await_args.kwargs,
        )
        self.assertIs(member, self.fake.owner)
        self.assertFalse(kwargs["overwrite"].send_messages)
        self.renamer.request.assert_called_once_with(
            channel, "closed-0001-max-mustermann"
        )
        self.assertEqual(said(interaction)[-1], "<@20> closed the ticket.")

    async def test_close_by_owner_respects_setting(self):
        await self.fake.configure(allow_user_close=False)
        channel = await self.fake.make_ticket()

        refused = self.fake.interaction(self.fake.owner, channel)
        await self.actions.handle(refused, Action.CLOSE)
        self.assertFalse((await self.stored()).is_closed)
        self.assertEqual(said(refused), ["You are not allowed to close this ticket."])

        await tickets.update_settings(GUILD_ID, allow_user_close=True)
        await self.actions.handle(
            self.fake.interaction(self.fake.owner, channel), Action.CLOSE
        )
        self.assertTrue((await self.stored()).is_closed)

    async def test_reopen_restores_send_and_name(self):
        await self.fake.configure()
        channel = await self.fake.make_ticket(is_closed=True)
        interaction = self.fake.interaction(self.fake.staff, channel)

        await self.actions.handle(interaction, Action.REOPEN)

        self.assertFalse((await self.stored()).is_closed)
        self.assertTrue(
            channel.set_permissions.await_args.kwargs["overwrite"].send_messages
        )
        self.renamer.request.assert_called_once_with(
            channel, "ticket-0001-max-mustermann"
        )

    async def test_reopen_of_archived_ticket_moves_channel_back(self):
        await self.fake.configure(archive_category_id=ARCHIVE_ID)
        channel = await self.fake.make_ticket(is_closed=True, is_archived=True)

        await self.actions.handle(
            self.fake.interaction(self.fake.staff, channel), Action.REOPEN
        )

        self.assertIs(channel.category, self.fake.category)
        self.assertFalse((await self.stored()).is_archived)

    async def test_reopen_into_full_category_is_refused(self):
        await self.fake.configure(archive_category_id=ARCHIVE_ID)
        channel = await self.fake.make_ticket(is_closed=True, is_archived=True)
        self.fake.category.channels = [MagicMock() for _ in range(50)]
        interaction = self.fake.interaction(self.fake.staff, channel)

        await self.actions.handle(interaction, Action.REOPEN)

        self.assertTrue((await self.stored()).is_closed)
        self.assertIn("The ticket category is full.", said(interaction)[0])

    async def test_actions_work_when_owner_left_the_guild(self):
        await self.fake.configure()
        channel = await self.fake.make_ticket()
        del self.fake.members[OWNER_ID]

        await self.actions.handle(
            self.fake.interaction(self.fake.staff, channel), Action.CLOSE
        )
        self.assertTrue((await self.stored()).is_closed)
        self.renamer.request.assert_called_with(channel, "closed-0001-max-mustermann")

        await self.actions.handle(
            self.fake.interaction(self.fake.staff, channel), Action.REOPEN
        )
        self.assertFalse((await self.stored()).is_closed)
        channel.set_permissions.assert_not_awaited()

    async def test_module_disabled_refuses_buttons(self):
        await self.fake.configure()
        channel = await self.fake.make_ticket()
        await cog_settings.set_enabled(GUILD_ID, "ticket", False)
        interaction = self.fake.interaction(self.fake.staff, channel)

        await self.actions.handle(interaction, Action.CLOSE)

        self.assertFalse((await self.stored()).is_closed)
        self.assertEqual(said(interaction), ["This module is disabled on this server."])

    async def test_click_outside_a_ticket_channel(self):
        await self.fake.configure()
        other = make_category(1)
        other.id = 4242
        interaction = self.fake.interaction(self.fake.staff, other)

        await self.actions.handle(interaction, Action.CLOSE)

        self.assertEqual(said(interaction), ["This channel is not a ticket."])

    async def test_legacy_ticket_without_control_message_adopts_clicked_message(self):
        await self.fake.configure()
        channel = await self.fake.make_ticket()
        await GuildTicket.objects.filter(channel_id=100).aupdate(
            control_message_id=None
        )
        interaction = self.fake.interaction(self.fake.staff, channel, message_id=4711)

        await self.actions.handle(interaction, Action.CLAIM)

        self.assertEqual((await self.stored()).control_message_id, 4711)


class DeleteTest(ActionsTestCase):
    async def test_delete_asks_first_then_deletes_channel_and_row(self):
        await self.fake.configure()
        channel = await self.fake.make_ticket()
        interaction = self.fake.interaction(self.fake.admin, channel)

        await self.actions.handle(interaction, Action.DELETE)

        call = interaction.response.send_message.await_args
        self.assertEqual(call.args[0], "Delete this ticket? This cannot be undone.")
        self.assertIsInstance(call.kwargs["view"], ConfirmDeleteView)
        self.assertTrue(call.kwargs["ephemeral"])
        self.assertEqual(await GuildTicket.objects.acount(), 1)
        channel.delete.assert_not_awaited()

        await self.actions.delete(self.fake.interaction(self.fake.admin, channel))

        channel.delete.assert_awaited_once()
        self.assertEqual(await GuildTicket.objects.acount(), 0)

    async def test_delete_by_staff_without_admin_is_refused(self):
        await self.fake.configure()
        channel = await self.fake.make_ticket()
        interaction = self.fake.interaction(self.fake.staff, channel)

        await self.actions.handle(interaction, Action.DELETE)
        await self.actions.delete(self.fake.interaction(self.fake.staff, channel))

        self.assertEqual(said(interaction), ["Only admins can delete a ticket."])
        channel.delete.assert_not_awaited()
        self.assertEqual(await GuildTicket.objects.acount(), 1)

    async def test_ticket_is_kept_when_the_channel_cannot_be_deleted(self):
        await self.fake.configure()
        channel = await self.fake.make_ticket()
        response = MagicMock(status=403, reason="Forbidden")
        channel.delete = AsyncMock(side_effect=discord.Forbidden(response, "nope"))
        interaction = self.fake.interaction(self.fake.admin, channel)

        await self.actions.delete(interaction)

        self.assertEqual(await GuildTicket.objects.acount(), 1)
        self.assertIn("permission", said(interaction)[-1])
