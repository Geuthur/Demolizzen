# Standard Library
import logging
import math
import random

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands

# Demolizzen
from demolizzen import models
from demolizzen.cogs.economy import missionfunc
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog
from demolizzen.services import bank, guilds, missions
from demolizzen.services.errors import (
    BankError,
    NoActiveMission,
    NoShip,
    OnCooldown,
    ShipAlreadyOwned,
    ShipNotFound,
)
from demolizzen.services.missions import Kind
from demolizzen.utils.functions import get_command_mention

logger = logging.getLogger(__name__)


# pylint: disable=too-many-public-methods
class TextAdventure(BaseCog):
    """All about text adventures"""

    key = "economy"

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
        self.alias = "text_adventure"
        self.title = "Text Adventure Games"

    mission = SlashCommandGroup(
        "mission",
        "Text Adventure Games",
        contexts=[discord.InteractionContextType.guild],
    )

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        # Members need no registration: profile and bank account are created on demand.
        await guilds.ensure_guild(ctx.guild.id, ctx.guild.name)
        await bank.ensure_account(ctx.guild.id, ctx.author.id, ctx.author.display_name)

    async def get_shop(self, ctx: discord.AutocompleteContext) -> list[str]:
        """Returns a list of names that begin with the entered characters."""
        category = ctx.options["category"].lower()
        search_term = ctx.value.lower()
        ship_data = [item async for item in models.EconomyShip.objects.all()]
        # Filter items that start with the search term
        filtered_items = [
            item.name
            for item in ship_data
            if item.category == category and search_term in item.name.lower()
        ]
        return filtered_items

    @commands.slash_command(contexts=[discord.InteractionContextType.guild])
    async def work(self, ctx: discord.ApplicationContext):
        """
        Go to work and let the coins flow.
        """
        username = ctx.author.name.capitalize()
        gif_url = "https://hell-rider.de/static/images/discord/work-working.gif"
        event = await missions.get_event(ctx.guild.id)

        # Roll the shift: payout, bonus for the adventure and the story
        payout = random.randrange(25, 75)
        chance = random.randint(1, 100)
        escalation_payout = random.randrange(10, 25)
        work_text, escalation_text, work_end_text = (
            models.UserWorkMission().get_work_text_combined()
        )
        if escalation_text is not None:
            payout += escalation_payout
        event_extra = 0
        if event.active:
            boosted = math.ceil(payout * event.factor)
            event_extra = boosted - payout
            payout = boosted

        try:
            shift = await missions.work(
                ctx.guild.id, ctx.author.id, ctx.author.display_name, payout, chance
            )
        except OnCooldown as cooldown:
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, You have already started working, come back in `{missions.format_remaining(cooldown.remaining)}`",
            )
            await ctx.respond(embed=em)
            return

        if shift.first:
            em = discord.Embed(
                title="",
                color=discord.Color.teal(),
                description=f"{ctx.author.mention}, You are starting to work, come back in `{shift.duration}`.",
            )
            return await ctx.respond(embed=em)

        # Generate Text Adventure
        em = discord.Embed(title="", color=discord.Color.teal(), description="")
        em.set_thumbnail(url=gif_url)
        em.add_field(
            name="",
            value=f":rocket: {username},\n {ctx.author.mention}, You are going to work 🚗",
            inline=False,
        )
        em.add_field(name="", value=f":rocket: {username},\n {work_text}", inline=False)
        if escalation_text is not None:
            em.add_field(
                name="",
                value=f":rocket: {username}, 🌟**BONUS**🌟\n{escalation_text}",
                inline=False,
            )
        if event.active:
            em.add_field(
                name="",
                value=f"🎉**EVENT DAY**🎉\nYou notice that there has been an extra payout on your pay slip, and the amount is **`{event_extra}`**:coin:",
                inline=False,
            )
            em.add_field(
                name="",
                value=f":rocket: {username},\n {work_end_text} **`{shift.paid}`**:coin:!!",
                inline=False,
            )
        else:
            em.add_field(
                name="",
                value=f":rocket: {username},\n {work_end_text} {shift.paid} :coin:",
                inline=False,
            )
        return await ctx.respond(embed=em)

    @mission.command(name="start")
    @option("action", description="Choose Mission", choices=["Mining", "Raiding"])
    async def missionevent(self, ctx: discord.ApplicationContext, action: str):
        """
        Start a Mission - to earn coins
        """
        modus = action.lower()
        if modus not in ("mining", "raiding"):
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, You haven't selected a `Mission`",
            )
            await ctx.respond(embed=em)
            return
        kind = Kind(modus)
        who = (ctx.guild.id, ctx.author.id, ctx.author.display_name)

        mission_account = await missions.get_mission(*who, kind)
        no_ship = discord.Embed(
            title="",
            color=discord.Color.red(),
            description=f"{ctx.author.mention}, You don't have a ship yet. \nYou can buy a ship with {get_command_mention(bot=self.bot, guild_id=ctx.guild.id, cog='TextAdventure', slash_command='mission', slash_command_group='buy')}. \nGet information about available ships with {get_command_mention(bot=self.bot, guild_id=ctx.guild.id, cog='TextAdventure', slash_command='mission', slash_command_group='price')}.",
        )
        if mission_account.ship is None:
            await ctx.respond(embed=no_ship)
            return

        # Roll the mission that starts now, in case this is the first one
        payout = random.randrange(10, 30) + mission_account.ship.payout_bonus
        success_chance = random.randint(1, 30) + mission_account.ship.success_bonus

        try:
            started = await missions.begin(*who, kind, payout, success_chance)
        except NoShip:
            await ctx.respond(embed=no_ship)
            return
        except OnCooldown as cooldown:
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, You are still on your way; come back in **`{missions.format_remaining(cooldown.remaining)}`**",
            )
            await ctx.respond(embed=em, ephemeral=True)
            return

        if started:
            em = discord.Embed(
                title="",
                color=discord.Color.teal(),
                description=f"{ctx.author.mention}, You are starting your mission. You can view the report once you return from your mission.",
            )
            return await ctx.respond(embed=em)

        # The previous mission is back: tell its story and let the pilot decide
        system = await models.EconomySolarSystem.objects.order_by("?").afirst()
        anomaly_text, story_text, interaction_text = mission_account.get_story()
        components = [
            missionfunc.MissionComponent("Attack", discord.ButtonStyle.danger),
            missionfunc.MissionComponent("Warp Out", discord.ButtonStyle.green),
        ]
        if kind is Kind.MINING:
            components.append(
                missionfunc.MissionComponent("Cyno", discord.ButtonStyle.blurple)
            )

        em = discord.Embed(title="", color=discord.Color.teal())
        em.add_field(
            name="",
            value=f":rocket: {ctx.author.display_name},\n You are flying with your **`{mission_account.ship.name}`** into the system **`{system if system else 'Unknown'}`**.",
            inline=False,
        )
        for text in (anomaly_text, story_text, interaction_text):
            em.add_field(
                name="",
                value=f":rocket: {ctx.author.display_name},\n {text}",
                inline=False,
            )
        await ctx.respond(
            embed=em,
            view=missionfunc.MissionEvent(
                components=components,
                ctx=ctx,
                mission_account=mission_account,
                kind=kind,
                event=await missions.get_event(ctx.guild.id),
            ),
        )

    @mission.command(name="cancel")
    @option("action", description="Choose Mission", choices=["Mining", "Raiding"])
    async def mission_cancel(self, ctx: discord.ApplicationContext, action: str):
        """
        Cancel an active Mission
        """
        modus = action.lower()
        if modus not in ("mining", "raiding"):
            return await ctx.respond(
                f"{ctx.author.mention}, You haven't selected a `Mission`",
                ephemeral=True,
            )
        try:
            await missions.cancel(
                ctx.guild.id, ctx.author.id, ctx.author.display_name, Kind(modus)
            )
        except NoActiveMission as error:
            return await ctx.respond(
                f"{ctx.author.mention}, {error.message}", ephemeral=True
            )
        return await ctx.respond(
            f"{ctx.author.mention}, Your active mission for **`{modus}`** has been canceled."
        )

    @mission.command()
    @option(
        "category",
        description="Shows the items in the store",
        choices=["Mining", "Raiding"],
    )
    @option(
        "item",
        description="Get more information about a specific item",
        autocomplete=get_shop,
    )
    async def buy(self, ctx: discord.ApplicationContext, category: str, item: str):
        """
        Buy a specific Ship for Mission Event
        """
        if category not in ("Mining", "Raiding"):
            return await ctx.respond(
                f"{ctx.author.mention}, No Category Selected.",
                ephemeral=True,
            )
        try:
            await missions.buy_ship(
                ctx.guild.id,
                ctx.author.id,
                ctx.author.display_name,
                Kind(category.lower()),
                item,
            )
        except ShipNotFound:
            color = discord.Color.red()
            text = f"The item `{item}` was not found!"
        except ShipAlreadyOwned:
            color = discord.Color.red()
            text = f"You already own the Ship **`{item}`**"
        except BankError:
            color = discord.Color.red()
            text = f"You don't have enough :coin: to buy **`{item}`**"
        else:
            color = discord.Color.teal()
            text = f"Buys a **`{item}`**"

        em = discord.Embed(
            title="", color=color, description=f"{ctx.author.mention}, {text}"
        )
        await ctx.respond(embed=em)

    @mission.command(name="price")
    @option(
        "category",
        description="Shows the items in the store",
        choices=["Mining", "Raiding"],
    )
    @option(
        "item",
        description="Get more information about a specific item",
        autocomplete=get_shop,
        required=False,
    )
    async def shipprice(
        self, ctx: discord.ApplicationContext, category: str, item=None
    ):
        """
        Get price information for specific Ship (with pagination if needed)
        """
        if category not in ("Mining", "Raiding"):
            return await ctx.respond(
                f"{ctx.author.mention}, Invalid category.", ephemeral=True
            )

        # Einzelnes Item anzeigen
        shop_data = [item async for item in models.EconomyShip.objects.all()]

        if item is not None:
            if item.capitalize() not in [item.name for item in shop_data]:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, The ship was not found!",
                )
                await ctx.respond(embed=em)
                return
            em = discord.Embed(
                title="Shop - Item Description",
                color=discord.Color.teal(),
                description="",
            )
            for data in shop_data:
                if data.category == category.lower():
                    name = data.name
                    price = data.price
                    desc = data.description
                    if item and item != name or item == name.lower():
                        continue
                    em.add_field(
                        name=f"\n\n {name} - :coin: {price}",
                        value=desc,
                        inline=False,
                    )
            await ctx.respond(embed=em)
            return

        # Pages for all ships of the category
        items_per_page = 10
        fields = []
        for data in shop_data:
            if data.category == category.lower():
                name = data.name
                price = data.price
                desc = data.description
                fields.append((name, price, desc))

        total_pages = (len(fields) + items_per_page - 1) // items_per_page

        def get_embed(page: int):
            em = discord.Embed(
                title=f"Shop (Seite {page + 1}/{total_pages})",
                color=discord.Color.teal(),
                description=f"Use {get_command_mention(bot=self.bot, guild_id=ctx.guild.id, cog='TextAdventure', slash_command='mission', slash_command_group='price')} `shipname` to learn more about the item. Use. \n Use {get_command_mention(bot=self.bot, guild_id=ctx.guild.id, cog='TextAdventure', slash_command='mission', slash_command_group='buy')} `shipname` to purchase the item. \n\n:money_with_wings: Here are the items:\n\n ",
            )
            for name, price, desc in fields[
                page * items_per_page : (page + 1) * items_per_page
            ]:
                em.add_field(
                    name=f"\n\n {name} - :coin: {price}",
                    value=desc,
                    inline=False,
                )
            return em

        class ShipPaginator(discord.ui.View):
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

        view = ShipPaginator(ctx.author.id)
        await ctx.respond(embed=get_embed(0), view=view)
        return
