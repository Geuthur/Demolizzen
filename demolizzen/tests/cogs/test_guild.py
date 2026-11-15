# Standard Library
from unittest.mock import AsyncMock, MagicMock, patch

# Django
from django.test import TestCase

# Demolizzen
from demolizzen.cogs.guild.guild import Guild
from demolizzen.models import GuildProfile, UserProfile, UserSettings
from demolizzen.services import guilds
from demolizzen.tests.helpers import make_ctx, make_guild, make_member


def make_cog(bot_guilds=()):
    bot = MagicMock()
    bot.guilds = list(bot_guilds)
    with patch("discord.ext.tasks.Loop.start"):
        return Guild(bot)


class GuildListenerTest(TestCase):
    async def test_on_guild_join_registers_guild_and_humans(self):
        guild = make_guild(
            1, "Alpha", members=[make_member(10, "a"), make_member(11, "b", bot=True)]
        )

        await make_cog().on_guild_join(guild)

        self.assertTrue(await GuildProfile.objects.filter(guild_id=1).aexists())
        self.assertEqual(
            [p.user_id async for p in UserProfile.objects.filter(guild_id=1)], [10]
        )
        self.assertEqual(await UserSettings.objects.acount(), 1)

    async def test_on_guild_join_of_known_guild_adds_missing_members(self):
        await guilds.ensure_guild(1, "Alpha")
        guild = make_guild(1, "Alpha", members=[make_member(10, "a")])

        await make_cog().on_guild_join(guild)

        self.assertEqual(await UserProfile.objects.filter(guild_id=1).acount(), 1)

    async def test_on_guild_remove_deletes_profile(self):
        await guilds.ensure_guild(1, "Alpha")

        await make_cog().on_guild_remove(make_guild(1, "Alpha"))

        self.assertFalse(await GuildProfile.objects.filter(guild_id=1).aexists())

    async def test_on_guild_remove_of_unknown_guild_is_quiet(self):
        await make_cog().on_guild_remove(make_guild(99, "Ghost"))

    async def test_on_guild_update_renames(self):
        await guilds.ensure_guild(1, "Alpha")

        await make_cog().on_guild_update(make_guild(1, "Alpha"), make_guild(1, "Beta"))

        self.assertEqual(
            (await GuildProfile.objects.aget(guild_id=1)).guild_name, "Beta"
        )

    async def test_on_member_update_renames(self):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.ensure_members(1, [(10, "old")])
        guild = make_guild(1, "Alpha")

        await make_cog().on_member_update(
            make_member(10, "old", guild=guild), make_member(10, "new", guild=guild)
        )

        self.assertEqual((await UserProfile.objects.aget(user_id=10)).user_name, "new")


class GuildPeriodicCheckTest(TestCase):
    async def test_check_registers_new_guilds_and_members(self):
        guild = make_guild(
            1, "Alpha", members=[make_member(10, "a"), make_member(11, "b", bot=True)]
        )

        await make_cog([guild]).check()

        self.assertTrue(await GuildProfile.objects.filter(guild_id=1).aexists())
        self.assertEqual(await UserProfile.objects.filter(guild_id=1).acount(), 1)

    async def test_check_removes_guilds_the_bot_left(self):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.ensure_guild(2, "Beta")

        await make_cog([make_guild(1, "Alpha")]).check()

        self.assertEqual([g.guild_id async for g in GuildProfile.objects.all()], [1])


class GuildChannelCommandTest(TestCase):
    async def test_set_channel_stores_channel(self):
        await guilds.ensure_guild(1, "Alpha")
        cog = make_cog()
        ctx = make_ctx(guild=make_guild(1, "Alpha"))
        channel = MagicMock(id=555)
        channel.name = "general"

        await cog.set_channel.callback(cog, ctx, channel)

        self.assertEqual(
            (await GuildProfile.objects.aget(guild_id=1)).main_channel_id, 555
        )
        ctx.respond.assert_awaited_once()

    async def test_unset_channel_clears_channel(self):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.set_main_channel(1, 555)
        cog = make_cog()
        ctx = make_ctx(guild=make_guild(1, "Alpha"))

        await cog.unset_channel.callback(cog, ctx)

        self.assertIsNone((await GuildProfile.objects.aget(guild_id=1)).main_channel_id)

    async def test_unset_channel_without_channel_informs(self):
        await guilds.ensure_guild(1, "Alpha")
        cog = make_cog()
        ctx = make_ctx(guild=make_guild(1, "Alpha"))

        await cog.unset_channel.callback(cog, ctx)

        embed = ctx.respond.await_args.kwargs["embed"]
        self.assertIn("already", embed.description)


class GuildSyncCommandTest(TestCase):
    """The owner's way to register the slash commands again by hand."""

    def make_ctx(self):
        ctx = make_ctx(guild=make_guild(1, "Alpha"))
        ctx.bot.sync_commands = AsyncMock()
        ctx.bot.command_scope.sync_guild = AsyncMock(return_value=True)
        return ctx

    async def test_global_registers_everything(self):
        cog, ctx = make_cog(), self.make_ctx()

        await cog.sync.callback(cog, ctx, "global")

        ctx.bot.sync_commands.assert_awaited_once_with()
        ctx.bot.command_scope.sync_guild.assert_not_awaited()

    async def test_guild_registers_this_server_only(self):
        # It must not turn every command into a command of this one server.
        cog, ctx = make_cog(), self.make_ctx()

        await cog.sync.callback(cog, ctx, "guild")

        ctx.bot.command_scope.sync_guild.assert_awaited_once_with(1)
        ctx.bot.sync_commands.assert_not_awaited()
        self.assertIn(
            "synchronized", ctx.respond.await_args.kwargs["embed"].description
        )

    async def test_guild_says_so_when_discord_did_not_take_the_commands(self):
        cog, ctx = make_cog(), self.make_ctx()
        ctx.bot.command_scope.sync_guild.return_value = False

        await cog.sync.callback(cog, ctx, "guild")

        self.assertIn("could not", ctx.respond.await_args.kwargs["embed"].description)

    async def test_discord_is_answered_before_the_registration_starts(self):
        for scope in ("global", "guild"):
            with self.subTest(scope=scope):
                cog, ctx = make_cog(), self.make_ctx()
                order: list[str] = []
                ctx.defer = AsyncMock(side_effect=lambda **_: order.append("defer"))
                ctx.bot.sync_commands.side_effect = lambda: order.append("register")
                ctx.bot.command_scope.sync_guild.side_effect = lambda _id: bool(
                    order.append("register") or True
                )

                await cog.sync.callback(cog, ctx, scope)

                self.assertEqual(order, ["defer", "register"])
