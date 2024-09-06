import datetime
import logging
import math
import random
from datetime import timedelta

import discord
from settings import db

# Set Global Variable for Event Status
from settings.config import EVENTS_SERVER

from . import mission

log = logging.getLogger("main")
log_test = logging.getLogger("testing")


# TODO Atomic Cooldown
class CooldownManager:
    def __init__(self, server_id):
        self.server_id = server_id

    async def get_cooldown(self, ctx, c_type, last_cooldown):
        """
        Calculate and retrieve the remaining cooldown time for a specific action.

        This method calculates the remaining cooldown time for a specific action based on the
        action type, the user's last cooldown timestamp, and predefined cooldown times.
        It returns the remaining cooldown time as a formatted string.

        Parameters
        ----------
        ctx : discord.ext.commands.Context
            The context of the command that triggered the cooldown check.
        type : str
            The type of action for which the cooldown is being checked (e.g., "work", "daily").
        last_cooldown : str
            The timestamp of the user's last cooldown for the action.

        Returns
        -------
        str
            A formatted string representing the remaining cooldown time for the action.

        Notes
        -----
        - The `server_id` attribute should be set during class initialization to manage cooldowns
          for the correct server.
        - The `type` parameter should indicate the type of action for which the cooldown is being checked.
        - The `last_cooldown` parameter should be a string representing the user's last cooldown timestamp.

        """

        ship_cooldown = mission.ship_speed_var.get(c_type)

        if c_type == "work":
            ship_cooldown = 3600
        if c_type == "daily":
            ship_cooldown = 86400
        ids = [784546720935182357, 240850566002114561]

        timer = timedelta(seconds=ship_cooldown)
        # Can be removed cause its only for checking code
        if ctx.author.id in ids and ctx.guild.id == 518052275076464640:
            timer = timedelta(seconds=0)
        if ctx.author.id in ids and ctx.guild.id == 337275567487320064:
            timer = timedelta(seconds=0)
        # ----- Ende -----
        # Zeitfunktion
        last_cooldown_str = last_cooldown
        format_des_strings = "%Y-%m-%d %H:%M:%S.%f"
        if last_cooldown_str == "0":
            last_cooldown = datetime.datetime.now() - timedelta(seconds=14400)
            if c_type == "daily":
                last_cooldown = datetime.datetime.now() - timedelta(days=1)
        else:
            last_cooldown = datetime.datetime.strptime(
                last_cooldown_str, format_des_strings
            )
        now = datetime.datetime.now()
        delta = now - last_cooldown
        cooldown = timer - delta

        cooldown = str(cooldown).split(".", maxsplit=1)[0]

        # Setzen der Variablen in der anderen Klasse
        self.timer = timer
        self.delta = delta
        self.cooldown = cooldown


async def buy_system(user, item_name, server_id, table):
    """
    Attempt to buy a specific item from an in-game shop and update the user's data.

    This function allows a user to purchase a specific item from an in-game shop.
    It checks the availability of the item, the user's balance, and updates the
    user's data with the purchased item.

    Parameters
    ----------
    user : discord.Member
        The Discord member making the purchase.
    item_name : str
        The name of the item to be purchased.
    server_id : int
        The ID of the server where the purchase is being made.
    table : str
        The name of the table in the database where user data is stored.

    Returns
    -------
    list
        A list containing two elements:
        - A boolean value indicating whether the purchase was successful (True for success, False for failure).
        - An integer code indicating the result of the purchase operation (1 for item not found, 2 for user already owning the item, 3 for insufficient balance, 4 for a database error).
    """
    # Get User Data
    sql = "SELECT * FROM `eve_shop`"
    shop = await db.select(sql, dictlist=True)
    user_id = user.id

    # Suche nach dem Artikel in raidshop
    for item in shop:
        name = item["name"]
        category = item["shop"]
        if name == item_name and category == table:
            price = int(item["price"])
            insurance = int(item["insurance"])
            i_type = item["type"]
            break
    else:
        return [False, 1]  # Gegenstand nicht gefunden

    cost = price

    # Get User Data
    sql = f"SELECT * FROM `{table}` WHERE `user_id` = {user_id} AND `guild_id` = {server_id}"
    data = await db.select(sql, single=True, dictlist=True)

    # data = await get_data(user_id, server_id, table)
    if not data:
        data = await db.create_user(user, server_id, table)

    sql = (
        f"SELECT * FROM `bank` WHERE `user_id` = {user_id} AND `guild_id` = {server_id}"
    )
    bal = await db.select(sql, single=True, dictlist=True)

    wallet = int(bal["wallet"])

    sql_query = []

    if not bal or not data:
        return [False, 5]

    # Überprüfen, ob der Benutzer bereits denselben Gegenstand besitzt
    if item_name == data["schiff"]:
        return [False, 2]  # Benutzer besitzt bereits den Gegenstand

    # Überprüfen, ob der Benutzer genug Geld hat
    if wallet < cost:
        return [False, 3]  # Benutzer hat nicht genug Geld

    # Aktualisieren Sie die Daten des Benutzers, wenn der Kauf erfolgreich ist
    sql_query.append(
        f"UPDATE `{table}` SET `schiff` = '{item_name}', `insurance` = {insurance}, `type` = '{i_type}' WHERE `user_id` = {user_id} AND `guild_id` = {server_id}"
    )
    try:
        buy_balance = wallet - cost
        sql_query.append(
            f"UPDATE bank SET `wallet` = {buy_balance} WHERE `user_id` = {user_id} AND `guild_id` = {server_id}"
        )
        sql_query = [query for query in sql_query if query is not None]
        update = await db.executemany_sql(sql_query)
    except update.Error as e:
        print(f"Fehler bei der Verbindung zur Datenbank: {e}")
        return [False, 4]

    return [True, "Worked"]


class MissionComponent:
    def __init__(self, label, style=discord.ButtonStyle.gray):
        self.label = label
        self.id = id
        self.style = style


# pylint: disable=too-many-instance-attributes
class MissionEvent(discord.ui.View):
    def __init__(
        self, ctx, data=None, modus=None, story=None, schiff=None, components=None
    ):
        super().__init__(timeout=20, disable_on_timeout=True)
        if components is None:
            components = []
        self.components = self.format_components(components)
        self.create_views()

        # Ship Settings
        self._ship_chance = mission.ship_chance_var
        self._ship_speed = mission.ship_speed_var

        # Userdata
        self.data = data
        self.last_coin = int(data["loan"])
        self.insurance = int(data["insurance"])

        # Mode (Mining, Raiding)
        self.modus = modus
        self.bonus = False
        self.flee = False
        self.cyno = False
        self.finish = False

        # Text Adventure
        self.story = story
        self.bonus_text = mission.get_bonus_text(self.modus, self.story)
        self.docken_text = mission.get_docken_text(self.modus, self.story)
        self.system = mission.get_random_system()
        self.system2 = mission.get_random_system2()
        self.tackle_text = mission.get_tackle_text(self.modus, schiff)
        self.cyno_text = mission.get_cyno_text()
        self.flee_text = mission.get_flee_text()
        self.cyno_fail_text = mission.get_cyno_fail_text()
        self.flee_fail_text = mission.get_flee_fail_text()

        # Discord Data
        self.userid = ctx.user.id
        self.guildid = ctx.guild.id
        self.username = ctx.author.name.capitalize()
        self.ctx = ctx
        self.chance = random.randint(1, 100)

        # Event Data
        if self.guildid in EVENTS_SERVER:
            self.events, self.event_factor = EVENTS_SERVER[self.guildid]
        else:
            EVENTS_SERVER[self.guildid] = (False, 0)
            self.events, self.event_factor = EVENTS_SERVER[self.guildid]
        self.last_coin_event = None

    async def on_timeout(self):
        # Ship Success Chance
        ship_chance = self._ship_chance.get(self.data["type"])

        if not self.finish:
            await self.mission_trigger(self.ctx, ship_chance)

        return await super().on_timeout()

    def format_components(self, components):
        for i, component in enumerate(components):
            component.id = i
        return components

    def create_views(self):
        for component in self.components:
            self.add_button(
                f"{component.label}", f"label-{component.id}", component.style, False, 1
            )

    # Calculate Event Amount
    async def calc_event(self, last_coin):
        self.last_coin_event = last_coin
        self.last_coin = math.ceil(last_coin * self.event_factor)
        self.last_coin_event = self.last_coin - self.last_coin_event

    # Mission Bonus Trigger
    # pylint: disable=too-many-statements
    async def mission_trigger(
        self, interaction: discord.ApplicationContext, missionchance
    ):
        # Get Mining Data
        ship_coin_var = mission.generate_ship_coin_var()
        # Get User Data
        mining = ship_coin_var.get(self.data["type"])

        # Create Embed7
        em = discord.Embed(title="", color=discord.Color.teal(), description="")
        if self.modus == "mining":
            em.set_thumbnail(
                url="https://hell-rider.de/static/images/discord/evewin.gif"
            )
        elif self.modus == "raiding":
            em.set_thumbnail(
                url="https://hell-rider.de/static/images/discord/raidwin.gif"
            )

        if self.chance <= missionchance:
            # Bonus
            if self.bonus is True and self.chance <= 25:
                reportbonus = random.randrange(50, 100)
                # Set Bonus Amount
                self.last_coin += reportbonus

            # Event Bonus Coin
            if self.events:
                await self.calc_event(self.last_coin)

            # Update Mission_payout
            multiply = 1.0
            # Set Multiply if Bonus Trigger
            if self.bonus is True:
                multiply = 1.0 if self.chance <= 25 else 0.8
            mission_payout = round(self.last_coin * multiply)

            # Bot Response
            if self.bonus is True and self.chance <= 25:
                em.add_field(
                    name="",
                    value=f":rocket: {self.username}, 🌟**BONUS**🌟\n{self.bonus_text}",
                    inline=False,
                )
            if self.events:
                em.add_field(
                    name="",
                    value=f"🎉**EVENT DAY**🎉\nYou realize that there is still more in the cargo, and you receive additional **`{self.last_coin_event}`**:coin:",
                    inline=False,
                )
            if self.cyno:
                em.add_field(
                    name="",
                    value=f":rocket: {self.username},\n {self.cyno_text}",
                    inline=False,
                )
            if self.flee:
                em.add_field(
                    name="",
                    value=f":rocket: {self.username},\n {self.flee_text}\nAfter docking, you sell everything.\n\nYour earnings are**`{mission_payout}`** :coin:",
                    inline=False,
                )
            else:
                em.add_field(
                    name="",
                    value=f":rocket: {self.username},\n {self.docken_text} **`{mission_payout}`** :coin:",
                    inline=False,
                )
        else:
            # Set Pay Insurence
            if self.events:
                mission_payout = +0
            else:
                mission_payout = -self.insurance

            # Bot Response
            if self.flee:
                em.add_field(
                    name="",
                    value=f":rocket: {self.username},\n {self.flee_fail_text}",
                    inline=False,
                )
            elif self.cyno:
                em.add_field(
                    name="",
                    value=f":rocket: {self.username},\n {self.cyno_fail_text}",
                    inline=False,
                )
            else:
                em.add_field(
                    name="",
                    value=f":rocket: {self.username}, \n{self.tackle_text}",
                    inline=False,
                )
            if self.events:
                em.add_field(
                    name="",
                    value=f":rocket: {self.username}, \n🎉**Event Day**🎉 \nYou wake up in {self.system2} and realize that the ship you lost is already in the hangar.",
                    inline=False,
                )
            else:
                em.add_field(
                    name="",
                    value=f":rocket: {self.username}, \nYou wake up in {self.system2} and fit a new ship, having paid {abs(mission_payout)} :coin: for insurance!",
                    inline=False,
                )

        # Init User Bank Data
        sql = f"SELECT * FROM `bank` WHERE `user_id` = {self.userid} AND `guild_id` = {self.guildid}"
        userbank = await db.select(sql, single=True, dictlist=True)

        if userbank is None:
            userbank = await db.create_user(self.ctx.author, self.guildid, "bank")
        elif userbank is False:
            return False

        wallet = userbank["wallet"]
        chance = random.randint(1, 100)
        usercooldown = str(datetime.datetime.now())

        if self.last_coin != 0:
            wallet += mission_payout
            earn = wallet
            e_query = "UPDATE bank SET `wallet` = :earn WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
            e_params = {"earn": earn, "user_id": self.userid, "guild_id": self.guildid}
            await db.execute_sql(e_query, e_params)

        l_query = f"UPDATE {self.modus} SET `loan` = :loan, `chance` = :chance, `cooldown` = :cooldown WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        l_params = {
            "loan": mining,
            "chance": chance,
            "cooldown": f"{usercooldown}",
            "user_id": self.userid,
            "guild_id": self.guildid,
        }
        update = await db.execute_sql(l_query, l_params)

        if update is False:
            return False

        try:
            if isinstance(interaction, discord.Interaction):
                await interaction.response.send_message(embed=em)
            else:
                await interaction.send(embed=em)
        # pylint: disable=broad-except
        except Exception as e:
            log_test.error(f"Fehler bei Mission Trigger Interaction {e}", exc_info=True)

        return True

    def add_button(self, label, custom_id, style, disabled, row):

        button = discord.ui.Button(
            label=label, custom_id=custom_id, style=style, disabled=disabled, row=row
        )

        async def button_callback(interaction: discord.Interaction, button=button):
            # Check if the interaction is from the user who triggered the button
            if interaction.user.id != self.userid:
                await interaction.response.send_message(
                    "This interaction is not yours.", ephemeral=True
                )
                return

            if button.label == "Attack":
                self.bonus = True
                # Ship Success Chance
                ship_chance = self._ship_chance.get(self.data["type"])

                if await self.mission_trigger(interaction, ship_chance):
                    self.disable_all_items()
                    await interaction.message.edit(view=self)
                    self.finish = True
                return

            if button.label == "Warp Out":
                # Ship Success Chance
                ship_chance = self._ship_chance.get(self.data["type"])
                self.flee = True

                if await self.mission_trigger(interaction, ship_chance):
                    self.disable_all_items()
                    await interaction.message.edit(view=self)
                    self.finish = True
                return

            if button.label == "Cyno":
                # Ship Success Chance
                ship_chance = self._ship_chance.get(self.data["type"])
                self.cyno = True

                if await self.mission_trigger(interaction, ship_chance):
                    self.disable_all_items()
                    await interaction.message.edit(view=self)
                    self.finish = True
                return

            try:
                await interaction.message.edit(view=MissionEvent(self.components))
            # pylint: disable=broad-exception-caught
            except Exception:
                pass

        button.callback = button_callback
        self.add_item(button)
