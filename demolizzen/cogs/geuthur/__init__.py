# Demolizzen
from demolizzen.core.bot import Demolizzen

from .geuthur import Geuthur


def setup(bot: Demolizzen):
    bot.add_cog(Geuthur(bot))
