# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import tasks

# Demolizzen
from demolizzen import models
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog
from demolizzen.services import bank, guilds
from demolizzen.services import shop as shop_service
from demolizzen.services.errors import (
    BankError,
    InsufficientFunds,
    ItemNotFound,
    ShopError,
)
from demolizzen.utils.functions import get_command_mention


class Shop(BaseCog):
    """
    You have Coins? Here you have a lot of choices, Happy Shopping!
    """

    key = "shop"

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
        self._shop = []
        self.title = "Shop"
        self.alias = "shop"
        self._shop: list[models.EconomyShop] = []
        self.shop_data.start()

    shop = SlashCommandGroup(
        "shop", "Shop System", contexts=[discord.InteractionContextType.guild]
    )

    # Update Shop every 2 Hours
    @tasks.loop(minutes=120)
    async def shop_data(self):
        """Fetch and update shop data from the database every 2 hours."""
        await self.fetch_shop_data()

    @shop_data.before_loop
    async def before_shop_data(self):
        await self.bot.wait_until_ready()
        self.bot.logger.info("Shop Data Updater Ready")

    def cog_unload(self):
        self.shop_data.cancel()

    async def fetch_shop_data(self):
        """Fetch shop data from the database."""
        self.bot.logger.debug("Fetch new Update shop data...")
        item_data = [
            item async for item in models.EconomyShop.objects.filter(active=True)
        ]
        self._shop.clear()
        self._shop.extend(item_data)

    async def get_shop_info(self, ctx: discord.AutocompleteContext) -> list[str]:
        """Returns a list of names that begin with the characters entered so far."""
        search_terms = ctx.value.lower()
        return [item.name for item in self._shop if search_terms in item.name.lower()]

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        # Members need no registration: profile and bank account are created on demand.
        await guilds.ensure_guild(ctx.guild.id, ctx.guild.name)
        await bank.ensure_account(ctx.guild.id, ctx.author.id, ctx.author.display_name)

    @shop.command(name="price")
    @option(
        "item",
        description="Get more information about a specific item",
        autocomplete=get_shop_info,
        required=False,
    )
    async def shopprice(self, ctx: discord.ApplicationContext, item=None):
        """
        Get price information for specific item, with pagination if needed.
        """
        # await ctx.defer()
        if item is not None:
            if item not in [item.name for item in self._shop]:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, {item} doesn't exist! Be sure you use the correct capitalize.",
                )
                await ctx.respond(embed=em)
                return
            em = discord.Embed(
                title="Shop - Item Description",
                color=discord.Color.teal(),
                description="",
            )
            for data in self._shop:
                name = data.name
                price = data.price
                desc = data.description
                if item and item != name or item == name.lower():
                    continue
                em.add_field(
                    name=f"\n\n {name} - :coin: {price}",
                    value=desc if item else "",
                    inline=False,
                )
            await ctx.respond(embed=em)
            return

        # Pagination for all items
        items_per_page = 10
        fields = []
        for data in self._shop:
            name = data.name
            price = data.price
            desc = data.description
            fields.append((name, price, desc))

        total_pages = (len(fields) + items_per_page - 1) // items_per_page

        def get_embed(page: int):
            em = discord.Embed(
                title=f"Shop (Seite {page + 1}/{total_pages})",
                color=discord.Color.teal(),
                description=f"Use {get_command_mention(bot=self.bot, guild_id=ctx.guild.id, cog='Shop', slash_command='shop', slash_command_group='price')} `item` to get more information about the item. \n Use {get_command_mention(bot=self.bot, guild_id=ctx.guild.id, cog='Shop', slash_command='shop', slash_command_group='buy')} `item` to buy the item. \n\n:money_with_wings: Here are the available items:\n\n ",
            )
            for name, price, __ in fields[
                page * items_per_page : (page + 1) * items_per_page
            ]:
                em.add_field(
                    name=f"\n\n {name} - :coin: {price}",
                    value="",
                    inline=False,
                )
            return em

        class ShopPaginator(discord.ui.View):
            def __init__(self, author_id, timeout=60):
                super().__init__(timeout=timeout)
                self.page = 0
                self.author_id = author_id

            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                return interaction.user.id == self.author_id

            @discord.ui.button(label="⏮️", style=discord.ButtonStyle.secondary)
            async def first(self, __, interaction: discord.Interaction):
                self.page = 0
                await interaction.response.edit_message(
                    embed=get_embed(self.page), view=self
                )

            @discord.ui.button(label="◀️", style=discord.ButtonStyle.primary)
            async def prev(self, __, interaction: discord.Interaction):
                if self.page > 0:
                    self.page -= 1
                    await interaction.response.edit_message(
                        embed=get_embed(self.page), view=self
                    )
                else:
                    await interaction.response.defer()

            @discord.ui.button(label="▶️", style=discord.ButtonStyle.primary)
            async def next(self, __, interaction: discord.Interaction):
                if self.page < total_pages - 1:
                    self.page += 1
                    await interaction.response.edit_message(
                        embed=get_embed(self.page), view=self
                    )
                else:
                    await interaction.response.defer()

            @discord.ui.button(label="⏭️", style=discord.ButtonStyle.secondary)
            async def last(self, __, interaction: discord.Interaction):
                self.page = total_pages - 1
                await interaction.response.edit_message(
                    embed=get_embed(self.page), view=self
                )

            @discord.ui.button(label="❌", style=discord.ButtonStyle.danger)
            async def close(self, __, interaction: discord.Interaction):
                await interaction.message.delete()

        view = ShopPaginator(ctx.author.id)
        await ctx.respond(embed=get_embed(0), view=view)
        return

    @shop.command(name="buy")
    @option(
        "item",
        description="Get more information about a specific item",
        autocomplete=get_shop_info,
    )
    async def shopbuy(self, ctx: discord.ApplicationContext, item: str, amount: int):
        """
        Buy a specific item
        """
        await guilds.ensure_guild(ctx.guild.id, ctx.guild.name)
        try:
            purchase = await shop_service.buy(
                ctx.guild.id, ctx.author.id, ctx.author.display_name, item, amount
            )
        except ItemNotFound:
            color = discord.Color.red()
            text = f"The Item `{item}` was not found!"
        except InsufficientFunds:
            color = discord.Color.red()
            text = f"You have not enough :coin: for **`{item}`**"
        except (ShopError, BankError) as error:
            color = discord.Color.red()
            text = error.message
        else:
            color = discord.Color.teal()
            text = f"Buy {purchase.quantity} x **`{purchase.item_name}`**"

        em = discord.Embed(
            title="", color=color, description=f"{ctx.author.mention}, {text}"
        )
        return await ctx.respond(embed=em)
