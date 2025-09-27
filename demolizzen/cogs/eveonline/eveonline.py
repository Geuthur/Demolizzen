# Standard Library
import logging

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands
from discord.ui import InputText, Modal

# Django
from django.utils import timezone

# Demolizzen
from demolizzen import models
from demolizzen.core.bot import Demolizzen
from demolizzen.utils.autocomplete import search_items
from demolizzen.utils.functions import application_cooldown, format_number
from demolizzen.utils.pricehandler import PriceHandler

log = logging.getLogger("main")


class EveOnline(commands.Cog):
    """
    All EVE-Online relevant commands.
    """

    eve = SlashCommandGroup(
        "eve", "EvE Online", contexts=[discord.InteractionContextType.guild]
    )

    # pylint: disable=too-many-instance-attributes
    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.title = "EVEOnline"
        self.alias = "eve"

    class PriceListModal(Modal):
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
    @commands.cooldown(
        10, 600, commands.BucketType.user
    )  # 10 Mal alle 10 Minuten pro Benutzer
    @option(
        "item_name",
        description="Get more information about a specific item",
        autocomplete=search_items,
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
        await ctx.trigger_typing()

        price_checker = PriceHandler(self.bot, ctx)

        # Map lowercase tradehub input to the correct TradehubChoices value
        tradehub_map = {
            "jita": models.EvePricecache.TradehubChoices.JITA,
            "amarr": models.EvePricecache.TradehubChoices.AMARR,
            "dodixie": models.EvePricecache.TradehubChoices.DODIXIE,
            "rens": models.EvePricecache.TradehubChoices.RENS,
            "hek": models.EvePricecache.TradehubChoices.HEK,
            "alliance": models.EvePricecache.TradehubChoices.ALLIANCE,
        }
        tradehub_key = tradehub.lower() if tradehub else "jita"
        tradehub_choice = tradehub_map.get(
            tradehub_key, models.EvePricecache.TradehubChoices.JITA
        )

        # Embed erstellen
        em = discord.Embed(
            title=f"Tradehub: **{tradehub_choice}**",
            color=discord.Color.teal(),
            description=f"**{item_name}**",
        )
        max_price = 0
        buy_price = 0

        # Prüfen, ob der Eintrag in der Datenbank vorhanden ist
        try:
            existing_entry = await models.EvePricecache.objects.aget(
                item_name=item_name, tradehub=tradehub_choice
            )
            cached_expiration = existing_entry.expiration
            if cached_expiration >= timezone.datetime.now():
                self.bot.logger.debug(f"Cache hit for {item_name} in {tradehub_choice}")
                # Cache is valid
                max_price = existing_entry.price
                buy_price = existing_entry.buy
            else:
                # Cache expired, fetch new price
                item_list = await price_checker.appraisel([item_name], tradehub_choice)
                if item_list:
                    item_data = item_list[0]
                    max_price = item_data.get("price", 0)
                    buy_price = item_data.get("buy", 0)
        except models.EvePricecache.DoesNotExist:
            # No cache entry, fetch new price
            item_list = await price_checker.appraisel([item_name], tradehub_key)
            if item_list:
                item_data = item_list[0]
                max_price = item_data.get("price", 0)
                buy_price = item_data.get("buy", 0)

        # Preis in ISK umwandeln und formatieren
        formatted_price = f"{max_price:,.0f} ISK"
        formatted_buy = f"{buy_price:,.0f} ISK"

        em.add_field(name="Sell", value=f"`{formatted_price}`", inline=True)
        em.add_field(name="Buy", value=f"`{formatted_buy}`", inline=True)
        await ctx.respond(embed=em)
