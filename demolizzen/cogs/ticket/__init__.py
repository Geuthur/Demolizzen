# Demolizzen
from demolizzen.cogs.ticket.ticket import TicketSystem
from demolizzen.cogs.ticket.ticket_config import TicketSystemConfig
from demolizzen.core.bot import Demolizzen


def setup(bot: Demolizzen):
    bot.add_cog(TicketSystem(bot))
    bot.add_cog(TicketSystemConfig(bot))
