# Demolizzen
from demolizzen.core.bot import Demolizzen

from .games import Games


def setup(bot: Demolizzen):
    bot.add_cog(Games(bot))
