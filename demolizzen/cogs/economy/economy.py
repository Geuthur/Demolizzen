import logging
import math
import random
from datetime import datetime, timedelta

import discord
from core import checks
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands

# Database
from settings import db

# Set Global Variable for Event Status
from settings.config import EVENTS_SERVER
from settings.functions import application_cooldown

# Mission System
from . import mission, missionfunc

# Economy System
from .settings import (
    get_work2_text,
    get_work_bonus_text,
    get_work_end_text,
    get_work_text,
)

log = logging.getLogger("main")
log_events = logging.getLogger("events")


class Eco(commands.Cog):
    """
    All about economy
    """

    def __init__(self, bot):
        self.bot = bot
        self.alias = "eco"
        self.title = "Economy"
        self._shop = []
        self._ship_chance = mission.ship_chance_var
        self._ship_speed = mission.ship_speed_var

        # Call the fetch_shop_data method when the class is initialized
        self.shop_data = self.bot.loop.create_task(self.fetch_shop_data())

    economy = SlashCommandGroup(
        "economy", "Text Adventure", contexts=[discord.InteractionContextType.guild]
    )
    mission = economy.create_subgroup(
        "mission", contexts=[discord.InteractionContextType.guild]
    )

    def cog_unload(self):
        self.shop_data.cancel()

    def set_event(self, guild_id, active, event_factor):
        self.events[guild_id] = (active, int(event_factor))

    def get_event(self, guild_id):
        return self.events.get(
            guild_id, (False, 0)
        )  # Standardwerte, falls das Event nicht vorhanden ist

    async def fetch_shop_data(self):
        await self.bot.wait_until_ready()
        sql = "SELECT * FROM `eve_shop`"
        shop_data = await db.select(sql, dictlist=True)
        # Löschen Sie die vorhandenen Daten in self._shop
        self._shop.clear()
        # Fügen Sie die neuen Daten aus der Datenbank hinzu
        self._shop.extend(shop_data)

    async def get_shop(self, ctx: discord.AutocompleteContext):
        """Returns a list of names that begin with the entered characters."""
        try:
            category = ctx.options["category"].lower()
        # pylint: disable=broad-except
        except Exception:
            category = "Mining"
        search_term = ctx.value.lower()

        # Filter items that start with the search term
        filtered_items = [
            item["name"]
            for item in self._shop
            if item["shop"] == category and search_term in item["name"].lower()
        ]

        return filtered_items

    async def db_connection(self, ctx: discord.ApplicationContext):
        log.error("[Economy Work Command] DB Connection Problem")
        em = discord.Embed(
            color=discord.Color.red(),
            description="❌ An error occurred, please try again later.",
        )
        await ctx.respond(embed=em, ephemeral=True, delete_after=10)
        return

    @economy.command()
    @checks.is_in_channel()
    @commands.cooldown(
        3, 600, commands.BucketType.user
    )  # 3 Mal alle 10 Minuten pro Benutzer
    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    async def work(self, ctx: discord.ApplicationContext):
        """
        Go to work and let the coins flow.
        """
        # await ctx.defer()

        # Get Server-ID for further process
        server_id = ctx.guild.id
        user_id = ctx.author.id
        user = ctx.author
        username = ctx.author.name
        username = username.capitalize()
        gif_url = "https://hell-rider.de/static/images/discord/work-working.gif"

        # Init User Data
        sql = "SELECT * FROM `working` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        val = {"user_id": user_id, "guild_id": server_id}
        usersdata = await db.select_var(sql, val, single=True, dictlist=True)

        # Init User Bank Data
        sql = f"SELECT * FROM `bank` WHERE `user_id` = {user_id} AND `guild_id` = {server_id}"
        userbank = await db.select(sql, single=True, dictlist=True)

        if usersdata is None:
            usersdata = await db.create_user(user, server_id, "working")
        elif usersdata is False:
            await self.db_connection(ctx)
            return

        if userbank is None:
            userbank = await db.create_user(user, server_id, "bank")
        elif userbank is False:
            await self.db_connection(ctx)
            return

        # Set All Database entrys
        last_coin = int(usersdata["loan"])
        userchance = usersdata["chance"]
        usercooldown = usersdata["cooldown"]

        if server_id in EVENTS_SERVER:
            events, event_factor = EVENTS_SERVER[server_id]
        else:
            EVENTS_SERVER[server_id] = (False, 0)
            events, event_factor = EVENTS_SERVER[server_id]

        bonus_text = get_work_bonus_text()
        worktext = get_work_text()
        worktext2 = get_work2_text()
        workend = get_work_end_text()

        # Write Coin Reward
        earnings = random.randrange(25, 75)

        # Bonus Chance Calculator
        bonus = random.randint(1, 100)
        bonus_chance = 25
        # Chance Calculator
        chance = random.randint(1, 100)

        # Write Report Bonus Coin Reward
        reportbonus = random.randrange(10, 25)

        # Timer Manager
        cooldown_manager = missionfunc.CooldownManager(server_id)
        await cooldown_manager.get_cooldown(ctx, "work", usercooldown)

        # Set Timer Variables
        delta = cooldown_manager.delta
        timer = cooldown_manager.timer
        cooldown = cooldown_manager.cooldown

        if delta < timer:
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, You have already started working, come back in `{cooldown}`",
            )
            await ctx.respond(embed=em)
            return

        if last_coin == 0:
            em = discord.Embed(
                title="",
                color=discord.Color.teal(),
                description=f"{ctx.author.mention}, You are starting to work, your earnings are {earnings} :coin: Collect them later.",
            )
            # Write Earn Coins
            userwallet = +last_coin

        else:
            # Set Report Bonus
            if bonus <= bonus_chance:
                last_coin += reportbonus
            # Event Bonus Coin
            if events is True:
                eventdifference = last_coin
                last_coin = math.ceil(last_coin * event_factor)
                eventdifference = last_coin - eventdifference
            # Summary Value Earn Coins
            userwallet = +last_coin

            em = discord.Embed(title="", color=discord.Color.teal(), description="")
            em.set_thumbnail(url=gif_url)
            em.add_field(
                name="",
                value=f":rocket: {username},\n {ctx.author.mention}, You are going to work 🚗",
                inline=False,
            )
            em.add_field(
                name="", value=f":rocket: {username},\n {worktext}", inline=False
            )
            em.add_field(
                name="", value=f":rocket: {username},\n {worktext2}", inline=False
            )
            if bonus <= bonus_chance:
                em.add_field(
                    name="",
                    value=f":rocket: {username}, 🌟**BONUS**🌟\n{bonus_text}",
                    inline=False,
                )
            if events:
                em.add_field(
                    name="",
                    value=f"🎉**EVENT DAY**🎉\nYou notice that there has been an extra payout on your pay slip, and the amount is **`{eventdifference}`**:coin:",
                    inline=False,
                )
                em.add_field(
                    name="",
                    value=f":rocket: {username},\n {workend} **`{last_coin}`**:coin:!!",
                    inline=False,
                )
            else:
                em.add_field(
                    name="",
                    value=f":rocket: {username},\n {workend} {last_coin} :coin:",
                    inline=False,
                )

        # Cooldown is written after this the Timer begins
        usercooldown = str(datetime.now())
        # Set Mining Chance
        userchance = chance
        # Set Reward
        last_coin = earnings

        if not last_coin == 0:
            userbank["wallet"] += userwallet
            earn = userbank["wallet"]
            e_query = f"UPDATE bank SET `wallet` = {earn} WHERE `user_id` = {user_id} AND `guild_id` = {server_id}"
            await db.execute_sql(e_query)

        l_query = f"UPDATE working SET `loan` = {last_coin}, `chance` = {userchance}, `cooldown` = '{usercooldown}' WHERE `user_id` = {user_id} AND `guild_id` = {server_id}"
        update = await db.execute_sql(l_query)

        if update is False:
            await self.db_connection(ctx)
            return

        await ctx.respond(embed=em)
        return

    @work.error
    async def command_cooldown(self, ctx, error):
        await application_cooldown(ctx, error)

    @economy.command()
    @checks.is_in_channel()
    @commands.cooldown(
        3, 600, commands.BucketType.user
    )  # 3 Mal alle 10 Minuten pro Benutzer
    async def daily(self, ctx: discord.ApplicationContext):
        """
        Collect your Daily Reward
        """
        # await ctx.defer()

        # Get Server-ID for further process
        server_id = ctx.guild.id
        user = ctx.author
        user_id = ctx.author.id

        # Reads and Write the Daily
        sql = "SELECT * FROM `daily` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        val = {"user_id": user_id, "guild_id": server_id}
        users = await db.select_var(sql, val, single=True, dictlist=True)

        # Init User Bank Data
        sql = f"SELECT * FROM `bank` WHERE `user_id` = {user_id} AND `guild_id` = {server_id}"
        userbank = await db.select(sql, single=True, dictlist=True)

        if users is None:
            users = await db.create_user(user, server_id, "daily")
        elif users is False:
            await self.db_connection(ctx)
            return

        if userbank is None:
            userbank = await db.create_user(user, server_id, "bank")
        elif userbank is False:
            await self.db_connection(ctx)
            return

        # Get User Streak
        streak = users["streak"]
        usercooldown = users["last_claim"]

        # Timer Manager
        cooldown_manager = missionfunc.CooldownManager(server_id)
        await cooldown_manager.get_cooldown(ctx, "daily", usercooldown)

        delta = cooldown_manager.delta
        cooldown = cooldown_manager.cooldown

        if delta < timedelta(hours=24):
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, You have already collected your daily reward, wait a bit more `{cooldown}`",
            )
            await ctx.respond(embed=em)
            return

        streak += 1
        if delta > timedelta(hours=48):
            streak = 1
        daily = random.randrange(30) + (streak * 5)

        userbank["wallet"] += daily
        earn = userbank["wallet"]

        usercooldown = str(datetime.now())

        # Save Data
        sql_query = [
            f"UPDATE daily SET `last_claim` = '{usercooldown}', `streak` = {streak} WHERE `user_id` = {user_id} AND `guild_id` = {server_id}",
            f"UPDATE bank SET `wallet` = {earn} WHERE `user_id` = {user_id} AND `guild_id` = {server_id}",
        ]
        sql_query = [query for query in sql_query if query is not None]

        update = await db.executemany_sql(sql_query)
        if update is False:
            await self.db_connection(ctx)
            return

        em = discord.Embed(
            title="",
            color=discord.Color.teal(),
            description=f"{ctx.author.mention}, **{streak}** At once. Here is your daily reward of {daily}:coin:",
        )
        await ctx.respond(embed=em)
        return

    @daily.error
    async def daily_cooldown(self, ctx, error):
        await application_cooldown(ctx, error)

    # ---------------------------- Mission ----------------------------
    # ---------------------------- Mission ----------------------------
    # ---------------------------- Mission ----------------------------

    @mission.command(name="start")
    @checks.is_in_channel()
    # @commands.cooldown(5, 600, commands.BucketType.user)  # 3 Mal alle 10 Minuten pro Benutzer
    @option("action", description="Choose Mission", choices=["Mining", "Raiding"])
    # pylint: disable=too-many-statements, too-many-locals
    async def missionevent(self, ctx: discord.ApplicationContext, action: str):
        # start = time.time()
        """
        Start a Mission - to earn coins
        """
        # await ctx.defer()

        # Get Server-ID for further process
        server_id = ctx.guild_id
        user_id = ctx.author.id
        user = ctx.author
        username = ctx.author.name
        username = username.capitalize()

        modus = action.lower()
        # print(f"task init done - {time.time() - start}")

        if modus not in ("mining", "raiding"):
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, You haven't selected a `Mission`",
            )
            await ctx.respond(embed=em)
            return

        # Init all important data
        sql = f"SELECT * FROM `{modus}` WHERE `user_id` = {user_id} AND `guild_id` = {server_id}"
        usersdata = await db.select(sql, single=True, dictlist=True)

        if usersdata is None:
            usersdata = await db.create_user(user, server_id, f"{modus}")
        elif usersdata is False:
            await self.db_connection(ctx)
            return

        # Init User Bank Data
        sql = f"SELECT * FROM `bank` WHERE `user_id` = {user_id} AND `guild_id` = {server_id}"
        userbank = await db.select(sql, single=True, dictlist=True)

        if userbank is None:
            userbank = await db.create_user(user, server_id, "bank")
        elif userbank is False:
            await self.db_connection(ctx)
            return

        # print(f"task check user done - {time.time() - start}")
        # Set All Database entrys
        last_coin = int(usersdata["loan"])
        userschiff = usersdata["schiff"]
        userchance = usersdata["chance"]
        usercooldown = usersdata["cooldown"]
        usertype = usersdata["type"]

        # Chance Calculator
        chance = random.randint(1, 100)
        # Get Mining Data
        ship_coin_var = mission.generate_ship_coin_var()
        # Get User Data
        mining = ship_coin_var.get(usersdata["type"])

        # Timer Manager
        cooldown_manager = missionfunc.CooldownManager(server_id)
        await cooldown_manager.get_cooldown(ctx, usertype, usercooldown)

        delta = cooldown_manager.delta
        timer = cooldown_manager.timer
        cooldown = cooldown_manager.cooldown

        # Get Adventure Data
        schiff = mission.get_random_ship(modus)
        system = mission.get_random_system()
        story_information = mission.get_story_information(modus)

        # Get Text Adventure
        anomalie_text = mission.get_anomalie_text()
        story_text = mission.get_story_text(modus, story_information)

        # Interaction Text
        event_interction = mission.get_interaction_text_mining(modus)

        # print(f"task init mission data done - {time.time() - start}")

        if delta < timer:
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, You are still on your way; come back in **`{cooldown}`**",
            )
            await ctx.respond(embed=em)
            return

        if userschiff == "0":
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, You don't have a ship yet. \nYou can buy a ship with `/buy`. \nGet information about available ships with `/price`.",
            )
            await ctx.respond(embed=em)
            return

        if last_coin == 0:
            em = discord.Embed(
                title="",
                color=discord.Color.teal(),
                description=f"{ctx.author.mention}, You are starting your mission. You can view the report once you return from your mission.",
            )
            # Write Earn Coins
            userwallet = +last_coin
            # Cooldown is written after this the Timer begins
            usercooldown = str(datetime.now())
            # Set Mining Chance
            userchance = chance
            # Set Reward
            last_coin = mining

            if not last_coin == 0:
                userbank["wallet"] += userwallet
                earn = userbank["wallet"]
                e_query = f"UPDATE bank SET `wallet` = {earn} WHERE `user_id` = {user_id} AND `guild_id` = {server_id}"
                await db.execute_sql(e_query)

            l_query = f"UPDATE {modus} SET `loan` = {last_coin}, `chance` = {userchance}, `cooldown` = '{usercooldown}' WHERE `user_id` = {user_id} AND `guild_id` = {server_id}"
            update = await db.execute_sql(l_query)

            if update is False:
                await self.db_connection(ctx)
                return

            await ctx.respond(embed=em)
            return

        if modus == "raiding":
            components = [
                missionfunc.MissionComponent("Attack", discord.ButtonStyle.danger),
                missionfunc.MissionComponent("Warp Out", discord.ButtonStyle.green),
            ]
        else:
            components = [
                missionfunc.MissionComponent("Attack", discord.ButtonStyle.danger),
                missionfunc.MissionComponent("Warp Out", discord.ButtonStyle.green),
                missionfunc.MissionComponent("Cyno", discord.ButtonStyle.blurple),
            ]

        em = discord.Embed(title="", color=discord.Color.teal())
        em.add_field(
            name="",
            value=f":rocket: {username},\n You are flying with your **`{userschiff}`** into the system **`{system}`**.",
            inline=False,
        )
        em.add_field(
            name="",
            value=f":rocket: {username},\n {anomalie_text}",
            inline=False,
        )
        em.add_field(
            name="", value=f":rocket: {username},\n {story_text}", inline=False
        )
        em.add_field(
            name="",
            value=f":rocket: {username},\n {event_interction}",
            inline=False,
        )
        await ctx.response.send_message(embed=em)
        await ctx.send(
            view=missionfunc.MissionEvent(
                components=components,
                ctx=ctx,
                data=usersdata,
                modus=modus,
                story=story_information,
                schiff=schiff,
            )
        )
        return

    @missionevent.error
    async def mission_cooldown(self, ctx: discord.ApplicationContext, error):
        await application_cooldown(ctx, error)

    @mission.command()
    @checks.is_in_channel()
    @commands.cooldown(
        10, 600, commands.BucketType.user
    )  # 10 Mal alle 10 Minuten pro Benutzer
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
    async def buy(self, ctx, category: str, item: str):
        """
        Buy a specific Ship for Mission Event
        """
        em = discord.Embed(
            title="",
            color=discord.Color.teal(),
            description=f"{ctx.author.mention}, You haven't selected a category",
        )

        server_id = ctx.guild.id
        if category in ("Mining", "Raiding"):
            res_raid = None
            if category == "Mining":
                res_raid = await missionfunc.buy_system(
                    ctx.author, item, server_id, "mining"
                )
            elif category == "Raiding":
                res_raid = await missionfunc.buy_system(
                    ctx.author, item, server_id, "raiding"
                )

            if res_raid[0]:
                em = discord.Embed(
                    title="",
                    color=discord.Color.teal(),
                    description=f"{ctx.author.mention}, Buys a **`{item}`**",
                )
            else:
                # pylint disable=duplication-code
                if res_raid[1] == 1:
                    em = discord.Embed(
                        title="",
                        color=discord.Color.red(),
                        description=f"{ctx.author.mention}, The item `{item}` was not found!",
                    )
                if res_raid[1] == 2:
                    em = discord.Embed(
                        title="",
                        color=discord.Color.red(),
                        description=f"{ctx.author.mention}, You already own the Ship **`{item}`**",
                    )
                if res_raid[1] == 3:
                    em = discord.Embed(
                        title="",
                        color=discord.Color.red(),
                        description=f"{ctx.author.mention}, You don't have enough :coin: to buy **`{item}`**",
                    )
                if res_raid[1] == 4:
                    em = discord.Embed(
                        title="",
                        color=discord.Color.red(),
                        description=f"{ctx.author.mention}, The database server seems unresponsive; please try again later.",
                    )
                if res_raid[1] == 5:
                    em = discord.Embed(
                        title="",
                        color=discord.Color.red(),
                        description=f"{ctx.author.mention}, You don't have a bank account to make a purchase.",
                    )
            await ctx.respond(embed=em)
            return

        await ctx.respond(embed=em)

    @buy.error
    async def buy_cooldown(self, ctx, error):
        await application_cooldown(ctx, error)

    @mission.command(name="price")
    @checks.is_in_channel()
    @commands.cooldown(
        10, 600, commands.BucketType.user
    )  # 10 Mal alle 10 Minuten pro Benutzer
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
    async def shipprice(self, ctx, category: str, item=None):
        """
        Get price information for specific Ship
        """
        # await ctx.defer()
        # pylint: disable=duplicate-code
        if category in ("Mining", "Raiding"):
            if item is None:
                em = discord.Embed(
                    title="Shop",
                    color=discord.Color.teal(),
                    description="Use `/eve mission price` `schiffname` to learn more about the item. Use. \n Use `/eve buy` `schiffname` to purchase the item. \n\n:money_with_wings: Here are the items:\n\n ",
                )
            else:
                if item.capitalize() not in [item["name"] for item in self._shop]:
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
                if data["shop"] == category.lower():
                    name = data["name"]
                    price = data["price"]
                    desc = data["description"]

                    if item and item != name or item == name.lower():
                        continue

                    em.add_field(
                        name=f"\n\n {name} - :coin: {price}",
                        value=desc,
                        inline=False,
                    )

            await ctx.respond(embed=em)
            return

    @shipprice.error
    async def shipprice_cooldown(self, ctx, error):
        await application_cooldown(ctx, error)

    @mission.command()
    @checks.is_in_channel()
    @commands.cooldown(1, 1800, commands.BucketType.user)
    @option("user", description="Wähle User")
    async def gank(self, ctx, user: discord.Member):
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
        # await ctx.defer()

        # Get Information for further process
        server_id = ctx.guild.id
        author = ctx.author.name.capitalize()

        # Opfer
        sql = f"SELECT * FROM `bank` WHERE `user_id` = {user.id} AND `guild_id` = {server_id}"
        baluser = await db.select(sql, single=True, dictlist=True)

        # Angreifer
        sql = f"SELECT * FROM `bank` WHERE `user_id` = {ctx.author.id} AND `guild_id` = {server_id}"
        balauthor = await db.select(sql, single=True, dictlist=True)

        if not baluser or not balauthor:
            await ctx.respond("You or He hasn't a Bank Account...", delete_after=10)
            return

        # Embed create
        em = discord.Embed(title="", color=discord.Color.teal(), description="")
        em.add_field(
            name="",
            value=f":rocket: {ctx.author.mention} versucht gerade {user.mention} zu Ganken!",
            inline=False,
        )

        # Configuration Gank System
        random_chance = random.randint(1, 100)
        amount = random.randint(1, 10)

        user_name = user.display_name.capitalize()
        # Text Adventure
        ganktext = [
            "nähert sich und beginnt erfolgreich zu scramblen!",
            "warpt heran und eröffnet das Feuer auf sein Ziel.",
            "wird überrascht, nachdem er aufgeschaltet und gepunktet wurde. Dann verlässt er das Schiff frustriert...",
            f"entdeckt {user_name}, der AFK beim Minern ist, und schießt auf sein Schiff. Es explodiert...",
        ]

        # Textabenteuer
        ganktext2 = [
            f"nähert sich und wird sofort von {user_name} beschossen!",
            f"warpt zu {user_name} und stellt fest, dass der local komplett rot aufblobbt...",
            f"überrascht {user_name}, ahnt jedoch nicht, dass {user_name} in einem Titan sitzt 💣.",
            f"bemerkt, dass {user_name} beim Minern AFK ist. Als er näher kommt, zieht {user_name} blitzschnell ein Cyno.",
        ]

        # Erfolgreicher Raid
        if random_chance <= 25:
            # Überprüfen, ob der Benutzer genug Geld hat
            if baluser["wallet"] < amount:
                em.add_field(
                    name="",
                    value=f":rocket: {author} " + random.choice(ganktext) + "",
                    inline=False,
                )
                em.add_field(
                    name="",
                    value=f":rocket: {author} lootet das wrack und stellt fest das es leer ist...",
                    inline=False,
                )
                await ctx.respond(embed=em)
                return

            # Attempt to update both balances
            new_user_balance = baluser["wallet"] - amount
            new_author_balance = balauthor["wallet"] + amount

            sql_query = [
                f"UPDATE bank SET `wallet` = {new_user_balance} WHERE `user_id` = {user.id} AND `guild_id` = {server_id}",
                f"UPDATE bank SET `wallet` = {new_author_balance} WHERE `user_id` = {ctx.author.id} AND `guild_id` = {server_id}",
            ]
            sql_query = [query for query in sql_query if query is not None]

            bank = await db.executemany_sql(sql_query)

            if bank is False:
                await ctx.respond(
                    "Es ist ein Fehler aufgetreten bitte versuch es später erneut."
                )

            em.add_field(
                name="",
                value=f":rocket: {author} " + random.choice(ganktext) + "",
                inline=False,
            )
            em.add_field(
                name="",
                value=f":rocket: {author} hat {amount}:coin: erbeutet!",
                inline=False,
            )
            await ctx.respond(embed=em)
            return

        # Mißlungerner Raid
        if random_chance <= 70:
            # Überprüfen, ob der Benutzer genug Geld hat
            if balauthor["wallet"] < amount:
                em.add_field(
                    name="",
                    value=f":rocket: {author} du bist pleite... geh wieder arbeiten...",
                    inline=False,
                )
                await ctx.respond(embed=em)
                return

            # Attempt to update both balances
            new_user_balance = baluser["wallet"] + amount
            new_author_balance = balauthor["wallet"] - amount

            sql_query = [
                f"UPDATE bank SET `wallet` = {new_user_balance} WHERE `user_id` = {user.id} AND `guild_id` = {server_id}",
                f"UPDATE bank SET `wallet` = {new_author_balance} WHERE `user_id` = {ctx.author.id} AND `guild_id` = {server_id}",
            ]
            sql_query = [query for query in sql_query if query is not None]

            bank = await db.executemany_sql(sql_query)

            if bank is False:
                await ctx.respond(
                    "Es ist ein Fehler aufgetreten bitte versuch es später erneut."
                )

            em.add_field(
                name="",
                value=f":rocket: {author} " + random.choice(ganktext2) + "",
                inline=False,
            )
            em.add_field(
                name="",
                value=f":rocket: {author} hat {amount}:coin: verloren!",
                inline=False,
            )
            await ctx.respond(embed=em)
            return

        em.add_field(
            name="",
            value=f":rocket: {author} es tauchte ein Wurmloch auf und schickte dich in ein anderes System",
            inline=False,
        )
        await ctx.respond(embed=em)
        return

    @gank.error
    async def gank_cooldown(self, ctx, error):
        await application_cooldown(ctx, error)

    # ---------------------------- Listener ----------------------------
    # ---------------------------- Listener ----------------------------
    # ---------------------------- Listener ----------------------------

    # on guild leave
    # pylint: disable=duplicate-code
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        sql_daily = "INSERT INTO `daily` (`user_id`, `guild_id`, `user_name`) VALUES (:user_id, :guild_id, :user_name)"
        sql_working = "INSERT INTO `working` (`user_id`, `guild_id`, `user_name`) VALUES (:user_id, :guild_id, :user_name)"
        sql_raiding = "INSERT INTO `raiding` (`user_id`, `guild_id`, `user_name`) VALUES (:user_id, :guild_id, :user_name)"
        sql_mining = "INSERT INTO `mining` (`user_id`, `guild_id`, `user_name`) VALUES (:user_id, :guild_id, :user_name)"

        try:
            newmembers = []
            for member in guild.members:
                if not member.bot:
                    newmembers.append(
                        {
                            "user_id": member.id,
                            "guild_id": member.guild.id,
                            "user_name": str(member.display_name.capitalize()),
                        }
                    )
                else:
                    continue
            sql_query = [query for query in newmembers if query is not None]
            await db.executemany_var_sql(sql_daily, sql_query)
            await db.executemany_var_sql(sql_working, sql_query)
            await db.executemany_var_sql(sql_raiding, sql_query)
            await db.executemany_var_sql(sql_mining, sql_query)
            log_events.info("Create User - Economy - On Guild Join Completed")
        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"[Listener] On Guild Economy Join - {e}")
            return

    # on guild leave
    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        sql_daily = (
            "DELETE FROM `daily` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        )
        sql_working = "DELETE FROM `working` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        sql_raiding = "DELETE FROM `raiding` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        sql_mining = (
            "DELETE FROM `mining` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        )

        try:
            removemembers = []
            for member in guild.members:
                if not member.bot:
                    removemembers.append(
                        {"user_id": member.id, "guild_id": member.guild.id}
                    )
                else:
                    continue
            sql_query = [query for query in removemembers if query is not None]
            await db.executemany_var_sql(sql_daily, sql_query)
            await db.executemany_var_sql(sql_working, sql_query)
            await db.executemany_var_sql(sql_raiding, sql_query)
            await db.executemany_var_sql(sql_mining, sql_query)
            log_events.info("Remove User - Economy - On Guild Remove Completed")
        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"[Listener] On Guild Economy Remove - {e}")
            return
