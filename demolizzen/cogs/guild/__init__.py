# Demolizzen
from demolizzen.core.bot import Demolizzen

from .guild import Guild


def setup(bot: Demolizzen):
    bot.add_cog(Guild(bot))
