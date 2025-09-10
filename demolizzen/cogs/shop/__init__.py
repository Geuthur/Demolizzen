# Demolizzen
from demolizzen.core.bot import Demolizzen

from .shop import Shop


def setup(bot: Demolizzen):
    bot.add_cog(Shop(bot))
