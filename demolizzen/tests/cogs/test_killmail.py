# Standard Library
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# Discord
import discord

# Django
from django.test import TestCase

# Demolizzen
from demolizzen.cogs.killmail.killmail import PAUSED_NOTICE, Killmail
from demolizzen.models import ZKillboard
from demolizzen.services import cog_settings, guilds, killmails
from demolizzen.tests.helpers import make_ctx, make_guild, make_member

NAMES = {90: "Victim", 100: "VCorp", 200: "VAlly", 500: "Killer", 300: "KCorp"}


def package(killmail_id=1, value=5_000_000, npc=False) -> dict:
    """A killmail as the zKillboard feed delivers it."""
    return {
        "killmail_id": killmail_id,
        "hash": "abc",
        "esi": {
            "killmail_time": "2026-11-15T10:00:00Z",
            "solar_system_id": 30000142,
            "victim": {
                "character_id": 90,
                "corporation_id": 100,
                "alliance_id": 200,
                "ship_type_id": 587,
                "damage_taken": 10,
            },
            "attackers": [
                {"character_id": 501, "corporation_id": 301, "final_blow": False},
                {
                    "character_id": 500,
                    "corporation_id": 300,
                    "alliance_id": 400,
                    "ship_type_id": 588,
                    "final_blow": True,
                },
            ],
        },
        "zkb": {"totalValue": value, "npc": npc, "attackerCount": 2, "hash": "abc"},
    }


def perms(allowed: bool) -> SimpleNamespace:
    return SimpleNamespace(
        view_channel=allowed, send_messages=allowed, embed_links=allowed
    )


def make_channel(channel_id: int, guild, can_send: bool = True) -> MagicMock:
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = channel_id
    channel.guild = guild
    channel.mention = f"<#{channel_id}>"
    channel.send = AsyncMock()
    channel.permissions_for.return_value = perms(can_send)
    return channel


def http_error(cls, status: int):
    return cls(MagicMock(status=status, reason="nope"), "nope")


class KillmailCogTestCase(TestCase):
    def setUp(self):
        cog_settings.invalidate()
        self.guild = make_guild(1, "Alpha")
        self.guild.unavailable = False
        self.guild.system_channel = None
        self.channels = {}
        self.bot = MagicMock()
        self.bot.get_channel.side_effect = lambda cid: self.channels.get(cid)
        self.bot.get_guild.side_effect = lambda gid: {1: self.guild}.get(gid)
        esi = self.bot.esi_data
        esi.resolve_names = AsyncMock(return_value=dict(NAMES))
        esi.get_region_id = AsyncMock(return_value=10000002)
        esi.item_info_db = AsyncMock(
            side_effect=lambda type_id: SimpleNamespace(name=f"Ship {type_id}")
        )
        esi.get_or_create_solar_system = AsyncMock(
            return_value=SimpleNamespace(solarSystemName="Jita")
        )
        esi.get_celestial_info = AsyncMock(return_value=None)
        with patch("discord.ext.tasks.Loop.start"):
            self.cog = Killmail(self.bot)

    def channel(self, channel_id: int, can_send: bool = True, guild=None):
        channel = make_channel(channel_id, guild or self.guild, can_send)
        self.channels[channel_id] = channel
        return channel

    async def subscribe(self, channel_id, group_id=6, guild_id=1, **kwargs):
        await guilds.ensure_guild(guild_id, f"G{guild_id}")
        rule, _ = await killmails.add_subscription(
            guild_id, 77, "owner", channel_id, group_id, **kwargs
        )
        self.cog.rules[rule.id] = rule
        return rule

    async def feed(self, *packages):
        for data in packages:
            await self.cog.handle_killmail(data)
            await asyncio.gather(*list(self.cog._deliveries))


class KillmailDeliveryTest(KillmailCogTestCase):
    async def test_matching_killmail_is_posted_once_per_channel(self):
        both = self.channel(10)
        other = self.channel(11)
        await self.subscribe(10)
        await self.subscribe(10, group_id=300)
        await self.subscribe(11, group_id=999)

        await self.feed(package())

        both.send.assert_awaited_once()
        other.send.assert_not_awaited()

    async def test_embed_names_the_victim_and_the_final_blow(self):
        channel = self.channel(10)
        await self.subscribe(10)

        await self.feed(package())

        embed = channel.send.await_args.kwargs["embed"]
        self.assertEqual(embed.author.name, "VAlly")
        self.assertEqual(embed.title, "Ship 587 destroyed in Jita")
        self.assertEqual(embed.url, "https://zkillboard.com/kill/1/")
        text = embed.fields[0].value
        self.assertIn("**[Victim](https://zkillboard.com/character/90/)**", text)
        self.assertIn("[VCorp](https://zkillboard.com/corporation/100/)", text)
        self.assertIn("worth **`5,000,000`** ISK", text)
        self.assertIn("Final Blow by **[Killer]", text)
        self.assertIn("in a `Ship 588`", text)
        self.assertIn("**Attackers: `2`**", text)

    async def test_names_are_resolved_in_one_call(self):
        self.channel(10)
        self.channel(11)
        await self.subscribe(10)
        await self.subscribe(11)

        await self.feed(package())

        self.bot.esi_data.resolve_names.assert_awaited_once()
        self.assertEqual(
            set(self.bot.esi_data.resolve_names.await_args.args[0]),
            {90, 100, 200, 500, 300, 400},
        )
        self.bot.esi_data.get_or_create_solar_system.assert_awaited_once()

    async def test_non_matching_killmail_is_not_enriched(self):
        channel = self.channel(10)
        await self.subscribe(10, group_id=999)

        await self.feed(package())

        channel.send.assert_not_awaited()
        self.bot.esi_data.resolve_names.assert_not_awaited()
        self.bot.esi_data.item_info_db.assert_not_awaited()

    async def test_npc_killmail_is_ignored(self):
        channel = self.channel(10)
        await self.subscribe(10)

        await self.feed(package(npc=True))

        channel.send.assert_not_awaited()
        self.bot.esi_data.resolve_names.assert_not_awaited()

    async def test_unreadable_killmail_is_ignored(self):
        channel = self.channel(10)
        await self.subscribe(10)

        await self.feed({"killmail_id": 5})

        channel.send.assert_not_awaited()

    async def test_repeated_killmail_is_posted_once(self):
        channel = self.channel(10)
        await self.subscribe(10)

        await self.feed(package(1), package(1), package(2))

        self.assertEqual(channel.send.await_count, 2)

    async def test_region_subscription_uses_the_region_of_the_system(self):
        channel = self.channel(10)
        await self.subscribe(10, group_id=10000002)

        await self.feed(package())

        self.bot.esi_data.get_region_id.assert_awaited_once_with(30000142)
        channel.send.assert_awaited_once()

    async def test_loss_is_red_and_kill_is_green(self):
        loss = self.channel(10)
        kill = self.channel(11)
        await self.subscribe(10, group_id=100, losses=True)
        await self.subscribe(11, group_id=300)

        await self.feed(package())

        self.assertEqual(
            loss.send.await_args.kwargs["embed"].colour, discord.Colour.red()
        )
        self.assertEqual(
            kill.send.await_args.kwargs["embed"].colour, discord.Colour.green()
        )

    async def test_killmails_are_not_delivered_to_guilds_that_disabled_the_module(
        self,
    ):
        other_guild = make_guild(2, "Beta")
        alpha = self.channel(10)
        beta = self.channel(20, guild=other_guild)
        await self.subscribe(10)
        await self.subscribe(20, guild_id=2)
        await cog_settings.set_enabled(2, "killmail", False)

        await self.feed(package())

        alpha.send.assert_awaited_once()
        beta.send.assert_not_awaited()

    async def test_delivery_failure_does_not_stop_other_channels(self):
        broken = self.channel(10)
        fine = self.channel(11)
        broken.send.side_effect = http_error(discord.HTTPException, 500)
        await self.subscribe(10)
        await self.subscribe(11)

        with self.assertLogs("demolizzen.cogs.killmail.killmail", "ERROR"):
            await self.feed(package())

        fine.send.assert_awaited_once()

    async def test_failing_lookup_still_posts_the_killmail(self):
        channel = self.channel(10)
        await self.subscribe(10)
        self.bot.esi_data.item_info_db.side_effect = RuntimeError("database away")

        with self.assertLogs("demolizzen.cogs.killmail.killmailmanager", "WARNING"):
            await self.feed(package())

        embed = channel.send.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "Unknown destroyed in Jita")

    async def test_feed_waits_while_five_deliveries_are_running(self):
        channel = self.channel(10)
        await self.subscribe(10)
        release = asyncio.Event()

        async def blocked(**kwargs):
            await release.wait()

        channel.send.side_effect = blocked

        for number in range(Killmail.MAX_DELIVERIES):
            await asyncio.wait_for(self.cog.handle_killmail(package(number + 1)), 1)
        sixth = asyncio.ensure_future(self.cog.handle_killmail(package(99)))
        await asyncio.sleep(0.05)
        self.assertFalse(sixth.done())

        release.set()
        await asyncio.wait_for(sixth, 1)
        await asyncio.gather(*list(self.cog._deliveries))
        self.assertEqual(channel.send.await_count, 6)

    def test_feed_hands_killmails_to_the_cog(self):
        self.assertEqual(self.cog.feed._handle, self.cog.handle_killmail)
        self.bot.session = "session"
        self.assertEqual(self.cog.feed._get_session(), "session")


class KillmailPermissionTest(KillmailCogTestCase):
    async def test_missing_permission_pauses_and_notifies_once(self):
        target = self.channel(10, can_send=False)
        main = self.channel(50)
        await self.subscribe(10)
        await guilds.set_main_channel(1, 50)

        await self.feed(package(1), package(2))

        target.send.assert_not_awaited()
        main.send.assert_awaited_once_with(
            "Killmail feed for <#10> is paused: I cannot send messages there."
        )
        self.assertEqual(
            PAUSED_NOTICE.format(channel_id=10), main.send.await_args.args[0]
        )
        self.bot.esi_data.resolve_names.assert_not_awaited()
        self.assertEqual(await ZKillboard.objects.acount(), 1)

    async def test_notice_falls_back_to_the_system_channel(self):
        self.channel(10, can_send=False)
        system = make_channel(60, self.guild)
        self.guild.system_channel = system
        await self.subscribe(10)

        await self.feed(package())

        system.send.assert_awaited_once()

    async def test_notice_is_not_sent_into_the_paused_channel_itself(self):
        target = self.channel(10, can_send=False)
        await self.subscribe(10)
        await guilds.set_main_channel(1, 10)

        await self.feed(package())

        target.send.assert_not_awaited()

    async def test_feed_resumes_when_permission_returns(self):
        target = self.channel(10, can_send=False)
        main = self.channel(50)
        await self.subscribe(10)
        await guilds.set_main_channel(1, 50)
        await self.feed(package(1))

        target.permissions_for.return_value = perms(True)
        await self.feed(package(2))
        target.permissions_for.return_value = perms(False)
        await self.feed(package(3))

        target.send.assert_awaited_once()
        self.assertEqual(main.send.await_count, 2)

    async def test_refused_message_pauses_without_trying_every_killmail(self):
        target = self.channel(10)
        main = self.channel(50)
        target.send.side_effect = http_error(discord.Forbidden, 403)
        await self.subscribe(10)
        await guilds.set_main_channel(1, 50)

        await self.feed(package(1), package(2), package(3))

        target.send.assert_awaited_once()
        main.send.assert_awaited_once()

    async def test_refused_channel_is_tried_again_later(self):
        target = self.channel(10)
        target.send.side_effect = [http_error(discord.Forbidden, 403), None]
        await self.subscribe(10)

        with patch.object(Killmail, "RETRY_REFUSED_AFTER", 0):
            await self.feed(package(1))
        await self.feed(package(2))

        self.assertEqual(target.send.await_count, 2)

    async def test_deleted_channel_loses_its_subscriptions(self):
        gone = self.channel(10)
        gone.send.side_effect = http_error(discord.NotFound, 404)
        kept = self.channel(11)
        await self.subscribe(10)
        await self.subscribe(10, group_id=300)
        rule = await self.subscribe(11)

        await self.feed(package())

        self.assertEqual(list(self.cog.rules), [rule.id])
        self.assertEqual(
            [row.channel_id async for row in ZKillboard.objects.all()], [11]
        )
        kept.send.assert_awaited_once()


class KillmailUpkeepTest(KillmailCogTestCase):
    def test_listens_to_the_event_pycord_dispatches(self):
        events = [event for event, _ in Killmail.__cog_listeners__]

        self.assertIn("on_guild_remove", events)
        self.assertNotIn("on_guild_leave", events)

    async def test_subscriptions_are_removed_even_when_module_is_disabled(self):
        await self.subscribe(100)
        await cog_settings.set_enabled(1, "killmail", False)

        await self.cog.on_guild_remove(self.guild)

        self.assertEqual(self.cog.rules, {})
        self.assertEqual(await ZKillboard.objects.acount(), 0)

    async def test_load_rules_reads_the_database(self):
        rule = await self.subscribe(10)
        self.cog.rules = {}

        await self.cog.load_rules()

        self.assertEqual(self.cog.rules, {rule.id: rule})

    async def test_watcher_picks_up_what_the_web_panel_changed(self):
        rule = await self.subscribe(10)
        await self.cog.load_rules()
        # The panel is another process: only the database changes.
        await ZKillboard.objects.filter(pk=rule.id).aupdate(channel_id=11)
        added = await self.subscribe(12)

        await self.cog.watch_subscriptions.coro(self.cog)

        self.assertEqual(self.cog.rules[rule.id].channel_id, 11)
        self.assertIn(added.id, self.cog.rules)

    async def test_watcher_forgets_what_the_web_panel_removed(self):
        rule = await self.subscribe(10)
        await self.cog.load_rules()
        await ZKillboard.objects.filter(pk=rule.id).adelete()

        await self.cog.watch_subscriptions.coro(self.cog)

        self.assertEqual(self.cog.rules, {})

    async def test_watcher_keeps_the_known_subscriptions_when_the_database_fails(self):
        rule = await self.subscribe(10)
        await self.cog.load_rules()

        with (
            patch.object(killmails, "load_rules", side_effect=RuntimeError("away")),
            self.assertLogs(level="ERROR"),
        ):
            await self.cog.watch_subscriptions.coro(self.cog)

        self.assertEqual(self.cog.rules, {rule.id: rule})

    def test_watcher_looks_once_a_minute(self):
        self.assertEqual(Killmail.watch_subscriptions.seconds, 60)

    async def test_daily_check_removes_subscriptions_of_deleted_channels(self):
        self.channel(11)
        await self.subscribe(10)
        kept = await self.subscribe(11)
        self.cog.rules = {}

        await self.cog.check_subscriptions()

        self.assertEqual(self.cog.rules, {kept.id: kept})
        self.assertEqual(await ZKillboard.objects.acount(), 1)

    async def test_daily_check_keeps_subscriptions_of_unreachable_guilds(self):
        await self.subscribe(10)
        await self.subscribe(20, guild_id=2)
        self.guild.unavailable = True

        await self.cog.check_subscriptions()

        self.assertEqual(await ZKillboard.objects.acount(), 2)
        self.assertEqual(len(self.cog.rules), 2)


class KillmailCommandTest(KillmailCogTestCase):
    def setUp(self):
        super().setUp()
        self.author = make_member(77, "owner", manage_guild=True, guild=self.guild)
        self.ctx = make_ctx(self.guild, self.author)

    def said(self) -> str:
        return self.ctx.respond.await_args.args[0]

    async def test_add_and_remove_commands_update_rules(self):
        await guilds.ensure_guild(1, "Alpha")
        channel = self.channel(10)

        await self.cog.add_killmail.callback(self.cog, self.ctx, channel, 300, 1000)

        self.assertEqual(self.said(), "Killmail subscription added!")
        (rule,) = self.cog.rules.values()
        self.assertEqual(
            (rule.channel_id, rule.group_id, rule.threshold, rule.losses),
            (10, 300, 1000, False),
        )

        await self.cog.add_killmail.callback(self.cog, self.ctx, channel, 300, 5)
        self.assertEqual(
            self.said(),
            "A subscription with the same parameters already exists for this channel.",
        )

        await self.cog.remove_killmail.callback(self.cog, self.ctx, None, rule.id)
        self.assertEqual(self.said(), f"Killmail `{rule.id}` has been removed.")
        self.assertEqual(self.cog.rules, {})
        self.assertEqual(await ZKillboard.objects.acount(), 0)

    async def test_add_refuses_a_channel_the_bot_cannot_write_to(self):
        await guilds.ensure_guild(1, "Alpha")
        channel = self.channel(10, can_send=False)

        await self.cog.add_killmail.callback(self.cog, self.ctx, channel, 300, None)

        self.assertIn("I lack permission to send messages there", self.said())
        self.assertEqual(await ZKillboard.objects.acount(), 0)

    async def test_remove_with_a_foreign_id(self):
        rule = await self.subscribe(20, guild_id=2)

        await self.cog.remove_killmail.callback(self.cog, self.ctx, None, rule.id)

        self.assertEqual(
            self.said(),
            f"ID {rule.id} does not match any of your killmail subscriptions.",
        )
        self.assertEqual(len(self.cog.rules), 1)

    async def test_remove_all_of_a_channel(self):
        channel = self.channel(10)
        await self.subscribe(10)
        await self.subscribe(10, group_id=300)
        kept = await self.subscribe(11)

        await self.cog.remove_killmail.callback(self.cog, self.ctx, channel, None)

        self.assertIn("All killmail subs removed for <#10>.", self.said())
        self.assertEqual(list(self.cog.rules), [kept.id])

        await self.cog.remove_killmail.callback(self.cog, self.ctx, channel, None)
        self.assertEqual(self.said(), "No killmail subs for <#10>.")

    async def test_subscription_list(self):
        self.channel(10)
        first = await self.subscribe(10, threshold=1000)
        second = await self.subscribe(10, group_id=300, losses=True)
        await self.subscribe(20, guild_id=2)

        await self.cog.subscription_killmail.callback(self.cog, self.ctx, None)

        embed = self.ctx.respond.await_args.kwargs["embed"]
        self.assertEqual(
            embed.description.split("\n"),
            [
                f"`{first.id}`: <#10> | Kills over `1,000` ISK",
                f"`{second.id}`: <#10> | Kills and Losses over `1` ISK"
                " | matching ID `300`",
            ],
        )

    async def test_subscription_list_of_an_empty_channel(self):
        await self.subscribe(10)

        await self.cog.subscription_killmail.callback(
            self.cog, self.ctx, self.channel(11)
        )

        self.assertEqual(self.said(), "No subscriptions found.")


class KillmailNoticeFailureTest(KillmailCogTestCase):
    async def test_failing_notice_does_not_stop_other_channels(self):
        self.channel(10, can_send=False)
        fine = self.channel(11)
        await self.subscribe(10)
        await self.subscribe(11)

        with (
            patch(
                "demolizzen.cogs.killmail.killmail.guilds.get_main_channel",
                AsyncMock(side_effect=RuntimeError("database away")),
            ),
            self.assertLogs("demolizzen.cogs.killmail.killmail", "ERROR"),
        ):
            await self.feed(package())

        fine.send.assert_awaited_once()
