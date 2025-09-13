# Demolizzen
from demolizzen.cogs.core.core import Core
from demolizzen.core.bot import Demolizzen


def setup(bot: Demolizzen):
    bot.add_cog(Core(bot))
