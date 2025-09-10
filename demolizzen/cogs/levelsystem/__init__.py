# Demolizzen
from demolizzen.core.bot import Demolizzen

from .levelsystem import Levelsystem


def setup(bot: Demolizzen):
    bot.add_cog(Levelsystem(bot))
