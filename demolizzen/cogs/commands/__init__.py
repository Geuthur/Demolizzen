# Demolizzen
from demolizzen.cogs.commands.commands import Commands
from demolizzen.core.bot import Demolizzen


def setup(bot: Demolizzen):
    bot.add_cog(Commands(bot))
