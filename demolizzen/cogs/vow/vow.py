# Standard Library
import logging

# Discord
import discord
from discord.ext import commands
from discord.ui import Button, View

logger = logging.getLogger(__name__)


class Vow(commands.Cog):
    """
    Get all relevant commands for the Corporation "Voices of War"
    """

    def __init__(self, bot):
        self.bot = bot
        self.title = "Voice of War"
        self.alias = "vow"
        self.access = 476405195585355776
        self.bot.add_view(
            self.PersistentTicketView(bot)
        )  # Add the persistent view to the bot

    # --------- Persistent Ticket Button ---------
    class PersistentTicketView(View):
        def __init__(self, bot):
            super().__init__(timeout=None)
            self.bot = bot
            self.add_item(self.TicketButton())

        class TicketButton(Button):
            def __init__(self):
                super().__init__(
                    label="Ticket eröffnen",
                    style=discord.ButtonStyle.green,
                    custom_id="persistent_ticket_button",
                )

            async def callback(self, interaction: discord.Interaction):
                # TicketSystem-Instanz holen
                ticket_cog = interaction.client.get_cog("TicketSystem")
                if not ticket_cog:
                    await interaction.response.send_message(
                        "Ticketsystem nicht geladen.", ephemeral=True
                    )
                    return
                # open_ticket aufrufen (async, wie im Original)
                ctx = await interaction.client.get_application_context(interaction)
                # GuildSettings laden wie im TicketSystem
                await ticket_cog.cog_before_invoke(ctx)
                await ticket_cog.open_ticket(ctx)

    @commands.slash_command(guild_ids=[476405195585355776, 518052275076464640])
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

    @commands.slash_command(guild_ids=[476405195585355776, 518052275076464640])
    @commands.is_owner()
    async def create_ticket_button(self, ctx: discord.ApplicationContext):
        """Create a persistent ticket button."""
        view = self.PersistentTicketView(self.bot)
        embed = discord.Embed(
            title="Support-Ticket eröffnen",
            description="Klicke auf den Button, um ein privates Ticket mit dem Team zu eröffnen.",
            color=discord.Color.green(),
        )
        await ctx.respond(embed=embed, view=view)

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
