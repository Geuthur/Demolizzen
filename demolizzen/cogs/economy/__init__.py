# Demolizzen
from demolizzen.cogs.economy._settings_page import economy_settings_page
from demolizzen.cogs.economy.economy import Economy
from demolizzen.cogs.economy.mission import TextAdventure
from demolizzen.core import settings_pages
from demolizzen.core.bot import Demolizzen


def setup(bot: Demolizzen):
    settings_pages.register("economy", economy_settings_page)
    bot.add_cog(Economy(bot))
    bot.add_cog(TextAdventure(bot))


def teardown(bot: Demolizzen):  # pylint: disable=unused-argument
    settings_pages.unregister("economy")
