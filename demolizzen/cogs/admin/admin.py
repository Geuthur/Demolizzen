import datetime
import logging
import os
import pkgutil

import discord
from core import checks
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands
from settings import db

# Set Global Variable for Event Status
from settings.config import EVENTS_SERVER

log = logging.getLogger("main")
log_test = logging.getLogger("testing")


class Admin(commands.Cog):
    """
    Secure the Server with automated Moderation Tools
    """

    def __init__(self, bot):
        self.bot = bot
        self.title = "Admin"
        self.alias = "admin"
        self.command_ids = {}

    admin = SlashCommandGroup(
        "admin", "Adminsystem", contexts=[discord.InteractionContextType.guild]
    )
    mod = SlashCommandGroup(
        "moderation",
        "Moderation System",
        contexts=[discord.InteractionContextType.guild],
    )
    bank = admin.create_subgroup(
        "bank", contexts=[discord.InteractionContextType.guild]
    )
    economy = admin.create_subgroup(
        "economy", contexts=[discord.InteractionContextType.guild]
    )
    killmail = admin.create_subgroup(
        "killmail", contexts=[discord.InteractionContextType.guild]
    )

    # ---------------------------- Moderation ----------------------------
    # ---------------------------- Moderation ----------------------------
    # ---------------------------- Moderation ----------------------------

    @mod.command()
    @checks.is_mod()
    @option("limit", description="How many")
    async def clear(self, ctx: discord.ApplicationContext, limit: int):
        """
        Clear Message from a Channel
        """
        # await ctx.defer(ephemeral=True)

        if limit > 100:
            embed = discord.Embed(
                description="❌ No more than 100 messages can be purged at a time."
            )
            await ctx.respond(embed=embed, ephemeral=True, delete_after=20)
            return

        # Fetching the messages to delete
        # messages = await ctx.channel.history(limit=limit).flatten()
        # Fetching the messages to delete, only considering messages within the last 14 days
        try:
            messages = await ctx.channel.history(
                limit=limit,
                after=datetime.datetime.utcnow() - datetime.timedelta(days=14),
                oldest_first=False,
            ).flatten()
        except discord.HTTPException as e:
            if e.code == 50001:  # Messages are older than 14 days
                pass
                # embed = discord.Embed(description="❌ I have no permission to see that channel...")
            else:
                log.error(e, exc_info=True)
                embed = discord.Embed(description="❌ Something went wrong try later.")
            return False

        if messages:
            try:
                # Try bulk deleting the messages
                await ctx.channel.delete_messages(messages)
                embed = discord.Embed(
                    description=f"✅ Deleted {len(messages)} message(s) bulk delete."
                )
            except discord.HTTPException as e:
                if e.code == 50034:  # Messages are older than 14 days
                    embed = discord.Embed(
                        description="❌ You can only bulk delete messages that are under 14 days old."
                    )
                elif e.code == 50013:  # No Permission
                    embed = discord.Embed(
                        description="❌ I have no permission to do that..."
                    )
                else:
                    log.error(e, exc_info=True)
                    embed = discord.Embed(
                        description="❌ Something went wrong try later."
                    )
        else:
            embed = discord.Embed(
                description="❌ No messages older than 14 days to delete."
            )
        await ctx.respond(embed=embed, ephemeral=True, delete_after=10)

    @mod.command()
    @checks.is_mod()
    @option("user", description="Wähle User")
    @option("role", description="Wähle Rolle")
    async def role(
        self, ctx: discord.ApplicationContext, user: discord.Member, role: discord.Role
    ):
        """
        Give a Role to a User
        """

        if ctx.author.top_role.position < user.top_role.position:
            return await ctx.respond("Du kannst seine Rolle nicht ändern.")
        try:
            await user.add_roles(role)
            await ctx.respond(f"{role} an {user.mention} hinzugefügt!")
            return
        except discord.HTTPException as e:
            if e.code == 50013:  # No Permission
                embed = discord.Embed(
                    description="❌ I have no permission to do that..."
                )
            elif e.code == 50001:  # No Permission
                embed = discord.Embed(
                    description="❌ I have no permission to do that..."
                )
            else:
                log.error(e, exc_info=True)
                embed = discord.Embed(description="❌ Something went wrong try later.")
        await ctx.respond(embed=embed, ephemeral=True, delete_after=10)

    @mod.command()
    @checks.is_mod()
    @option("user", description="Wähle User")
    @option("derole", description="Wähle Rolle")
    async def derole(self, ctx, user: discord.Member, role: discord.Role):
        """
        Remove a Role to a User
        """

        if ctx.author.top_role.position < user.top_role.position:
            return await ctx.respond("Du kannst seine Rolle nicht ändern.")
        try:
            await user.remove_roles(role)
            await ctx.respond(f"{role} an {user.mention} entfernt!")
            return
        except discord.HTTPException as e:
            if e.code == 50013:  # No Permission
                embed = discord.Embed(
                    description="❌ I have no permission to do that..."
                )
            elif e.code == 50001:  # No Access
                embed = discord.Embed(
                    description="❌ I have no permission to do that..."
                )
            else:
                log.error(e, exc_info=True)
                embed = discord.Embed(description="❌ Something went wrong try later.")
        await ctx.respond(embed=embed, ephemeral=True, delete_after=10)

    # ---------------------------- Mission System ----------------------------
    # ---------------------------- Mission System ----------------------------
    # ---------------------------- Mission System ----------------------------

    @economy.command()
    @checks.is_botmanager()
    @option(
        "action",
        description="Start or Stop the Event for the Mining/Raid System",
        choices=["On", "Off", "Status"],
    )
    async def mode(self, ctx, action: str):
        """
        Start or Stop the Event for the Mining/Raid System
        """

        server_id = ctx.guild.id

        if server_id in EVENTS_SERVER:
            events, event_factor = EVENTS_SERVER[server_id]
        else:
            EVENTS_SERVER[server_id] = (False, 0)
            events, event_factor = EVENTS_SERVER[server_id]

        if action == "Status":
            if events:
                await ctx.respond(f"🟢 Event ist aktiv.\n Faktor: {event_factor}")
            else:
                await ctx.respond(f"🔴 Event ist nicht aktiv.\n Faktor: {event_factor}")

        if action == "On":
            EVENTS_SERVER[server_id] = (True, int(event_factor))
            await ctx.respond("🟢 Event wurde aktiviert.")
            return

        if action == "Off":
            EVENTS_SERVER[server_id] = (False, int(event_factor))
            await ctx.respond("🔴 Event wurde deaktiviert.")
            return

    @economy.command()
    @checks.is_botmanager()
    @option("amount", description="Multiply the Loan")
    async def set(self, ctx, amount: int):
        """
        Set the Event Faktor as Multiplier
        """
        server_id = ctx.guild.id

        EVENTS_SERVER[server_id] = (True, int(amount))
        await ctx.respond(
            f"🟢 Event wurde aktiviert und der Faktor auf x {amount} gesetzt."
        )
        return

    # ---------------------------- Extension ----------------------------
    # ---------------------------- Extension ----------------------------
    # ---------------------------- Extension ----------------------------

    @commands.slash_command()
    @checks.is_owner()
    @option("extension", description="Which extension should be unloaded?")
    async def unload(self, ctx, extension):
        """
        Unload a Extension
        """

        try:
            ctx.bot.unload_extension(f"Cogs.{extension.capitalize()}")
        # pylint: disable=broad-except
        except Exception:
            await ctx.respond("Could not unload cog")
            return
        await ctx.respond("Cog unloaded")

    @commands.slash_command()
    @checks.is_owner()
    @option("extension", description="Which extension should be load or reload?")
    async def load_cog(self, ctx: discord.ApplicationContext, extension):
        """
        Load or Reload a Extension
        """
        try:
            ext_dir = os.path.join(os.path.dirname(__file__), "..")
            ext_files = [name for _, name, _ in pkgutil.iter_modules([ext_dir])]

            if extension not in ext_files:
                await ctx.respond(f"{extension} extension not found.")
                return

            ext_name = f"Cogs.{extension}"
            was_loaded = ext_name in ctx.bot.extensions
            try:
                if was_loaded:
                    ctx.bot.reload_extension(ext_name)
                    await ctx.respond(f"{extension} extension reloaded.")
                else:
                    ctx.bot.load_extension(ext_name)
                    await ctx.respond(f"{extension} extension loaded.")
            # pylint: disable=broad-except
            except Exception:
                await ctx.respond(f"Exception on loading {extension}")
        # pylint: disable=broad-except
        except Exception:
            await ctx.respond(f"Exception on loading {extension}")

    # ---------------------------- Bank System ----------------------------
    # ---------------------------- Bank System ----------------------------
    # ---------------------------- Bank System ----------------------------

    @bank.command(name="give-money")
    @checks.is_botmanager()
    @option("member", description="Choose Member")
    @option("amount", description="Specify the amount of Coins to Give")
    async def give_money(
        self, ctx: discord.ApplicationContext, member: discord.Member, amount: int
    ):
        """
        Give money to a specific user
        """
        # Get Server-ID for further process
        server_id = ctx.guild_id

        amount = int(amount)
        if amount < 0:
            await ctx.respond("Amount must be positive!")
            return

        sql = (
            "SELECT * FROM `bank` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        )
        params = {"user_id": member.id, "guild_id": server_id}
        bal = await db.select_var(sql, params, single=True, dictlist=True)

        if bal is False:
            await ctx.respond(
                "Es ist ein Fehler aufgetreten versuche es später erneut."
            )

        if not bal:
            bal = await db.create_user(member, server_id, "bank")

        if bal:
            transfer = bal["wallet"] + amount
            sql = "UPDATE bank SET `wallet` = :wallet WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
            params = {"wallet": transfer, "user_id": member.id, "guild_id": server_id}
            bank = await db.execute_sql(sql, params)

            if bank:
                await ctx.respond(
                    f"You gave {amount}:coin:! to {member.mention}", delete_after=15
                )
                return
            log.error("Verbindung zur Datenbank konnte nicht hergestellt werden.")
            await ctx.respond(
                "Es scheint ein fehler aufgetreten zu sein. \nBitte versuch es erneut später."
            )
            return
        await ctx.respond("This User hasn't an Account", delete_after=10)

    @bank.command(name="remove-money")
    @checks.is_botmanager()
    @option("member", description="Choose Member")
    @option("amount", description="Specify the amount of Coins to Remove")
    @option("konto", description="Choose Account", choices=["wallet", "bank"])
    async def remove_money(self, ctx, member: discord.Member, amount: int, konto: str):
        """
        Remove money from a specific user
        """
        # Get Server-ID for further process
        server_id = ctx.guild.id

        if amount < 0:
            await ctx.respond("Amount must be positive!")
            return

        sql = f"SELECT * FROM `bank` WHERE `user_id` = {member.id} AND `guild_id` = {server_id}"
        bal = await db.select(sql, single=True, dictlist=True)

        if bal is False:
            await ctx.respond(
                "Es ist ein Fehler aufgetreten versuche es später erneut."
            )

        if bal:
            transfer = bal[konto] - amount
            if amount > bal[konto]:
                transfer = bal[konto] - bal[konto]
                amount = bal[konto]

            sql = f"UPDATE bank SET `{konto}` = {transfer} WHERE `user_id` = {member.id} AND `guild_id` = {server_id}"
            bank = await db.execute_sql(sql)

            if bank:
                await ctx.respond(
                    f"You Removed {amount}:coin:! to {member.mention}", delete_after=15
                )
                return
            log.error("Verbindung zur Datenbank konnte nicht hergestellt werden.")
            await ctx.respond(
                "Es scheint ein fehler aufgetreten zu sein. \nBitte versuch es erneut später."
            )
            return

        await ctx.respond("This User hasn't an Account", delete_after=10)

    @bank.command(name="remove-bank")
    @checks.is_botmanager()
    @option("member", description="Choose Member")
    async def reset_money(self, ctx, member: discord.Member):
        """
        Delete Bankaccount from Member
        """
        # await ctx.defer(ephemeral=True)

        # Get Server-ID for further process
        server_id = ctx.guild.id
        user_id = member.id
        sql_query = (
            "DELETE FROM `bank` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        )
        val = {"user_id": user_id, "guild_id": server_id}
        result = await db.execute_sql(sql_query, val)
        if result:
            await ctx.respond(f"You deleted {member.mention}", delete_after=10)
        else:
            log.error("Verbindung zur Datenbank konnte nicht hergestellt werden.")

    @bank.command(name="force-earns")
    @checks.is_owner()
    async def update_earns(self, ctx: discord.ApplicationContext):
        await self.update_bank()
        await ctx.respond("Tägliche Aktualisierung abgeschlossen.")

    async def update_bank(self):
        banksystem_cog = self.bot.get_cog("Bank")
        earns = banksystem_cog.earns

        sql = f"UPDATE `bank` SET bank = bank + (bank * {earns});"
        await db.execute_sql(sql)

    # ---------------------------- Bank System ----------------------------
    # ---------------------------- Bank System ----------------------------
    # ---------------------------- Bank System ----------------------------

    @killmail.command(name="analyze")
    @checks.is_owner()
    async def killmail_counter(self, ctx):
        """
        Owner Only - Bug Fixing
        """
        log_test.error("Char Names: %s", self.bot.esi_data._char_name_cache)
        log_test.error("System Names: %s", self.bot.esi_data._system_id_name_cache)
        log_test.error("Region Names: %s", self.bot.esi_data._region_id_cache)
        await ctx.respond("Daten gespeichert")
