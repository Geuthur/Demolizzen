# Standard Library
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# Django
from django.test import TestCase

# Demolizzen
from demolizzen.cogs.killmail.killmail import Killmail
from demolizzen.models import UserProfile, ZKillboard
from demolizzen.services import cog_settings, guilds
from demolizzen.tests.helpers import make_guild


def make_cog() -> Killmail:
    with patch("discord.ext.tasks.Loop.start"):
        return Killmail(MagicMock())


def make_sub(sub_id: int, guild_id: int):
    return SimpleNamespace(
        id=sub_id,
        channel=SimpleNamespace(id=sub_id * 100, guild=SimpleNamespace(id=guild_id)),
        mail=AsyncMock(),
    )


class KillmailDeliveryTest(TestCase):
    def setUp(self):
        cog_settings.invalidate()

    async def test_killmails_are_not_delivered_to_guilds_that_disabled_the_module(
        self,
    ):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.ensure_guild(2, "Beta")
        await cog_settings.set_enabled(2, "killmail", False)
        cog = make_cog()
        cog.subs = {1: make_sub(1, guild_id=1), 2: make_sub(2, guild_id=2)}
        killmail = SimpleNamespace(zkb=SimpleNamespace(is_npc=False))

        with patch(
            "demolizzen.cogs.killmail.killmail.KillmailManager._create_from_zkb",
            return_value=killmail,
        ):
            cog.process_mail({"killmail_id": 1})
            await asyncio.sleep(0.05)

        cog.subs[1].mail.assert_awaited_once_with(killmail)
        cog.subs[2].mail.assert_not_awaited()


class KillmailGuildRemoveTest(TestCase):
    def setUp(self):
        cog_settings.invalidate()

    def test_listens_to_the_event_pycord_dispatches(self):
        events = [event for event, _ in Killmail.__cog_listeners__]

        self.assertIn("on_guild_remove", events)
        self.assertNotIn("on_guild_leave", events)

    async def test_subscriptions_are_removed_even_when_module_is_disabled(self):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.ensure_members(1, [(10, "owner")])
        owner = await UserProfile.objects.aget(user_id=10)
        row = await ZKillboard.objects.acreate(
            channel_id=100, guild_id=1, owner=owner, threshold=0
        )
        await cog_settings.set_enabled(1, "killmail", False)
        cog = make_cog()
        cog.subs = {row.id: make_sub(row.id, guild_id=1)}

        await cog.on_guild_remove(make_guild(1, "Alpha"))

        self.assertEqual(cog.subs, {})
        self.assertEqual(await ZKillboard.objects.acount(), 0)
