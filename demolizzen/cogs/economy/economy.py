# Standard Library
import math
import random

# Third Party
from asgiref.sync import sync_to_async

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks

# Django
from django.db import transaction
from django.utils import timezone

# Demolizzen
from demolizzen import models
from demolizzen.config import EVENTS_SERVER
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen


# pylint: disable=too-many-public-methods
class Economy(commands.Cog):
    """All about economy"""

    # pylint: disable=import-outside-toplevel
    # Demolizzen
    from demolizzen.cogs.economy import missionfunc

    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.alias = "eco"
        self.title = "Economy"
        self._shop: list[models.EconomyShip] = []
        self.shop_data.start()

    economy = SlashCommandGroup(
        "economy", "Text Adventure", contexts=[discord.InteractionContextType.guild]
    )
    mission = economy.create_subgroup(
        "mission", contexts=[discord.InteractionContextType.guild]
    )

    # Update Shop every 2 Hours
    @tasks.loop(minutes=120)
    async def shop_data(self):
        await self.fetch_ship_data()

    @shop_data.before_loop
    async def before_shop_data(self):
        await self.bot.wait_until_ready()
        self.bot.logger.info("Shop Data Fetcher Ready")

    def cog_unload(self):
        self.shop_data.cancel()

    def set_event(self, guild_id, active, event_factor):
        self.events[guild_id] = (active, int(event_factor))

    def get_event(self, guild_id):
        return self.events.get(
            guild_id, (False, 0)
        )  # Standardwerte, falls das Event nicht vorhanden ist

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        try:
            user = await models.UserProfile.objects.select_related(
                "bank_account", "bags", "raid_mission", "mining_mission"
            ).aget(user_id=ctx.author.id, guild_id=ctx.guild.id)
            ctx.user_profile = user
            self.bot.logger.debug(f"UserProfile loaded for {ctx.author}.")
        except models.UserProfile.DoesNotExist as exc:
            raise commands.CheckFailure(
                "UserProfile does not exist. Please register first. `/auth register`"
            ) from exc

        try:
            assert user.bank_account
        except models.UserBankAccount.DoesNotExist as exc:
            raise commands.CheckFailure(
                "Bank account does not exist. Please create one first. `/bank create`"
            ) from exc

    async def fetch_ship_data(self) -> list[models.EconomyShip]:
        # Fetch shop data from the database and store it in self._shop.
        self.bot.logger.debug("Updating ship data...")
        ship_data = [item async for item in models.EconomyShip.objects.all()]
        self._shop.clear()
        self._shop.extend(ship_data)

    async def get_shop(self, ctx: discord.AutocompleteContext) -> list[str]:
        """Returns a list of names that begin with the entered characters."""
        try:
            category = ctx.options["category"].lower()
        # pylint: disable=broad-except
        except Exception:
            category = "Mining"
        search_term = ctx.value.lower()

        # Filter items that start with the search term
        filtered_items = [
            item.name
            for item in self._shop
            if item.category == category and search_term in item.name.lower()
        ]

        return filtered_items

    # pylint: disable=too-many-statements
    @economy.command()
    @checks.is_in_channel()
    async def work(self, ctx: discord.ApplicationContext):
        """
        Go to work and let the coins flow.
        """
        server_id = ctx.guild.id
        username = ctx.author.name
        username = username.capitalize()
        gif_url = "https://hell-rider.de/static/images/discord/work-working.gif"

        # Init User Data
        user_work, __ = await models.UserWorkMission.objects.select_related(
            "user"
        ).aget_or_create(user=ctx.user_profile)

        if server_id in EVENTS_SERVER:
            events, event_factor = EVENTS_SERVER[server_id]
        else:
            EVENTS_SERVER[server_id] = (False, 0)
            events, event_factor = EVENTS_SERVER[server_id]

        # Write Coin Reward
        payout = random.randrange(25, 75)
        chance = random.randint(1, 100)
        # Get more if you play Adventure
        escalation_payout = random.randrange(10, 25)

        # Timer Manager
        remaining_time = await user_work.user.get_cooldown(
            ctx=ctx,
            ship_cooldown=timezone.timedelta(seconds=user_work.job_duration),
            last_cooldown=user_work.cooldown,
        )

        # Generate Job Story
        work_text, escalation_text, work_end_text = user_work.get_work_text_combined()

        # Set Timer Variables
        delta = remaining_time.delta
        timer = remaining_time.timer
        remaining_time = remaining_time.cooldown

        if delta < timer:
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, You have already started working, come back in `{remaining_time}`",
            )
            await ctx.respond(embed=em)
            return

        if user_work.salary is None:
            em = discord.Embed(
                title="",
                color=discord.Color.teal(),
                description=f"{ctx.author.mention}, You are starting to work, come back in `{timer}`.",
            )
        else:
            # Generate Text Adventure
            em = discord.Embed(title="", color=discord.Color.teal(), description="")
            em.set_thumbnail(url=gif_url)
            em.add_field(
                name="",
                value=f":rocket: {username},\n {ctx.author.mention}, You are going to work 🚗",
                inline=False,
            )
            em.add_field(
                name="", value=f":rocket: {username},\n {work_text}", inline=False
            )
            if escalation_text is not None:
                em.add_field(
                    name="",
                    value=f":rocket: {username}, 🌟**BONUS**🌟\n{escalation_text}",
                    inline=False,
                )
                # Escalation Bonus
                payout += escalation_payout
            if events is True:
                # Event Bonus Payout
                eventdifference = payout
                payout = math.ceil(payout * event_factor)
                eventdifference = payout - eventdifference

                em.add_field(
                    name="",
                    value=f"🎉**EVENT DAY**🎉\nYou notice that there has been an extra payout on your pay slip, and the amount is **`{eventdifference}`**:coin:",
                    inline=False,
                )
                em.add_field(
                    name="",
                    value=f":rocket: {username},\n {work_end_text} **`{payout}`**:coin:!!",
                    inline=False,
                )
            else:
                em.add_field(
                    name="",
                    value=f":rocket: {username},\n {work_end_text} {payout} :coin:",
                    inline=False,
                )

        # Save Data
        def sync_save():
            with transaction.atomic():
                if user_work.salary is not None:
                    bank_account: models.UserBankAccount = ctx.user_profile.bank_account
                    bank_account.wallet += payout
                    bank_account.save()
                user_work.cooldown = timezone.now()
                user_work.chance = chance
                user_work.salary = payout
                user_work.save()

        await sync_to_async(sync_save)()
        return await ctx.respond(embed=em)

    @economy.command()
    @checks.is_in_channel()
    async def daily(self, ctx: discord.ApplicationContext):
        """
        Collect your Daily Reward
        """
        try:
            daily_account, __ = await models.UserDailyReward.objects.select_related(
                "user"
            ).aget_or_create(user=ctx.user_profile)

            # Timer Manager
            remaining_time = await daily_account.user.get_cooldown(
                ctx=ctx,
                ship_cooldown=timezone.timedelta(days=1),
                last_cooldown=daily_account.last_claim,
            )

            delta = remaining_time.delta
            cooldown = remaining_time.cooldown

            if delta < remaining_time.timer:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, You have already collected your daily reward, wait a bit more `{cooldown}`",
                )
                await ctx.respond(embed=em)
                return

            # Set Daily Reward
            # Streak: +1 wenn mehr als 24h vergangen, sonst 1
            streak = daily_account.streak + 1 if delta > remaining_time.timer else 1
            daily_account.streak = streak
            daily_account.last_claim = timezone.now()
            daily_reward = random.randrange(30) + (daily_account.streak * 5)
            # Update Bank Account
            bank_account: models.UserBankAccount = ctx.user_profile.bank_account
            bank_account.wallet += daily_reward
            await daily_account.asave()
            await bank_account.asave()

            # Send Response
            em = discord.Embed(
                title="",
                color=discord.Color.teal(),
                description=f"{ctx.author.mention}, **{streak}** At once. Here is your daily reward of {daily_reward}:coin:",
            )

            await ctx.respond(embed=em)
        except Exception as e:
            self.bot.logger.exception(f"Error in daily command: {e}")
            await ctx.respond(
                "An error occurred while processing your command. Please try again later."
            )
        return

    # ---------------------------- Mission ----------------------------
    # ---------------------------- Mission ----------------------------
    # ---------------------------- Mission ----------------------------

    @mission.command(name="start")
    @checks.is_in_channel()
    @option("action", description="Choose Mission", choices=["Mining", "Raiding"])
    async def missionevent(
        self, ctx: discord.ApplicationContext, action: str
    ):  # pylint: disable=too-many-statements
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

        if modus == "mining":
            mission_account, __ = await models.UserMiningMission.objects.select_related(
                "user", "user__bank_account", "ship"
            ).aget_or_create(user=ctx.user_profile)
        elif modus == "raiding":
            mission_account, __ = await models.UserRaidMission.objects.select_related(
                "user", "user__bank_account", "ship"
            ).aget_or_create(user=ctx.user_profile)
        else:
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, No mission selected.",
            )
            await ctx.respond(embed=em)
            return

        if mission_account.ship is None:
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, You don't have a ship yet. \nYou can buy a ship with `/mission buy`. \nGet information about available ships with `/price`.",
            )
            await ctx.respond(embed=em)
            return

        # Calculate Payout
        earning = random.randrange(10, 30)
        payout_bonus = mission_account.ship.payout_bonus
        payout = earning + payout_bonus
        # Calculate Success Chance
        random_chance = random.randint(1, 30)
        ship_success_bonus = mission_account.ship.success_bonus
        success_chance = random_chance + ship_success_bonus
        # Timer Manager
        cooldown_info = await mission_account.user.get_cooldown(
            ctx,
            timezone.timedelta(seconds=mission_account.ship.ship_speed),
            mission_account.cooldown,
        )

        # Get Adventure Data
        system = await models.EconomySolarSystem.objects.order_by("?").afirst()
        anomaly_text, story_text, interaction_text = mission_account.get_story()

        if cooldown_info.delta < cooldown_info.timer:
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, You are still on your way; come back in **`{cooldown_info.cooldown}`**",
            )
            await ctx.respond(embed=em, ephemeral=True)
            return

        if mission_account.salary is None:
            em = discord.Embed(
                title="",
                color=discord.Color.teal(),
                description=f"{ctx.author.mention}, You are starting your mission. You can view the report once you return from your mission.",
            )

            mission_account.cooldown = timezone.now()
            mission_account.chance = success_chance
            mission_account.salary = payout
            mission_account.active = True
            await mission_account.asave()
            return await ctx.respond(embed=em)

        if modus == "raiding":
            components = [
                self.missionfunc.MissionComponent("Attack", discord.ButtonStyle.danger),
                self.missionfunc.MissionComponent(
                    "Warp Out", discord.ButtonStyle.green
                ),
            ]
        else:
            components = [
                self.missionfunc.MissionComponent("Attack", discord.ButtonStyle.danger),
                self.missionfunc.MissionComponent(
                    "Warp Out", discord.ButtonStyle.green
                ),
                self.missionfunc.MissionComponent("Cyno", discord.ButtonStyle.blurple),
            ]

        em = discord.Embed(title="", color=discord.Color.teal())
        em.add_field(
            name="",
            value=f":rocket: {ctx.author.display_name},\n You are flying with your **`{mission_account.ship.name}`** into the system **`{system if system else 'Unknown'}`**.",
            inline=False,
        )
        em.add_field(
            name="",
            value=f":rocket: {ctx.author.display_name},\n {anomaly_text}",
            inline=False,
        )
        em.add_field(
            name="",
            value=f":rocket: {ctx.author.display_name},\n {story_text}",
            inline=False,
        )
        em.add_field(
            name="",
            value=f":rocket: {ctx.author.display_name},\n {interaction_text}",
            inline=False,
        )
        mission_account.active = True
        await ctx.response.send_message(embed=em)
        await ctx.send(
            view=self.missionfunc.MissionEvent(
                components=components,
                ctx=ctx,
                mission_account=mission_account,
            )
        )
        return

    @mission.command(name="cancel")
    @checks.is_in_channel()
    @option("action", description="Choose Mission", choices=["Mining", "Raiding"])
    async def mission_cancel(self, ctx: discord.ApplicationContext, action: str):
        """
        Cancel an active Mission
        """
        modus = action.lower()
        mission_account = None
        if modus == "mining":
            try:
                mission_account = await models.UserMiningMission.objects.aget(
                    user=ctx.user_profile
                )
            except models.UserMiningMission.DoesNotExist:
                return await ctx.respond(
                    f"{ctx.author.mention}, You don't have a mining mission account yet. Please start a mining mission first.",
                    ephemeral=True,
                )
        if modus == "raiding":
            try:
                mission_account = await models.UserRaidMission.objects.aget(
                    user=ctx.user_profile
                )
            except models.UserRaidMission.DoesNotExist:
                return await ctx.respond(
                    f"{ctx.author.mention}, You don't have a raid mission account yet. Please start a raid mission first.",
                    ephemeral=True,
                )
        if modus not in ("mining", "raiding"):
            return await ctx.respond(
                f"{ctx.author.mention}, You haven't selected a `Mission`",
                ephemeral=True,
            )
        if mission_account is None or mission_account.active is False:
            return await ctx.respond(
                f"{ctx.author.mention}, You don't have an active mission to cancel.",
                ephemeral=True,
            )

        # Cancel the active mission
        mission_account.active = False
        mission_account.cooldown = None
        mission_account.chance = None
        mission_account.salary = None
        await mission_account.asave()

        return await ctx.respond(
            f"{ctx.author.mention}, Your active mission for **`{modus}`** has been canceled."
        )

    @mission.command()
    @checks.is_in_channel()
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
        try:
            bank_account = ctx.user_profile.bank_account
            if category == "Mining":
                mission_account = ctx.user_profile.mining_mission
            elif category == "Raiding":
                mission_account = ctx.user_profile.raid_mission
            else:
                return await ctx.respond(
                    f"{ctx.author.mention}, No Category Selected.",
                    ephemeral=True,
                )
        except models.UserMiningMission.DoesNotExist:
            mission_account = await models.UserMiningMission.objects.select_related(
                "user__bank_account"
            ).acreate(user=ctx.user_profile)
        except models.UserRaidMission.DoesNotExist:
            mission_account = await models.UserRaidMission.objects.select_related(
                "user__bank_account"
            ).acreate(user=ctx.user_profile)

        async def buy_ship(
            item_name,
            category: str,
            mission_account: models.UserMiningMission | models.UserRaidMission,
            bank_account: models.UserBankAccount,
        ):
            try:
                ship = await models.EconomyShip.objects.aget(
                    name__iexact=item_name, category=category.lower()
                )
            except models.EconomyShip.DoesNotExist:
                response = [False, 1]  # Item not found

            if mission_account.ship == ship.name:
                response = [False, 2]  # Item already owned

            def check_bill():
                with transaction.atomic():
                    mission_account.ship = ship
                    if bank_account.wallet >= ship.price:
                        bank_account.wallet -= ship.price
                        bank_account.save()
                        mission_account.save()
                        return True
                    return False

            purchased = await sync_to_async(check_bill)()
            if purchased:
                response = [True, 0]
            else:
                response = [False, 3]  # Benutzer hat nicht genug Geld

            if response[0] is True:
                em = discord.Embed(
                    title="",
                    color=discord.Color.teal(),
                    description=f"{ctx.author.mention}, Buys a **`{item}`**",
                )
            else:
                if response[1] == 1:
                    em = discord.Embed(
                        title="",
                        color=discord.Color.red(),
                        description=f"{ctx.author.mention}, The item `{item}` was not found!",
                    )
                elif response[1] == 2:
                    em = discord.Embed(
                        title="",
                        color=discord.Color.red(),
                        description=f"{ctx.author.mention}, You already own the Ship **`{item}`**",
                    )
                elif response[1] == 3:
                    em = discord.Embed(
                        title="",
                        color=discord.Color.red(),
                        description=f"{ctx.author.mention}, You don't have enough :coin: to buy **`{item}`**",
                    )
                else:
                    em = discord.Embed(
                        title="",
                        color=discord.Color.red(),
                        description=f"{ctx.author.mention}, An unknown error occurred.",
                    )
            await ctx.respond(embed=em)

        return await buy_ship(item, category, mission_account, bank_account)

    @mission.command(name="price")
    @checks.is_in_channel()
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
        if item is not None:
            if item.capitalize() not in [item.name for item in self._shop]:
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
            for data in self._shop:
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

        # Pagination für alle Schiffe der Kategorie
        items_per_page = 10
        fields = []
        for data in self._shop:
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
                description="Use `/eve mission price` `schiffname` to learn more about the item. Use. \n Use `/eve buy` `schiffname` to purchase the item. \n\n:money_with_wings: Here are the items:\n\n ",
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

    @mission.command()
    @checks.is_in_channel()
    @commands.cooldown(1, 300, commands.BucketType.user)
    @option("user", description="Wähle User")
    async def gank(self, ctx: discord.ApplicationContext, user: discord.Member):
        """
        Engage a target member and attempt to steal their coins.

        Arguments
        ----------
        ctx: `context`
            The context containing information about the request.
        user: `member`
            The target member from whom to attempt to steal coins.

        Returns
        -------
        str
            A message indicating the outcome of the attempted theft.
        """
        # Get Information for further process
        server_id = ctx.guild.id
        author = ctx.author.name.capitalize()

        try:
            gank_account = await models.UserProfile.objects.select_related(
                "bank_account"
            ).aget(user_id=user.id, guild_id=server_id)
            assert gank_account.bank_account  # Ensure bank_account is loaded
        except (models.UserProfile.DoesNotExist, models.UserBankAccount.DoesNotExist):
            gank_account = None

        if gank_account is None:
            await ctx.respond("He hasn't a Bank Account...", ephemeral=True)
            return

        # Embed create
        em = discord.Embed(title="", color=discord.Color.teal(), description="")
        em.add_field(
            name="",
            value=f":rocket: {ctx.author.mention} tries to gank {user.mention}!",
            inline=False,
        )

        # Configuration Gank System
        random_chance = random.randint(1, 100)
        amount = random.randint(1, 10)

        user_name = user.display_name.capitalize()
        # Text Adventure (English)
        ganktext = [
            "approaches and successfully starts scrambling!",
            "warps in and opens fire on the target.",
            "is surprised after being locked and pointed. Then leaves the ship frustrated...",
            f"spots {user_name}, who is AFK mining, and shoots their ship. It explodes...",
        ]

        # Text Adventure (English, failed raid)
        ganktext2 = [
            f"approaches and is immediately shot at by {user_name}!",
            f"warps to {user_name} and realizes local is full of reds...",
            f"surprises {user_name}, but doesn't realize {user_name} is sitting in a Titan 💣.",
            f"notices {user_name} is AFK mining. As they get closer, {user_name} quickly lights a Cyno.",
        ]

        bank_account: models.UserBankAccount = ctx.user_profile.bank_account

        # Erfolgreicher Raid
        if random_chance <= 25:
            # Überprüfen, ob der Benutzer genug Geld hat
            if gank_account.bank_account.wallet < amount:
                em.add_field(
                    name="",
                    value=f":rocket: {author} " + random.choice(ganktext) + "",
                    inline=False,
                )
                em.add_field(
                    name="",
                    value=f":rocket: {author} loots the wreck and finds it empty...",
                    inline=False,
                )
                await ctx.respond(embed=em)
                return

            # Attempt to update both balances
            def gank_transaction():
                with transaction.atomic():
                    gank_account.bank_account.wallet -= amount
                    bank_account.wallet += amount
                    gank_account.bank_account.save()
                    bank_account.save()

            sync_to_async(gank_transaction)()

            em.add_field(
                name="",
                value=f":rocket: {author} " + random.choice(ganktext) + "",
                inline=False,
            )
            em.add_field(
                name="",
                value=f":rocket: {author} has looted {amount}:coin:!",
                inline=False,
            )
            return await ctx.respond(embed=em)

        # Mißlungerner Raid
        if random_chance <= 70:
            # Überprüfen, ob der Benutzer genug Geld hat
            if bank_account.wallet < amount:
                em.add_field(
                    name="",
                    value=f":rocket: {author} you are broke... go back to work...",
                    inline=False,
                )
                return await ctx.respond(embed=em)

            def gank_fail_transaction():
                with transaction.atomic():
                    bank_account.wallet -= amount
                    gank_account.bank_account.wallet += amount
                    bank_account.save()
                    gank_account.bank_account.save()

            await sync_to_async(gank_fail_transaction)()

            em.add_field(
                name="",
                value=f":rocket: {author} " + random.choice(ganktext2) + "",
                inline=False,
            )
            em.add_field(
                name="",
                value=f":rocket: {author} has lost {amount}:coin:!",
                inline=False,
            )
            await ctx.respond(embed=em)
            return

        em.add_field(
            name="",
            value=f":rocket: {author} a wormhole appeared and sent you to another system.",
            inline=False,
        )
        return await ctx.respond(embed=em)

    # ---------------------------- Listener ----------------------------
    # ---------------------------- Listener ----------------------------
    # ---------------------------- Listener ----------------------------

    # on guild leave
    # pylint: disable=duplicate-code
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        pass

    # on guild leave
    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        pass
