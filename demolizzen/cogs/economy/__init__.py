# Demolizzen
from demolizzen.cogs.economy.economy import Economy
from demolizzen.cogs.economy.mission import TextAdventure
from demolizzen.core.bot import Demolizzen


def setup(bot: Demolizzen):
    bot.add_cog(Economy(bot))
    bot.add_cog(TextAdventure(bot))
