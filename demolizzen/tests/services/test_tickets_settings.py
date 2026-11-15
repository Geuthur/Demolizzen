# Django
from django.test import TestCase

# Demolizzen
from demolizzen.models import GuildTicket, GuildTicketSettings
from demolizzen.services import guilds, tickets
from demolizzen.services.errors import GuildNotRegistered, InvalidTicketSetting


class GetSettingsTest(TestCase):
    async def test_get_settings_creates_row_with_defaults(self):
        await guilds.ensure_guild(1, "Alpha")
        await GuildTicketSettings.objects.filter(guild_id=1).adelete()

        settings = await tickets.get_settings(1)

        self.assertEqual(settings.max_open_tickets, 1)
        self.assertIsNone(settings.log_channel_id)
        self.assertEqual(await GuildTicketSettings.objects.acount(), 1)

    async def test_get_settings_unregistered_guild_raises(self):
        with self.assertRaises(GuildNotRegistered):
            await tickets.get_settings(99)


class UpdateSettingsTest(TestCase):
    async def test_update_settings_persists_each_allowed_field(self):
        await guilds.ensure_guild(1, "Alpha")
        values = {
            "category_id": 11,
            "archive_category_id": 12,
            "log_channel_id": 13,
            "roles": [21, 22],
            "auto_archive_days": 7,
            "max_open_tickets": 3,
            "allow_user_close": False,
            "allow_user_reopen": False,
        }
        self.assertEqual(set(values), set(tickets.SETTING_FIELDS))

        for field, value in values.items():
            with self.subTest(field=field):
                returned = await tickets.update_settings(1, **{field: value})

                self.assertEqual(getattr(returned, field), value)
                stored = await GuildTicketSettings.objects.aget(guild_id=1)
                self.assertEqual(getattr(stored, field), value)

    async def test_channels_can_be_cleared(self):
        await guilds.ensure_guild(1, "Alpha")
        await tickets.update_settings(1, log_channel_id=13)

        settings = await tickets.update_settings(1, log_channel_id=None)

        self.assertIsNone(settings.log_channel_id)

    async def test_update_settings_rejects_unknown_field(self):
        await guilds.ensure_guild(1, "Alpha")

        with self.assertRaises(InvalidTicketSetting):
            await tickets.update_settings(1, ticket_count=500)

    async def test_update_settings_rejects_out_of_range(self):
        await guilds.ensure_guild(1, "Alpha")
        bad = [
            {"auto_archive_days": 0},
            {"auto_archive_days": 366},
            {"max_open_tickets": 0},
            {"max_open_tickets": 11},
            {"roles": "x"},
            {"roles": ["a"]},
            {"allow_user_close": "yes"},
            {"category_id": "abc"},
        ]
        for fields in bad:
            with self.subTest(fields=fields):
                with self.assertRaises(InvalidTicketSetting):
                    await tickets.update_settings(1, **fields)

        stored = await GuildTicketSettings.objects.aget(guild_id=1)
        self.assertEqual(stored.auto_archive_days, 3)

    async def test_update_settings_unregistered_guild_raises(self):
        with self.assertRaises(GuildNotRegistered):
            await tickets.update_settings(99, max_open_tickets=2)


class StaffRolesTest(TestCase):
    def test_staff_role_ids_ignores_garbage(self):
        cases = [
            (None, []),
            ({"a": 1}, []),
            (["1", 5, None, True], [5]),
            ([7, 8], [7, 8]),
        ]
        for stored, expected in cases:
            with self.subTest(stored=stored):
                settings = GuildTicketSettings(roles=stored)
                self.assertEqual(tickets.staff_role_ids(settings), expected)


class TicketFieldsTest(TestCase):
    async def test_ticket_has_subject_and_control_message_fields(self):
        await guilds.ensure_guild(1, "Alpha")

        ticket = await GuildTicket.objects.acreate(
            guild_id=1, ticket_number=1, channel_id=100, user_id=10
        )

        self.assertEqual(ticket.subject, "")
        self.assertIsNone(ticket.control_message_id)
