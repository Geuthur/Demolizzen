# Demolizzen
from demolizzen.cogs.panel.panel import Panel
from demolizzen.core.bot import Demolizzen


def setup(bot: Demolizzen):
    bot.add_cog(Panel(bot))
