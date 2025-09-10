# Demolizzen
from demolizzen.core.bot import Demolizzen

from .token import Token


def setup(bot: Demolizzen):
    bot.add_cog(Token(bot))
