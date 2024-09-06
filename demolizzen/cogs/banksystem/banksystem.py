import datetime as dt
import logging
from datetime import datetime

import discord
import pytz
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks
from settings import db
from settings.functions import application_cooldown

log = logging.getLogger("main")
log_test = logging.getLogger("testing")
log_events = logging.getLogger("events")

time = dt.time(hour=23)


class Bank(commands.Cog):
    """
    Save you money, Deposit it or Withdraw it watch out of other Players...
    """

    def __init__(self, bot):
        self.bot = bot
        self.last_update_time = datetime.now(pytz.UTC)
        self.title = "Banksystem"
        self.alias = "bank"
        self.earns = 0.01
        self.daily_update.start()

    def cog_unload(self):
        self.daily_update.cancel()

    bank = SlashCommandGroup(
        "bank", "Banksystem", contexts=[discord.InteractionContextType.guild]
    )

    # Täglicher Update-Task
    @tasks.loop(time=time)
    async def daily_update(self):
        await self.update_bank()
        self.last_update_time = datetime.now(pytz.UTC)

    @daily_update.before_loop
    async def before_daily_update(self):
        await self.bot.wait_until_ready()

    async def update_bank(self):
        log.debug("Daily Earn Ausgeführt")
        sql = f"UPDATE `bank` SET bank = bank + (bank * {self.earns});"
        await db.execute_sql(sql)

    async def db_connection(self, ctx):
        log.error("[Economy Work Command] DB Connection Problem")
        em = discord.Embed(
            color=discord.Color.red(),
            description="❌ Something went wrong, please try again later.",
        )
        await ctx.respond(embed=em, ephemeral=True, delete_after=10)
        return

    @bank.command()
    @commands.cooldown(
        5, 600, commands.BucketType.user
    )  # 5 Mal alle 10 Minuten pro Benutzer
    async def balance(self, ctx):
        """
        Check your money
        """
        # await ctx.defer()

        # Get Bank Data from User
        user = ctx.author
        user_id = ctx.author.id
        server_id = ctx.guild.id
        # SQL Check
        sql = (
            "SELECT * FROM `bank` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        )
        val = {"user_id": user_id, "guild_id": server_id}
        users = await db.select_var(sql, val, single=True, dictlist=True)

        if not users:
            users = await db.create_user(user, server_id, "bank")

        if users:
            wallet_amt = users["wallet"]
            bank_amt = users["bank"]
            em = discord.Embed(
                title="",
                color=discord.Color.dark_teal(),
                description=f"{ctx.author.mention}, You have\n",
            )
            em.add_field(
                name="Personal 💰", value=f"`🪙` **Wallet**: ${wallet_amt}", inline=True
            )
            em.add_field(
                name="Bank 🏦",
                value=f"`💵` **Balance:** ${bank_amt}\n `📈` **INTEREST:** 1%",
                inline=True,
            )
            await ctx.respond(embed=em)
        else:
            em = discord.Embed(
                title="",
                color=discord.Color.dark_teal(),
                description=f"{ctx.author.mention}, You don't own a Bank Account.",
            )
            await ctx.respond(embed=em)

    @balance.error
    async def balance_cooldown(self, ctx: discord.ApplicationContext, error):
        await application_cooldown(ctx, error)

    @bank.command()
    @commands.cooldown(
        5, 600, commands.BucketType.user
    )  # 5 Mal alle 10 Minuten pro Benutzer
    @option("amount", description="Specify the amount of Coins to Deposit")
    async def deposit(self, ctx, amount: int):
        """
        Deposit your money to the bank
        """
        # await ctx.defer()

        # Get Server-ID for further process
        server_id = ctx.guild.id

        sql = f"SELECT * FROM `bank` WHERE `user_id` = {ctx.author.id} AND `guild_id` = {server_id}"
        bal = await db.select(sql, single=True, dictlist=True)

        if bal:
            amount = int(amount)
            if amount > bal["wallet"]:
                await ctx.respond("You don't have that much money!")
                return
            if amount < 0:
                await ctx.respond("Amount must be positive!")
                return

            try:
                # Attempt to update both wallet and bank balances
                new_wallet_balance = bal["wallet"] - amount
                new_bank_balance = bal["bank"] + amount

                sql_query = [
                    f"UPDATE bank SET `wallet` = {new_wallet_balance} WHERE `user_id` = {ctx.author.id} AND `guild_id` = {server_id}",
                    f"UPDATE bank SET `bank` = {new_bank_balance} WHERE `user_id` = {ctx.author.id} AND `guild_id` = {server_id}",
                ]
                sql_query = [query for query in sql_query if query is not None]

                update = await db.executemany_sql(sql_query)
                if update is False:
                    await self.db_connection(ctx)
                    return
                await ctx.respond(f"You deposited {amount} :coin:!")
            # pylint: disable=broad-exception-caught
            except Exception as e:
                log.error(f"[Deposit] • {e}", exc_info=True)
                await ctx.respond(
                    "❌ Something went wrong, please try again later.", ephemeral=True
                )
                return
        else:
            await ctx.respond(
                "❌ Something went wrong, please try again later.", ephemeral=True
            )

    @deposit.error
    async def deposit_cooldown(self, ctx: discord.ApplicationContext, error):
        await application_cooldown(ctx, error)

    @bank.command()
    @commands.cooldown(
        5, 600, commands.BucketType.user
    )  # 5 Mal alle 10 Minuten pro Benutzer
    @option("amount", description="Specify the amount of Coins to Withdraw")
    async def withdraw(self, ctx, amount: int):
        """
        Withdraw your money from the bank
        """
        # await ctx.defer()

        # Get Server-ID for further process
        server_id = ctx.guild.id

        sql = f"SELECT * FROM `bank` WHERE `user_id` = {ctx.author.id} AND `guild_id` = {server_id}"
        bal = await db.select(sql, single=True, dictlist=True)

        if bal:
            amount = int(amount)
            if amount > bal["bank"]:
                await ctx.respond("You don't have that much money!")
                return
            if amount < 0:
                await ctx.respond("Amount must be positive!")
                return

            try:
                # Attempt to update both wallet and bank balances
                new_wallet_balance = bal["wallet"] + amount
                new_bank_balance = bal["bank"] - amount

                sql_query = [
                    f"UPDATE bank SET `wallet` = {new_wallet_balance} WHERE `user_id` = {ctx.author.id} AND `guild_id` = {server_id}",
                    f"UPDATE bank SET `bank` = {new_bank_balance} WHERE `user_id` = {ctx.author.id} AND `guild_id` = {server_id}",
                ]
                sql_query = [query for query in sql_query if query is not None]

                update = await db.executemany_sql(sql_query)
                if update is False:
                    await self.db_connection(ctx)
                    return
                await ctx.respond(f"You Withdraw {amount}:coin:!")
            # pylint: disable=broad-exception-caught
            except Exception as e:
                log.error(f"[Withdraw] • {e}", exc_info=True)
                await ctx.respond(
                    "❌ Something went wrong, please try again later.", ephemeral=True
                )
                return
        else:
            await ctx.respond(
                "❌ Something went wrong, please try again later.", ephemeral=True
            )

    @withdraw.error
    async def withdraw_cooldown(self, ctx: discord.ApplicationContext, error):
        await application_cooldown(ctx, error)

    @bank.command()
    @commands.cooldown(
        5, 600, commands.BucketType.user
    )  # 5 Mal alle 10 Minuten pro Benutzer
    @option("member", description="Choose Member")
    @option("amount", description="Specify the amount of Coins to Send")
    async def send(self, ctx, member: discord.Member, amount: int):
        """
        Send your money to a specific user
        """
        # await ctx.defer()

        # Get Server-ID for further process
        server_id = ctx.guild.id

        if member == ctx.author:
            await ctx.respond("You can't send to yourself...")
            return

        sql = f"SELECT * FROM `bank` WHERE `user_id` = {ctx.author.id} AND `guild_id` = {server_id}"
        bal = await db.select(sql, single=True, dictlist=True)

        sql = f"SELECT * FROM `bank` WHERE `user_id` = {member.id} AND `guild_id` = {server_id}"
        bal_member = await db.select(sql, single=True, dictlist=True)

        if bal and bal_member:
            amount = int(amount)
            if amount > bal["wallet"]:
                await ctx.respond("You don't have that much money!")
                return
            if amount < 0:
                await ctx.respond("Amount must be positive!")
                return
            try:
                # Attempt to update both wallet and bank balances
                new_wallet_balance = bal["wallet"] - amount
                new_member_wallet_balance = bal_member["wallet"] + amount

                sql_query = [
                    f"UPDATE bank SET `wallet` = {new_wallet_balance} WHERE `user_id` = {ctx.author.id} AND `guild_id` = {server_id}",
                    f"UPDATE bank SET `wallet` = {new_member_wallet_balance} WHERE `user_id` = {member.id} AND `guild_id` = {server_id}",
                ]
                sql_query = [query for query in sql_query if query is not None]

                update = await db.executemany_sql(sql_query)
                if update is False:
                    await self.db_connection(ctx)
                    return
                await ctx.respond(f"You gave {amount}:coin:! to {member.mention}")
            # pylint: disable=broad-exception-caught
            except Exception as e:
                log.error(f"[Send] • {e}", exc_info=True)
                await ctx.respond(
                    "❌ Something went wrong, please try again later.", ephemeral=True
                )
                return
        else:
            await ctx.respond("❌ Something went wrong, please try again later.")

    @send.error
    async def send_cooldown(self, ctx: discord.ApplicationContext, error):
        await application_cooldown(ctx, error)

    # ------------------------------ADMIN BEREICH----------------------------

    # on guild leave
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        try:
            query = "INSERT INTO `bank` (`user_id`, `guild_id`, `user_name`) VALUES (:user_id, :guild_id, :user_name)"
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
            await db.executemany_var_sql(query, sql_query)
            log_events.info("Create User - Bank - On Guild Join Completed")
        # pylint: disable=broad-exception-caught
        except Exception as e:
            log.error("[Listener] On Guild Bank Join - %s", e)
            return

    # on guild leave
    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        try:
            query = "DELETE FROM `bank` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
            removemembers = []
            for member in guild.members:
                if not member.bot:
                    removemembers.append(
                        {"user_id": member.id, "guild_id": member.guild.id}
                    )
                else:
                    continue
            sql_query = [query for query in removemembers if query is not None]
            await db.executemany_var_sql(query, sql_query)
            log_events.info("Remove User - Bank - On Guild Remove Completed")
        # pylint: disable=broad-exception-caught
        except Exception as e:
            log.error("[Listener] On Guild Bank Remove - %s", e)
            return
