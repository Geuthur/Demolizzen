# Standard Library
from unittest.mock import AsyncMock, MagicMock

# Django
from django.test import SimpleTestCase

# Demolizzen
from demolizzen.cogs.vow.vow import TICKET_BUTTON_ID, Vow


class VowSetupTest(SimpleTestCase):
    def test_loads_before_the_event_loop_runs(self):
        # py-cord views need a running loop; extensions load before there is one.
        bot = MagicMock()

        Vow(bot)

        bot.add_view.assert_not_called()

    async def test_ready_registers_the_ticket_button_once(self):
        bot = MagicMock()
        cog = Vow(bot)
        bot.add_view.reset_mock()
        cog._view_registered = False

        await cog.on_ready()
        await cog.on_ready()

        (view,) = (call.args[0] for call in bot.add_view.call_args_list)
        self.assertTrue(view.is_persistent())
        self.assertEqual([item.custom_id for item in view.children], [TICKET_BUTTON_ID])

    async def test_loaded_while_running_registers_the_button_immediately(self):
        bot = MagicMock()

        Vow(bot)

        bot.add_view.assert_called_once()


class VowTicketButtonTest(SimpleTestCase):
    async def click(self, ticket_cog):
        interaction = MagicMock()
        interaction.client.get_cog = MagicMock(return_value=ticket_cog)
        interaction.response.send_message = AsyncMock()
        view = Vow.PersistentTicketView(MagicMock())
        await view.children[0].callback(interaction)
        return interaction

    async def test_button_opens_a_ticket_through_the_ticket_module(self):
        ticket_cog = MagicMock()
        ticket_cog.actions.start_open = AsyncMock()

        interaction = await self.click(ticket_cog)

        interaction.client.get_cog.assert_called_once_with("TicketSystem")
        ticket_cog.actions.start_open.assert_awaited_once_with(interaction)
        interaction.response.send_message.assert_not_awaited()

    async def test_button_says_so_when_tickets_are_not_loaded(self):
        interaction = await self.click(None)

        interaction.response.send_message.assert_awaited_once()
        self.assertTrue(
            interaction.response.send_message.await_args.kwargs["ephemeral"]
        )
