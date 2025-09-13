# Demolizzen
from demolizzen.cogs.ticket.ticket import TicketSystem
from demolizzen.core.bot import Demolizzen


def setup(bot: Demolizzen):
    bot.add_cog(TicketSystem(bot))
