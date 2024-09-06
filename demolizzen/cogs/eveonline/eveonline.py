import difflib
import logging
from datetime import datetime, timedelta

import aiohttp
import discord
from core import checks
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands
from discord.ui import InputText, Modal
from settings import db
from settings.functions import application_cooldown, format_number

log = logging.getLogger("main")

# Load functions & settings


class Eve(commands.Cog):
    """
    All EVE-Online relevant commands.
    """

    eve = SlashCommandGroup(
        "eve", "EvE Online", contexts=[discord.InteractionContextType.guild]
    )

    # pylint: disable=too-many-instance-attributes
    def __init__(self, bot):
        self.bot = bot
        self._eve_item_db = {}
        self.title = "EVEOnline"
        self.alias = "eve"

        # Call the fetch_shop_data method when the class is initialized
        self.item_db = bot.loop.create_task(self.fetch_item_db())

    def cog_unload(self):
        self.item_db.cancel()

    async def fetch_item_db(self):
        await self.bot.wait_until_ready()
        if not self._eve_item_db:
            sql = "SELECT typeID, typeName FROM invTypes"
            results = await db.select(sql)
            self._eve_item_db = {result[1]: result[0] for result in results}

    async def get_items(self, ctx: discord.AutocompleteContext):
        """Returns a list of items that begin with the entered characters."""
        item_names = self._eve_item_db
        search_term = ctx.value.lower()

        # Filter items that start with the search term
        filtered_items = [
            item_name
            for item_name, _ in item_names.items()
            if search_term in item_name.lower()
        ]

        # Sort the filtered items based on similarity to the search term
        sorted_items = sorted(
            filtered_items,
            key=lambda x: difflib.SequenceMatcher(None, x.lower(), search_term).ratio(),
            reverse=True,
        )

        return sorted_items

    async def db_connection(self, ctx: discord.ApplicationContext):
        log.error("[Economy Work Command] DB Connection Problem")
        em = discord.Embed(
            color=discord.Color.red(),
            description="❌ An error occurred, please try again later.",
        )
        await ctx.respond(embed=em, ephemeral=True, delete_after=10)
        return

    class PriceListModal(Modal):
        # pylint: disable=import-outside-toplevel
        from .functions import PriceHandler

        def __init__(self, bot, tradehub, *args, **kwargs) -> None:
            kwargs.setdefault("title", "Enter a Supported Format")
            super().__init__(*args, **kwargs)
            self.bot = bot
            self.tradehub = tradehub if tradehub else "Jita"

            # Add a text input field
            self.add_item(
                InputText(
                    label="Price List",
                    style=discord.InputTextStyle.long,
                    placeholder="Copy to Clipboard from EFT, Material List, Order or Retriever x1",
                )
            )

        async def callback(self, interaction: discord.Interaction):
            if not self.tradehub:
                region = 60003760
            else:
                tradehub_dict = {
                    "Jita": 60003760,
                    "Amarr": 60008494,
                    "Dodixie": 60011866,
                    "Rens": 60004588,
                    "Hek": 60005686,
                    "Delve": 10000060,
                }
                region = tradehub_dict.get(self.tradehub, "Jita")

            # Handle the modal submission
            content = self.children[0].value  # Get the value from the text input field

            pricehandler = self.PriceHandler(self.bot, content, interaction, region)
            data = await pricehandler.process_input()

            if data:
                währung = "ISK"
                try:
                    if data.total_price > 0:
                        item_summary = "\n".join(
                            [
                                f"{item} (x{format_number(items_count)}) - {'Nicht auf dem Markt' if data.item_price_dict.get(item, 0) == 0 else format_number(data.item_price_dict[item], währung)}"
                                for item, items_count in data.items_dict.items()
                                if item
                                and item
                                in data.item_price_dict  # Stellen Sie sicher, dass das Element sowohl in items_dict als auch in item_price_dict vorhanden ist
                            ]
                        )

                        # Überprüfe die Länge von item_summary
                        if len(item_summary) > 4000:
                            # Teile den Text in Teile mit maximal 4000 Zeichen
                            parts = [
                                item_summary[i : i + 4000]
                                for i in range(0, len(item_summary), 4000)
                            ]

                            # Erstellen und Senden von Embeds für jedes Teil
                            last_item_name = None
                            for index, part in enumerate(parts):
                                # Extrahiere den Gegenstandsnamen aus dem letzten Teil des vorherigen Embeds
                                first_item_name = (
                                    part.split("\n")[0].split("(")[0].strip()
                                )

                                # Überprüfe und ersetze den Namen, wenn er abgeschnitten wurde
                                if (
                                    last_item_name
                                    and last_item_name not in first_item_name
                                ):
                                    part = part.replace(
                                        first_item_name,
                                        last_item_name + " " + first_item_name,
                                        1,
                                    )

                                # Speichere den Gegenstandsnamen aus dem letzten Teil des aktuellen Embeds
                                last_item_name = (
                                    part.split("\n")[-1].split("(")[0].strip()
                                )

                                if index == 0:
                                    # Erstellen des ersten Embeds mit zusätzlichen Informationen
                                    embed = discord.Embed(
                                        title=f"Summary Part {index + 1}",
                                        description=f"Tradehub: `{self.tradehub}`\n\nTotal Sell: `{data.formatted_total_price}`\nTotal Buy: `{data.formatted_total_buyprice}`\n\nItems - Sell:\n{part}",
                                        color=discord.Color.green(),
                                    )
                                else:
                                    # Erstellen der nachfolgenden Embeds mit nur dem Teil als Beschreibung
                                    embed = discord.Embed(
                                        title=f"Part {index + 1}",
                                        description=part,
                                        color=discord.Color.green(),
                                    )

                                # Senden des Embeds (je nachdem, wie du mit Discord interagierst)
                                await interaction.edit_original_response(embed=embed)
                        else:
                            # Erstellen und Senden des einzigen Embeds, wenn der Text nicht geteilt wurde
                            embed = discord.Embed(
                                title="Summary",
                                description=f"Tradehub: `{self.tradehub}`\n\nTotal Sell: `{data.formatted_total_price}`\nTotal Buy: `{data.formatted_total_buyprice}`\n\nItems - Sell:\n{item_summary}",
                                color=discord.Color.green(),
                            )

                            # Senden des Embeds (je nachdem, wie du mit Discord interagierst)
                            await interaction.respond(embed=embed)
                # pylint: disable=broad-except
                except Exception as e:
                    log.error(f"[Price List Command] • {e}", exc_info=True)
                    em = discord.Embed(
                        title="",
                        color=discord.Color.teal(),
                        description="An Error occours, Try again later",
                    )
                    await interaction.respond(embed=em, delete_after=10)

    @eve.command(name="status")
    @checks.is_in_channel()
    @commands.cooldown(
        3, 600, commands.BucketType.user
    )  # 10 Mal alle 10 Minuten pro Benutzer
    async def status(self, ctx: discord.ApplicationContext):
        """
        Get Status of tranquility Server

        """
        await ctx.defer()

        data = await ctx.bot.esi_data.server_info()
        start_time = data.get("start_time") if data else None
        em = discord.Embed(
            title="Server Status", color=discord.Color.teal(), description=""
        )
        if start_time:
            player_count = data.get("players")
            # Embed erstellen
            em.set_thumbnail(
                url="https://image.eveonline.com/Alliance/434243723_64.png"
            )  # Fügen Sie das Thumbnail als Bild hinzu
            em.add_field(
                name="Server Online 🟢",
                value=f"{player_count:,} players connected.",
                inline=True,
            )
        else:
            em.add_field(name="Server Online 🔴", value="Server Offline", inline=True)
        await ctx.respond(embed=em)

    @status.error
    async def command_cooldown(self, ctx, error):
        await application_cooldown(ctx, error)

    @eve.command(name="price")
    @checks.is_in_channel()
    @commands.cooldown(
        10, 600, commands.BucketType.user
    )  # 10 Mal alle 10 Minuten pro Benutzer
    @option(
        "item_name",
        description="Get more information about a specific item",
        autocomplete=get_items,
    )
    @option(
        "tradehub",
        description="Choose Tradehub",
        choices=["Jita", "Amarr", "Dodixie", "Rens", "Hek"],
        required=False,
    )
    async def priceinfo(
        self, ctx: discord.ApplicationContext, item_name: str, tradehub: str
    ):
        """
        Get Tradehub Price Information from specific item

        Arguments
        ----------
        ctx: `context`
            The context containing information about the request.
        item_name: `str`
            The name of the item for which you want information.

        Returns
        -------
            Returns the Price of the given item.

        Raises
        ------
        Exception
            If no records are returned, an error is raised.
        """
        await ctx.defer()

        expire_time_seconds = 600  # 10 Minuten in Sekunden
        expiration = datetime.now() + timedelta(seconds=expire_time_seconds)
        item_id = None

        if not tradehub:
            region = 60003760
        else:
            tradehub_dict = {
                "Jita": 60003760,
                "Amarr": 60008494,
                "Dodixie": 60011866,
                "Rens": 60004588,
                "Hek": 60005686,
                "Delve": 10000060,
            }
            region = tradehub_dict.get(tradehub)

        if item_name in self._eve_item_db:
            item_id = self._eve_item_db[item_name]

        async def fuzzwork(region, item_id):
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://market.fuzzwork.co.uk/aggregates/?station={region}&types={item_id}"
                ) as r:
                    if r.status == 200:
                        response = await r.json()

                        price = int(round(float(response[str(item_id)]["sell"]["min"])))
                        maxprice = int(
                            round(float(response[str(item_id)]["buy"]["max"]))
                        )

                        sql = "REPLACE INTO eve_pricecache (item_name, price, buy, tradehub, expiration) VALUES (:item_name, :price, :buy, :tradehub, :expiration)"
                        params = {
                            "item_name": item_name,
                            "price": price,
                            "buy": maxprice,
                            "tradehub": region,
                            "expiration": expiration,
                        }

                        await db.execute_sql(sql, params)
                        return price, maxprice
                    return 0, 0

        if item_id:
            try:
                sql = "SELECT item_name, price, buy, expiration FROM `eve_pricecache` WHERE `tradehub` = :region AND `item_name` = :item_name"
                params = {"region": region, "item_name": item_name}
                results = await db.select_var(sql, params, single=True, dictlist=True)

                if results is not None:
                    price = results["price"]
                    maxprice = results["buy"]
                    cached_expiration = results["expiration"]
                    if cached_expiration < datetime.now():
                        await fuzzwork(region, item_id)
                else:
                    price, maxprice = await fuzzwork(region, item_id)

                # Preis in ISK umwandeln und formatieren
                formatted_price = f"{price:,.0f} ISK"
                formatted_maxprice = f"{maxprice:,.0f} ISK"

                # Embed erstellen
                em = discord.Embed(
                    title=f"Tradehub: **{tradehub}**",
                    color=discord.Color.teal(),
                    description=f"**{item_name}**",
                )
                em.set_thumbnail(
                    url=f"https://images.evetech.net/types/{item_id}/icon"
                )  # Fügen Sie das Thumbnail als Bild hinzu
                em.add_field(name="Sell", value=f"`{formatted_price}`", inline=True)
                em.add_field(name="Buy", value=f"`{formatted_maxprice}`", inline=True)
                await ctx.respond(embed=em)
            # pylint: disable=broad-except
            except Exception as e:
                log.error(f"[Price Command] • {e}", exc_info=True)
                await ctx.respond(
                    "Der Gegenstand wurde nicht gefunden.", ephemeral=True
                )
                return
        else:
            await ctx.respond("Der Gegenstand wurde nicht gefunden.", delete_after=10)

    @priceinfo.error
    async def priceinfo_cooldown(self, ctx, error):
        await application_cooldown(ctx, error)

    @eve.command(name="price-list")
    @checks.is_in_channel()
    @commands.cooldown(
        5, 600, commands.BucketType.user
    )  # 5 Mal alle 10 Minuten pro Benutzer
    @option(
        "tradehub",
        description="Choose Tradehub",
        choices=["Jita", "Amarr", "Dodixie", "Rens", "Hek"],
        required=False,
    )
    async def pricelist(self, ctx: discord.ApplicationContext, tradehub: str):
        """
        Get Tradehub Price Information from a Batch List

        Arguments
        ----------
        ctx: `context`
            The context containing information about the request.
        input: `message`
            The message waiting for user interaction to provide results.

        Returns
        -------
            A list of items and their corresponding prices based on user input.

        Raises
        ------
        Exception
            If no records are returned, an error is raised.
        """
        # Show the modal to the user
        modal = self.PriceListModal(self.bot, tradehub)
        await ctx.send_modal(modal)

        return

    @pricelist.error
    async def pricelist_cooldown(self, ctx, error):
        await application_cooldown(ctx, error)

    # ---------------------------- Listener ----------------------------
    # ---------------------------- Listener ----------------------------
    # ---------------------------- Listener ----------------------------

    # @commands.Cog.listener()
    # async def on_guild_join(self, guild):
    #    pass

    # on guild leave
    # @commands.Cog.listener()
    # async def on_guild_remove(self, guild):
    #    pass
