# Standard Library
import asyncio
import logging

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands

# Demolizzen
from demolizzen import USER_AGENT_TEXT
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog
from demolizzen.services import prices
from demolizzen.services.errors import PriceError
from demolizzen.utils.autocomplete import search_items

from ._appraisal import AppraisalClient

logger = logging.getLogger(__name__)


class EveOnline(BaseCog):
    """
    All EVE-Online relevant commands.
    """

    eve = SlashCommandGroup(
        "eve", "EvE Online", contexts=[discord.InteractionContextType.guild]
    )

    key = "eveonline"

    # Seconds to wait for the server status before it counts as offline.
    STATUS_TIMEOUT = 10

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
        self.title = "EVEOnline"
        self.alias = "eve"
        self.appraisal = AppraisalClient(
            lambda: getattr(self.bot, "session", None),
            headers={"User-Agent": USER_AGENT_TEXT},
        )

    async def _server_info(self):
        """The status of Tranquility, or None when it cannot be read in time."""
        try:
            return await asyncio.wait_for(
                self.bot.esi_data.server_info(), timeout=self.STATUS_TIMEOUT
            )
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.warning("Server status could not be read: %r", error)
            return None

    @eve.command(name="status")
    @commands.cooldown(3, 600, commands.BucketType.user)  # 3 per 10 minutes
    async def status(self, ctx: discord.ApplicationContext):
        """
        Get Status of tranquility Server

        """
        await ctx.defer()

        data = await self._server_info()
        em = discord.Embed(
            title="Server Status", color=discord.Color.teal(), description=""
        )
        if data is not None and getattr(data, "start_time", None):
            em.set_thumbnail(
                url="https://image.eveonline.com/Alliance/434243723_64.png"
            )
            em.add_field(
                name="Server Online 🟢",
                value=f"{data.players:,} players connected.",
                inline=True,
            )
        else:
            em.add_field(
                name="Server Offline 🔴",
                value="Tranquility is not responding.",
                inline=True,
            )
        await ctx.respond(embed=em)

    @eve.command(name="price")
    @commands.cooldown(10, 600, commands.BucketType.user)  # 10 per 10 minutes
    @option(
        "item_name",
        description="Get more information about a specific item",
        autocomplete=search_items,
    )
    @option(
        "tradehub",
        description="Choose Tradehub",
        choices=[hub.title for hub in prices.TRADEHUBS.values()],
        required=False,
    )
    async def priceinfo(
        self, ctx: discord.ApplicationContext, item_name: str, tradehub: str = None
    ):
        """Get Tradehub Price Information from specific item"""
        await ctx.defer()

        hub = prices.tradehub(tradehub)
        try:
            price = await prices.get_price(item_name, hub, self.appraisal.quotes)
        except PriceError as error:
            await ctx.respond(
                error.message, allowed_mentions=discord.AllowedMentions.none()
            )
            return

        em = discord.Embed(
            title=f"Tradehub: **{hub.station}**",
            color=discord.Color.teal(),
            description=f"**{price.item_name}**",
        )
        em.add_field(name="Sell", value=f"`{price.sell:,.0f} ISK`", inline=True)
        em.add_field(name="Buy", value=f"`{price.buy:,.0f} ISK`", inline=True)
        await ctx.respond(embed=em)
