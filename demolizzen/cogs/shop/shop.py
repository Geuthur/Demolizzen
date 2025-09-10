# Third Party
from asgiref.sync import sync_to_async

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks

# Django
from django.db import transaction

# Demolizzen
from demolizzen import models
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen


class Shop(commands.Cog):
    """
    You have Coins? Here you have a lot of choices, Happy Shopping!
    """

    def __init__(self, bot: Demolizzen):
        self.bot = bot
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
        try:
            user = await models.UserProfile.objects.select_related(
                "bank_account", "bags"
            ).aget(user_id=ctx.author.id, guild_id=ctx.guild.id)
            ctx.user_profile = user
            self.bot.logger.debug(f"UserProfile loaded for {ctx.author}.")
        except models.UserProfile.DoesNotExist as exc:
            raise commands.CheckFailure(
                "UserProfile does not exist. Please register first. `/auth register`"
            ) from exc

    @shop.command(name="price")
    @checks.is_in_channel()
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
                description="Use `/shop price` `item` to get more information about the item. \n Use `/shop buy` `item` to buy the item. \n\n:money_with_wings: Here are the available items:\n\n ",
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
    @checks.is_in_channel()
    @option(
        "item",
        description="Get more information about a specific item",
        autocomplete=get_shop_info,
    )
    async def shopbuy(self, ctx: discord.ApplicationContext, item: str, amount: int):
        """
        Buy a specific item
        """
        em = discord.Embed(
            title="Shop",
            color=discord.Color.teal(),
            description="",
        )

        async def buy_item(
            item_name,
            user_profile: models.UserProfile,
        ):
            try:
                shop_item = await models.EconomyShop.objects.aget(
                    name__iexact=item_name
                )
            except models.EconomyShop.DoesNotExist:
                return [False, 1]  # Item not found

            try:
                if user_profile.bank_account.wallet < (shop_item.price * amount):
                    return [False, 2]  # Not enough money
                item = await user_profile.bags.items.aget(item_name=item_name)
                item.quantity += amount
            except models.UserBag.DoesNotExist:
                user_bag = await models.UserBag.objects.select_related("items").acreate(
                    user=user_profile
                )
                item = user_bag.items.get(item_name=item_name)
            except models.UserBagItems.DoesNotExist:
                item = await models.UserBagItems.objects.acreate(
                    user_bag=user_profile.bags,
                    item_name=shop_item.name,
                    item_type=shop_item.shop_type,
                    quantity=amount,
                )

            def save_transaction():
                with transaction.atomic():
                    user_profile.bank_account.wallet -= shop_item.price * amount
                    user_profile.bank_account.save()
                    item.save()
                    return True
                return False

            bought = await sync_to_async(save_transaction)()
            if bought:
                return [True, 0]
            return [False, 2]  # Transaction failed

        response = await buy_item(item_name=item, user_profile=ctx.user_profile)

        if not response[0]:
            if response[1] == 1:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, The Item `{item}` was not found!",
                )
            if response[1] == 2:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, You have not enough :coin: for **`{item}`**",
                )

        if response[0]:
            em = discord.Embed(
                title="",
                color=discord.Color.teal(),
                description=f"{ctx.author.mention}, Buy {amount} x **`{item}`**",
            )
        return await ctx.respond(embed=em)
