# Django
from django.test import SimpleTestCase, TestCase

# Demolizzen
from demolizzen.services import guilds
from demolizzen.web import access


def guild(guild_id=1, permissions="0", owner=False, **extra) -> dict:
    """A server as Discord lists it for the signed-in user."""
    return {
        "id": str(guild_id),
        "name": f"G{guild_id}",
        "owner": owner,
        "permissions": permissions,
        **extra,
    }


class CanManageTest(SimpleTestCase):
    def test_owner_administrator_and_manage_server_may_manage(self):
        self.assertTrue(access.can_manage(guild(owner=True)))
        self.assertTrue(access.can_manage(guild(permissions="8")))
        self.assertTrue(access.can_manage(guild(permissions="32")))
        self.assertTrue(access.can_manage(guild(permissions=str(0x20 | 0x400 | 0x800))))
        # Permission sets no longer fit into 53 bits; they arrive as text.
        self.assertTrue(access.can_manage(guild(permissions=str((1 << 60) | 0x8))))
        self.assertEqual((access.ADMINISTRATOR, access.MANAGE_GUILD), (0x8, 0x20))

    def test_other_members_may_not_manage(self):
        self.assertFalse(access.can_manage(guild(permissions="0")))
        # Manage Messages, Manage Channels, Kick, Ban: not enough.
        self.assertFalse(
            access.can_manage(guild(permissions=str(0x2000 | 0x10 | 0x2 | 0x4)))
        )
        self.assertFalse(access.can_manage(guild(permissions=str(1 << 60))))

    def test_broken_permission_values_may_not_manage(self):
        for value in (None, "", "abc", "8.5", [], {"bits": 8}):
            with self.subTest(value=value):
                self.assertFalse(access.can_manage(guild(permissions=value)))
        self.assertFalse(access.can_manage({"id": "1"}))
        self.assertFalse(access.can_manage(guild(owner="yes")))
        self.assertFalse(access.can_manage("not a guild"))


class ManageableGuildsTest(TestCase):
    async def test_only_registered_and_manageable_guilds_are_kept(self):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.ensure_guild(2, "Beta")
        await guilds.ensure_guild(3, "Gamma")
        listed = [
            guild(3, owner=True),
            guild(1, permissions="32"),
            guild(2, permissions="0"),  # registered, but no rights
            guild(4, owner=True),  # rights, but the bot is not there
            {"name": "no id", "owner": True},
            guild("abc", owner=True),
        ]

        self.assertEqual(await access.manageable_guild_ids(listed), [1, 3])

    async def test_nothing_listed(self):
        self.assertEqual(await access.manageable_guild_ids([]), [])
        self.assertEqual(await access.manageable_guild_ids("garbage"), [])
