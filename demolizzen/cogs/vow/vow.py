# Standard Library
import logging

# Discord
import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands
from discord.ext.pages import Paginator
from discord.ui import Button, View

log = logging.getLogger("main")


class Vow(commands.Cog):
    """
    Get all relevant commands for the Corporation "Voices of War"
    """

    def __init__(self, bot):
        self.bot = bot
        self.title = "Voice of War"
        self.alias = "vow"
        self.access = 476405195585355776

    vow = SlashCommandGroup(
        name="vow", description="VoiceofWar", guild_ids=[476405195585355776]
    )

    async def get_assets_data(self, assets, ctx: discord.ApplicationContext):
        """
        Voices of War Asset System
        """
        pages = []
        try:
            counter = 0
            embed = discord.Embed(
                title="Voices of War Assets",
                description="",
                color=discord.Color.blurple(),
            )
            for entry in assets:
                total_price = entry["price"] * entry["quantity"]
                total_price = f"{total_price:,.0f} ISK".replace(",", ".")
                quantity = f"{entry['quantity']:,}".replace(",", ".")
                embed.add_field(
                    name=f"{entry['eve_type_name']}\nQuantity: {quantity}",
                    value=f"{total_price}",
                )
                counter += 1

                if counter == 10:
                    embed.description += "\n[Click here for more details](https://auth.voices-of-war.de/assets/)"
                    pages.append(embed)
                    embed = discord.Embed(
                        title="Voices of War Assets",
                        description="",
                        color=discord.Color.blurple(),
                    )
                    counter = 0

            # Add the last page if there are remaining entries
            if counter > 0:
                embed.description += "\n[Click here for more details](https://auth.voices-of-war.de/assets/)"
                pages.append(embed)

            paginator = Paginator(pages=pages, timeout=30)
            message = await paginator.respond(ctx.interaction)
            return message
        # pylint: disable=broad-except
        except Exception as e:
            # Handle the connection error here
            log.error(f"Error on Get Assets Data: {e}")
            return None

    @commands.slash_command(guild_ids=[476405195585355776])
    @commands.guild_only()
    @commands.cooldown(
        5, 600, commands.BucketType.user
    )  # 3 Mal alle 10 Minuten pro Benutzer
    async def transport(self, ctx: discord.ApplicationContext):
        """
        Get Information about Sector Transport
        """
        await ctx.defer()

        button1 = Button(
            label="Contracts",
            url="https://auth.voices-of-war.de/voicesofwar/freight/current_contracts",
            style=discord.ButtonStyle.green,
            emoji="📜",
        )
        button2 = Button(
            label="Routecalc",
            url="https://auth.voices-of-war.de/voicesofwar/freight/calc",
            style=discord.ButtonStyle.green,
            emoji="🚚",
        )
        button3 = Button(
            label="Courier Rates",
            url="https://auth.voices-of-war.de/voicesofwar/freight/rates",
            style=discord.ButtonStyle.green,
            emoji="💰",
        )
        button4 = Button(
            label="FAQ",
            url="https://auth.voices-of-war.de/voicesofwar/freight/index",
            style=discord.ButtonStyle.green,
            emoji="📕",
        )

        view = View()
        view.add_item(button1)
        view.add_item(button2)
        view.add_item(button3)
        view.add_item(button4)
        await ctx.respond("Was genau möchtest du wissen?", view=view)

    # ---------------------------- Listener ----------------------------
    # ---------------------------- Listener ----------------------------
    # ---------------------------- Listener ----------------------------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id in [self.access]:
            channel = member.guild.get_channel(714908793351176319)
            if channel is not None:
                welcome_text = (
                    f"**__Willkommen, {member.mention}!__**\n\n"
                    "Schön, dass du zu uns gefunden hast.\n"
                    "Um Berechtigung unseres Discord Servers zu erhalten, bitten wir dich um Folgendes:\n\n"
                    "- Stelle dich kurz vor, damit wir wissen, wer du bist.\n"
                    "- Logge dich mit deinem Hauptcharakter in unser [Auth-System](https://auth.voices-of-war.de/) ein.\n"
                    "- Aktiviere anschließend den Discord-Service im Menüpunkt [Services](https://auth.voices-of-war.de/services/) um Berechtigungen zu erhalten.\n"
                    "**Zusätzlich für Bewerber:**"
                    "- Linke deinen Main Character im Dashboard über den CharLink damit der Bewerbungsprozess beschleunigt wird.\n\n"
                    "Vielen Dank und viel Spaß auf unserem Server!\n\n"
                    "*Hinweis: Nicht verifizierte Nutzer können nach einiger Zeit entfernt werden.*"
                )
                await channel.send(welcome_text)
