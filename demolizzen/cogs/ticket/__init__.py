# Demolizzen
from demolizzen.cogs.ticket._settings_page import ticket_settings_page
from demolizzen.cogs.ticket.ticket import TicketSystem
from demolizzen.cogs.ticket.ticket_config import TicketSystemConfig
from demolizzen.core import settings_pages
from demolizzen.core.bot import Demolizzen


def setup(bot: Demolizzen):
    settings_pages.register("ticket", ticket_settings_page)
    bot.add_cog(TicketSystem(bot))
    bot.add_cog(TicketSystemConfig(bot))


def teardown(bot: Demolizzen):  # pylint: disable=unused-argument
    settings_pages.unregister("ticket")
