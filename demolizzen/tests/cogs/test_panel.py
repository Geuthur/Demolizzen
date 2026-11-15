# Standard Library
from unittest.mock import MagicMock

# Django
from django.test import SimpleTestCase, TestCase

# Demolizzen
from demolizzen.cogs.panel._view import PanelView, build_embed
from demolizzen.cogs.panel.panel import Panel
from demolizzen.models import GuildProfile
from demolizzen.services import cog_settings, guilds
from demolizzen.tests.helpers import make_ctx, make_guild, make_interaction, make_member

FIXED = {"core", "owner", "guild", "panel"}
BANK_GROUP = ["banksystem", "economy", "shop", "games"]


class BuildEmbedTest(SimpleTestCase):
    def test_embed_lists_every_given_cog_with_its_state(self):
        embed = build_embed("Alpha", {"games": False, "ticket": True})

        self.assertEqual(embed.title, "⚙️ Demolizzen Panel – Alpha")
        self.assertEqual(
            [field.name for field in embed.fields], ["🔴 Games", "🟢 Ticket System"]
        )

    def test_selected_cog_is_described(self):
        embed = build_embed("Alpha", {"games": False}, selected="games")

        self.assertIn("Games", embed.description)
        self.assertIn("Disabled", embed.description)

    def test_notice_replaces_description(self):
        embed = build_embed("Alpha", {"games": True}, selected="games", notice="Sure?")

        self.assertEqual(embed.description, "Sure?")


class PanelTestCase(TestCase):
    def setUp(self):
        cog_settings.invalidate()
        self.admin = make_member(10, "admin", manage_guild=True)
        self.guild = make_guild(
            1, "Alpha", members=[make_member(1, "owner"), self.admin]
        )

    async def make_view(self) -> PanelView:
        await guilds.ensure_guild(1, "Alpha")
        return PanelView(1, "Alpha", 10, await cog_settings.get_states(1))

    def interaction(self, user=None):
        return make_interaction(guild=self.guild, user=user or self.admin)


class PanelCommandTest(PanelTestCase):
    async def test_command_registers_guild_and_responds_ephemeral(self):
        cog = Panel(MagicMock())
        ctx = make_ctx(guild=self.guild, author=self.admin)

        await cog.panel.callback(cog, ctx)

        self.assertTrue(await GuildProfile.objects.filter(guild_id=1).aexists())
        kwargs = ctx.respond.await_args.kwargs
        self.assertTrue(kwargs["ephemeral"])
        self.assertIsInstance(kwargs["view"], PanelView)
        self.assertEqual(kwargs["embed"].title, "⚙️ Demolizzen Panel – Alpha")

    def test_command_is_limited_to_guild_managers(self):
        self.assertTrue(Panel.panel.default_member_permissions.manage_guild)
        self.assertEqual(Panel.key, "panel")


class PanelViewTest(PanelTestCase):
    async def test_select_has_no_fixed_cogs(self):
        view = await self.make_view()

        values = {option.value for option in view.select.options}

        self.assertFalse(values & FIXED)
        self.assertEqual(values, set(await cog_settings.get_states(1)))

    async def test_buttons_are_disabled_until_a_module_is_chosen(self):
        view = await self.make_view()

        self.assertTrue(view.enable_button.disabled)
        self.assertTrue(view.disable_button.disabled)

    async def test_choosing_an_enabled_module_offers_only_disable(self):
        view = await self.make_view()
        interaction = self.interaction()

        await view.choose(interaction, "ticket")

        self.assertTrue(view.enable_button.disabled)
        self.assertFalse(view.disable_button.disabled)
        interaction.response.edit_message.assert_awaited_once()

    async def test_disable_button_persists_and_redraws(self):
        view = await self.make_view()
        await view.choose(self.interaction(), "ticket")
        interaction = self.interaction()

        await view.toggle(interaction, False)

        self.assertFalse(await cog_settings.is_enabled(1, "ticket"))
        embed = interaction.response.edit_message.await_args.kwargs["embed"]
        self.assertIn("🔴 Ticket System", [field.name for field in embed.fields])
        self.assertFalse(view.enable_button.disabled)
        self.assertTrue(view.disable_button.disabled)

    async def test_enable_button_persists(self):
        view = await self.make_view()
        await cog_settings.set_enabled(1, "ticket", False)
        await view.choose(self.interaction(), "ticket")

        await view.toggle(self.interaction(), True)

        self.assertTrue(await cog_settings.is_enabled(1, "ticket"))

    async def test_toggle_without_selection_changes_nothing(self):
        view = await self.make_view()

        await view.toggle(self.interaction(), False)

        self.assertTrue(all((await cog_settings.get_states(1)).values()))


class PanelDependencyTest(PanelTestCase):
    async def test_disable_bank_asks_before_cascading(self):
        view = await self.make_view()
        await view.choose(self.interaction(), "banksystem")
        interaction = self.interaction()

        await view.toggle(interaction, False)

        self.assertTrue(await cog_settings.is_enabled(1, "banksystem"))
        embed = interaction.response.edit_message.await_args.kwargs["embed"]
        self.assertIn(
            "Disabling Banksystem will also disable: Economy, Shop, Games.",
            embed.description,
        )
        labels = [item.label for item in view.children]
        self.assertEqual(labels, ["Confirm", "Cancel"])

    async def test_confirm_cascades(self):
        view = await self.make_view()
        await view.choose(self.interaction(), "banksystem")
        await view.toggle(self.interaction(), False)

        await view.confirm(self.interaction())

        for key in BANK_GROUP:
            self.assertFalse(await cog_settings.is_enabled(1, key), key)
        self.assertIn(view.select, view.children)

    async def test_cancel_changes_nothing(self):
        view = await self.make_view()
        await view.choose(self.interaction(), "banksystem")
        await view.toggle(self.interaction(), False)

        await view.cancel(self.interaction())

        for key in BANK_GROUP:
            self.assertTrue(await cog_settings.is_enabled(1, key), key)
        self.assertIn(view.select, view.children)

    async def test_enabling_dependent_asks_to_enable_bank(self):
        view = await self.make_view()
        await cog_settings.set_enabled(1, "banksystem", False, cascade=True)
        await view.choose(self.interaction(), "games")
        interaction = self.interaction()

        await view.toggle(interaction, True)

        embed = interaction.response.edit_message.await_args.kwargs["embed"]
        self.assertIn("Enabling Games will also enable: Banksystem.", embed.description)
        await view.confirm(self.interaction())
        self.assertTrue(await cog_settings.is_enabled(1, "games"))
        self.assertTrue(await cog_settings.is_enabled(1, "banksystem"))


class PanelPermissionTest(PanelTestCase):
    async def test_author_with_permission_is_accepted(self):
        view = await self.make_view()

        self.assertTrue(await view.interaction_check(self.interaction()))

    async def test_guild_owner_is_accepted_without_manage_guild(self):
        await guilds.ensure_guild(1, "Alpha")
        view = PanelView(1, "Alpha", 1, await cog_settings.get_states(1))

        self.assertTrue(
            await view.interaction_check(self.interaction(self.guild.owner))
        )

    async def test_foreign_user_is_rejected(self):
        view = await self.make_view()
        interaction = self.interaction(make_member(99, manage_guild=True))

        self.assertFalse(await view.interaction_check(interaction))
        interaction.response.send_message.assert_awaited_once_with(
            "You are not allowed to use this panel.", ephemeral=True
        )

    async def test_author_without_permission_is_rejected(self):
        view = await self.make_view()
        interaction = self.interaction(make_member(10, manage_guild=False))

        self.assertFalse(await view.interaction_check(interaction))
        self.assertTrue(await cog_settings.is_enabled(1, "games"))
