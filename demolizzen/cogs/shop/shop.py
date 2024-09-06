import discord
from core import checks
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands
from settings import db
from settings.functions import application_cooldown

from .functions import buy_this


class Shop(commands.Cog):
    """
    You have Coins? Here you have a lot of choices, Happy Shopping!
    """

    def __init__(self, bot):
        self.bot = bot
        self._shop = []
        self.title = "Shop"
        self.alias = "shop"
        # Load data into _shop
        self.shop_data = bot.loop.create_task(self.fetch_shop_data())

    shop = SlashCommandGroup(
        "shop", "Shop System", contexts=[discord.InteractionContextType.guild]
    )

    def cog_unload(self):
        self.shop_data.cancel()

    async def fetch_shop_data(self):
        # Assuming you have a database connection object called 'db'
        await self.bot.wait_until_ready()
        try:
            sql = "SELECT * FROM `eve_shop`"
            shop_data = await db.select(sql, dictlist=True)

            # Löschen Sie die vorhandenen Daten in self._shop
            self._shop.clear()

            # Fügen Sie die neuen Daten aus der Datenbank hinzu
            self._shop.extend(shop_data)
        # pylint: disable=broad-except
        except Exception as e:
            print(f"[Fetch Shop Data] • {e}")

    async def get_shop_info(self, ctx: discord.AutocompleteContext):
        """Returns a list of names that begin with the characters entered so far."""
        return [
            item["name"]
            for item in self._shop
            if item["shop"] == "shop" and item["name"].startswith(ctx.value)
        ]

    @shop.command(name="price")
    @checks.is_in_channel()
    @commands.cooldown(
        10, 600, commands.BucketType.user
    )  # 10 Mal alle 10 Minuten pro Benutzer
    @option(
        "item",
        description="Get more information about a specific item",
        autocomplete=get_shop_info,
        required=False,
    )
    async def shopprice(self, ctx, item=None):
        """
        Get price information for specific item
        """
        # await ctx.defer()

        if item is None:
            em = discord.Embed(
                title="Shop",
                color=discord.Color.teal(),
                description="Use `/shop price` `item` to get more information about the item. \n Use `/shop buy` `item` to buy the item. \n\n:money_with_wings: Here are the available items:\n\n ",
            )
        else:
            if item not in [item["name"] for item in self._shop]:
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
            if data["shop"] == "shop":
                name = data["name"]
                price = data["price"]
                desc = data["description"]

                if item and item != name or item == name.lower():
                    continue

                em.add_field(
                    name=f"\n\n {name} - :coin: {price}",
                    value=desc if item else "",
                    inline=False,
                )

        await ctx.respond(embed=em)
        return

    @shopprice.error
    async def command_cooldown(self, ctx, error):
        await application_cooldown(ctx, error)

    @shop.command(name="buy")
    @checks.is_in_channel()
    @commands.cooldown(
        10, 600, commands.BucketType.user
    )  # 10 Mal alle 10 Minuten pro Benutzer
    @option(
        "item",
        description="Get more information about a specific item",
        autocomplete=get_shop_info,
    )
    async def shopbuy(self, ctx, item: str, amount: int):
        """
        Buy a specific item
        """
        # await ctx.defer()

        server_id = ctx.guild.id

        em = discord.Embed(
            title="Shop",
            color=discord.Color.teal(),
            description="",
        )

        res_raid = await buy_this(ctx.author, server_id, item, amount)
        if not res_raid[0]:
            if res_raid[1] == 1:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, The Item `{item}` was not found!",
                )
            if res_raid[1] == 2:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, You already own **`{item}`**!",
                )
            if res_raid[1] == 3:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, You have not enough :coin: for **`{item}`**",
                )
        # Hier erfolgt die Aktualisierung des Kontos des Benutzers nur, wenn der Kauf erfolgreich ist
        if res_raid[0]:
            em = discord.Embed(
                title="",
                color=discord.Color.teal(),
                description=f"{ctx.author.mention}, Buy {amount} x **`{item}`**",
            )
        await ctx.respond(embed=em)
        return

    @shopbuy.error
    async def shopbuy_cooldown(self, ctx, error):
        await application_cooldown(ctx, error)
