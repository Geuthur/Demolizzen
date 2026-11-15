# Standard Library
from datetime import timedelta

# Django
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

# Demolizzen
from demolizzen.models import GuildTicket, GuildTicketSettings
from demolizzen.services import guilds, tickets
from demolizzen.services.errors import (
    TicketLimitReached,
    TicketNotConfigured,
    TicketNotFound,
    TicketPermissionDenied,
    TicketStateError,
)
from demolizzen.services.tickets import Action, Actor

OWNER = Actor(user_id=10)
STAFF = Actor(user_id=20, is_staff=True)
ADMIN = Actor(user_id=30, is_admin=True)
STRANGER = Actor(user_id=40)
STAFF_OWNER = Actor(user_id=10, is_staff=True)


def ticket_of(user_id: int = 10, **fields) -> GuildTicket:
    return GuildTicket(ticket_number=1, channel_id=100, user_id=user_id, **fields)


def settings_with(close: bool, reopen: bool) -> GuildTicketSettings:
    return GuildTicketSettings(allow_user_close=close, allow_user_reopen=reopen)


class RightsTableTest(SimpleTestCase):
    def test_every_cell_of_the_rights_table(self):
        for allow in (True, False):
            settings = settings_with(close=allow, reopen=allow)
            table = {
                (Action.CLAIM, OWNER): False,
                (Action.CLAIM, STAFF): True,
                (Action.CLAIM, ADMIN): True,
                (Action.CLOSE, OWNER): allow,
                (Action.CLOSE, STAFF): True,
                (Action.CLOSE, ADMIN): True,
                (Action.REOPEN, OWNER): allow,
                (Action.REOPEN, STAFF): True,
                (Action.REOPEN, ADMIN): True,
                (Action.DELETE, OWNER): False,
                (Action.DELETE, STAFF): False,
                (Action.DELETE, ADMIN): True,
            }
            for (action, actor), expected in table.items():
                with self.subTest(action=action, actor=actor, allow=allow):
                    self.assertIs(
                        tickets.is_allowed(action, actor, ticket_of(), settings),
                        expected,
                    )

    def test_close_and_reopen_settings_are_independent(self):
        settings = settings_with(close=True, reopen=False)

        self.assertTrue(tickets.is_allowed(Action.CLOSE, OWNER, ticket_of(), settings))
        self.assertFalse(
            tickets.is_allowed(Action.REOPEN, OWNER, ticket_of(), settings)
        )

    def test_stranger_may_do_nothing(self):
        settings = settings_with(close=True, reopen=True)
        for action in Action:
            with self.subTest(action=action):
                self.assertFalse(
                    tickets.is_allowed(action, STRANGER, ticket_of(), settings)
                )

    def test_staff_member_on_own_ticket(self):
        settings = settings_with(close=False, reopen=False)
        ticket = ticket_of()

        self.assertTrue(tickets.is_allowed(Action.CLOSE, STAFF_OWNER, ticket, settings))
        self.assertTrue(
            tickets.is_allowed(Action.REOPEN, STAFF_OWNER, ticket, settings)
        )
        self.assertFalse(
            tickets.is_allowed(Action.CLAIM, STAFF_OWNER, ticket, settings)
        )

    def test_admin_may_not_claim_own_ticket(self):
        admin_owner = Actor(user_id=10, is_admin=True)

        self.assertFalse(
            tickets.is_allowed(
                Action.CLAIM, admin_owner, ticket_of(), settings_with(True, True)
            )
        )


class ChannelNameTest(SimpleTestCase):
    def test_open_and_closed_names(self):
        self.assertEqual(
            tickets.channel_name(42, "Max Mustermann!", False),
            "ticket-0042-max-mustermann",
        )
        self.assertEqual(
            tickets.channel_name(42, "Max Mustermann!", True),
            "closed-0042-max-mustermann",
        )

    def test_name_without_usable_characters(self):
        for name in ("", "!!!", "😀😀", None):
            with self.subTest(name=name):
                self.assertEqual(
                    tickets.channel_name(42, name, False), "ticket-0042-user"
                )

    def test_long_names_are_cut(self):
        name = tickets.channel_name(42, "a" * 150, True)

        self.assertLessEqual(len(name), 100)
        self.assertTrue(name.startswith("closed-0042-aaa"))

    def test_large_numbers_keep_all_digits(self):
        self.assertEqual(tickets.channel_name(12345, "x", False), "ticket-12345-x")


class TicketTestCase(TestCase):
    async def configure(self, **fields):
        await guilds.ensure_guild(1, "Alpha")
        defaults = {"category_id": 500, "roles": [900]}
        defaults.update(fields)
        return await tickets.update_settings(1, **defaults)

    async def make_ticket(self, number=1, channel_id=100, user_id=10, **fields):
        ticket = await tickets.create_ticket(1, number, channel_id, user_id, "Subject")
        if fields:
            await GuildTicket.objects.filter(pk=ticket.pk).aupdate(**fields)
        return ticket

    async def stored(self, channel_id=100) -> GuildTicket:
        return await GuildTicket.objects.aget(channel_id=channel_id)


class OpenTest(TicketTestCase):
    async def test_unconfigured_guild_cannot_open(self):
        await guilds.ensure_guild(1, "Alpha")
        for fields in ({}, {"category_id": 500}, {"roles": [900]}):
            with self.subTest(fields=fields):
                await GuildTicketSettings.objects.filter(guild_id=1).aupdate(
                    category_id=None, roles=None
                )
                if fields:
                    await tickets.update_settings(1, **fields)

                with self.assertRaises(TicketNotConfigured):
                    await tickets.check_can_open(1, 10)

    async def test_configured_guild_can_open(self):
        await self.configure()

        settings = await tickets.check_can_open(1, 10)

        self.assertEqual(settings.category_id, 500)

    async def test_limit_counts_only_open_tickets_of_the_member(self):
        await self.configure()
        await self.make_ticket(1, 100, user_id=10, is_closed=True)
        await self.make_ticket(2, 101, user_id=11)
        await tickets.check_can_open(1, 10)

        await self.make_ticket(3, 102, user_id=10)

        with self.assertRaises(TicketLimitReached):
            await tickets.check_can_open(1, 10)

    async def test_higher_limit_allows_more(self):
        await self.configure(max_open_tickets=2)
        await self.make_ticket(1, 100)

        await tickets.check_can_open(1, 10)

    async def test_allocate_number_counts_up(self):
        await self.configure()

        numbers = [await tickets.allocate_number(1) for _ in range(3)]

        self.assertEqual(numbers, [1, 2, 3])
        self.assertEqual(
            (await GuildTicketSettings.objects.aget(guild_id=1)).ticket_count, 4
        )

    async def test_create_ticket_stores_subject_and_message(self):
        await self.configure()

        ticket = await tickets.create_ticket(1, 7, 100, 10, "Login", 555)

        self.assertEqual(ticket.subject, "Login")
        self.assertEqual((await self.stored()).control_message_id, 555)

    async def test_long_subject_is_cut(self):
        await self.configure()

        ticket = await tickets.create_ticket(1, 7, 100, 10, "x" * 150)

        self.assertEqual(len(ticket.subject), 100)


class StateTest(TicketTestCase):
    async def test_claim_sets_claimed_by(self):
        await self.configure()
        await self.make_ticket()

        ticket = await tickets.claim(100, STAFF)

        self.assertEqual(ticket.claimed_by, 20)
        self.assertEqual((await self.stored()).claimed_by, 20)

    async def test_second_claim_is_refused(self):
        await self.configure()
        await self.make_ticket()
        await tickets.claim(100, STAFF)

        with self.assertRaisesMessage(TicketStateError, "already claimed"):
            await tickets.claim(100, ADMIN)

        self.assertEqual((await self.stored()).claimed_by, 20)

    async def test_claim_on_closed_ticket_is_refused(self):
        await self.configure()
        await self.make_ticket(is_closed=True)

        with self.assertRaises(TicketStateError):
            await tickets.claim(100, STAFF)

    async def test_close_records_who_and_when(self):
        await self.configure()
        await self.make_ticket()

        ticket = await tickets.close(100, STAFF)

        self.assertTrue(ticket.is_closed)
        self.assertEqual(ticket.closed_by, 20)
        self.assertIsNotNone((await self.stored()).closed_at)

    async def test_close_twice_is_refused(self):
        await self.configure()
        await self.make_ticket()
        await tickets.close(100, STAFF)

        with self.assertRaises(TicketStateError):
            await tickets.close(100, STAFF)

    async def test_owner_close_follows_setting(self):
        await self.configure(allow_user_close=False)
        await self.make_ticket()

        with self.assertRaises(TicketPermissionDenied):
            await tickets.close(100, OWNER)
        self.assertFalse((await self.stored()).is_closed)

        await tickets.update_settings(1, allow_user_close=True)
        await tickets.close(100, OWNER)
        self.assertTrue((await self.stored()).is_closed)

    async def test_reopen_resets_the_ticket(self):
        await self.configure()
        await self.make_ticket(
            is_closed=True,
            is_archived=True,
            closed_by=20,
            closed_at=timezone.now(),
            claimed_by=20,
        )

        ticket = await tickets.reopen(100, STAFF)

        self.assertFalse(ticket.is_closed)
        stored = await self.stored()
        self.assertFalse(stored.is_archived)
        self.assertIsNone(stored.closed_by)
        self.assertIsNone(stored.closed_at)
        self.assertIsNone(stored.claimed_by)

    async def test_reopen_of_open_ticket_is_refused(self):
        await self.configure()
        await self.make_ticket()

        with self.assertRaises(TicketStateError):
            await tickets.reopen(100, STAFF)

    async def test_owner_reopen_follows_setting(self):
        await self.configure(allow_user_reopen=False)
        await self.make_ticket(is_closed=True)

        with self.assertRaises(TicketPermissionDenied):
            await tickets.reopen(100, OWNER)

        self.assertTrue((await self.stored()).is_closed)

    async def test_permission_is_checked_before_state(self):
        await self.configure()
        await self.make_ticket(is_closed=True)

        with self.assertRaises(TicketPermissionDenied):
            await tickets.close(100, STRANGER)

    async def test_delete_by_staff_is_refused(self):
        await self.configure()
        await self.make_ticket()

        with self.assertRaises(TicketPermissionDenied):
            await tickets.delete(100, STAFF)

        self.assertEqual(await GuildTicket.objects.acount(), 1)

    async def test_delete_by_admin_removes_the_ticket(self):
        await self.configure()
        await self.make_ticket(is_closed=True)

        ticket = await tickets.delete(100, ADMIN)

        self.assertEqual(ticket.ticket_number, 1)
        self.assertEqual(await GuildTicket.objects.acount(), 0)

    async def test_unknown_channel(self):
        await self.configure()

        for call in (tickets.claim, tickets.close, tickets.reopen, tickets.delete):
            with self.subTest(call=call.__name__):
                with self.assertRaises(TicketNotFound):
                    await call(999, ADMIN)
        with self.assertRaises(TicketNotFound):
            await tickets.get_by_channel(999)

    async def test_check_action_changes_nothing(self):
        await self.configure()
        await self.make_ticket()

        ticket = await tickets.check_action(100, Action.DELETE, ADMIN)

        self.assertEqual(ticket.channel_id, 100)
        self.assertEqual(await GuildTicket.objects.acount(), 1)
        with self.assertRaises(TicketPermissionDenied):
            await tickets.check_action(100, Action.DELETE, STAFF)
        with self.assertRaises(TicketStateError):
            await tickets.check_action(100, Action.REOPEN, STAFF)

    async def test_set_control_message(self):
        await self.configure()
        await self.make_ticket()

        await tickets.set_control_message(100, 777)

        self.assertEqual((await self.stored()).control_message_id, 777)


class ArchiveTest(TicketTestCase):
    async def test_due_for_archive(self):
        await self.configure(archive_category_id=600, auto_archive_days=3)
        now = timezone.now()
        await self.make_ticket(
            1, 100, is_closed=True, closed_at=now - timedelta(days=4)
        )
        await self.make_ticket(
            2, 101, is_closed=True, closed_at=now - timedelta(days=2)
        )
        await self.make_ticket(3, 102)
        await self.make_ticket(
            4, 103, is_closed=True, is_archived=True, closed_at=now - timedelta(days=9)
        )

        due = await tickets.due_for_archive(now)

        self.assertEqual([ticket.channel_id for ticket in due], [100])

    async def test_nothing_is_due_without_archive_category(self):
        await self.configure(auto_archive_days=1)
        await self.make_ticket(
            is_closed=True, closed_at=timezone.now() - timedelta(days=30)
        )

        self.assertEqual(await tickets.due_for_archive(), [])

    async def test_mark_archived(self):
        await self.configure()
        ticket = await self.make_ticket(is_closed=True)

        await tickets.mark_archived(ticket.pk)

        self.assertTrue((await self.stored()).is_archived)

    async def test_active_tickets_excludes_archived_and_other_guilds(self):
        await self.configure()
        await guilds.ensure_guild(2, "Beta")
        await self.make_ticket(1, 100)
        await self.make_ticket(2, 101, is_closed=True)
        await self.make_ticket(3, 102, is_closed=True, is_archived=True)
        await tickets.create_ticket(2, 1, 200, 10, "Other")

        active = await tickets.active_tickets([1])

        self.assertEqual(sorted(t.channel_id for t in active), [100, 101])

    async def test_remove_by_channel(self):
        await self.configure()
        await self.make_ticket()

        self.assertTrue(await tickets.remove_by_channel(100))
        self.assertFalse(await tickets.remove_by_channel(100))
        await tickets.check_can_open(1, 10)
