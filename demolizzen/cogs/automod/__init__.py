# Demolizzen
from demolizzen.core.bot import Demolizzen

from .automod import Automod


def setup(bot: Demolizzen):
    bot.add_cog(Automod(bot))
