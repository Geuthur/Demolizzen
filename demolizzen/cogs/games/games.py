import logging
import random

import discord
from core import checks
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands
from settings import db
from settings.functions import application_cooldown

MAX_AMOUNT = 240

log = logging.getLogger("main")


class Games(commands.Cog):
    """
    Play games, but be careful not to gamble away everything.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.title = "Games"
        self.alias = "games"

    games = SlashCommandGroup(
        "games", "Gamesystem", contexts=[discord.InteractionContextType.guild]
    )

    @games.command()
    @commands.guild_only()
    @checks.is_in_channel()
    @commands.cooldown(
        5, 600, commands.BucketType.user
    )  # 5 Mal alle 10 Minuten pro Benutzer
    @option(
        "choose", description="Choose between", choices=["Rock", "Paper", "Scissors"]
    )
    async def rps(self, ctx, choose: str):
        """
        Play a game of Rock Paper Scissors
        """
        # await ctx.defer()

        bot_choices = ["Rock", "Paper", "Scissors"]
        bot_choice = random.choice(bot_choices)

        # Determine the winner
        # pylint: disable=too-many-boolean-expressions
        if choose == bot_choice:
            message = f"It's a draw! Both chose: {choose}"
        elif (
            (choose == "Rock" and bot_choice == "Scissors")
            or (choose == "Paper" and bot_choice == "Rock")
            or (choose == "Scissors" and bot_choice == "Paper")
        ):
            message = f"You win: {choose} vs {bot_choice}"
        else:
            message = f"You lose: {choose} vs {bot_choice}"

        await ctx.respond(message)

    @rps.error
    async def command_cooldown(self, ctx: discord.ApplicationContext, error):
        await application_cooldown(ctx, error)

    @games.command()
    @commands.guild_only()
    @checks.is_in_channel()
    @commands.cooldown(
        5, 600, commands.BucketType.user
    )  # 5 Mal alle 10 Minuten pro Benutzer
    @option(
        "amount", description="Specify the amount of Coins to bet in the slot machine."
    )
    async def slots(self, ctx: discord.ApplicationContext, amount: int):
        """
        Play a game of Slots with your bet of coins
        """
        # await ctx.defer()

        # Get Server-ID for further process
        server_id = ctx.guild.id

        try:
            sql = f"SELECT * FROM `bank` WHERE `user_id` = {ctx.author.id} AND `guild_id` = {server_id}"
            bal = await db.select(sql, single=True, dictlist=True)

            amount = int(amount)
            if amount > bal["wallet"]:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, You not have enough :coin:",
                )
                await ctx.respond(embed=em)
                return
            if amount < 0:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, The number must be positive",
                )
                await ctx.respond(embed=em)
                return
            if amount > MAX_AMOUNT:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, The limit is {MAX_AMOUNT} :coin:",
                )
                await ctx.respond(embed=em)
                return

            final = []
            for _ in range(3):
                a = random.choice([":red_circle:", ":yellow_circle:", ":blue_circle:"])

                final.append(a)

            await ctx.respond(str(final))

            if final[0] == final[0] and final[0] == final[1] and final[0] == final[2]:
                winamount = bal["wallet"] + (2 * amount)
                sql_query = f"UPDATE bank SET `wallet` = {winamount} WHERE `user_id` = {ctx.author.id} AND `guild_id` = {server_id}"
                update = await db.execute_sql(sql_query)

                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, You won! {3 * amount} :coin:",
                )
            else:
                looseamount = bal["wallet"] - amount
                sql_query = f"UPDATE bank SET `wallet` = {looseamount} WHERE `user_id` = {ctx.author.id} AND `guild_id` = {server_id}"
                update = await db.execute_sql(sql_query)

                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, You lose!",
                )

            # Error Handler if Database Transaction doesn't work
            if update is False:
                await ctx.respond("Something went wrong, please try again later.")
                return
            # Send Message
            await ctx.respond(embed=em)
        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"[Slots Command] • {e}", exc_info=True)
            await ctx.respond(
                "Something went wrong, please try again later", ephemeral=True
            )
            return

    @slots.error
    async def slots_cooldown(self, ctx: discord.ApplicationContext, error):
        await application_cooldown(ctx, error)

    @games.command()
    @commands.guild_only()
    @checks.is_in_channel()
    @commands.cooldown(
        5, 600, commands.BucketType.user
    )  # 5 Mal alle 10 Minuten pro Benutzer
    @option("amount", description="Specify the amount of Coins to dice.")
    async def dice(self, ctx, amount: int):
        """
        Play a game of Dice with your bet of coins
        """
        # await ctx.defer()

        # Get Server-ID for further process
        server_id = ctx.guild.id

        try:

            sql = f"SELECT * FROM `bank` WHERE `user_id` = {ctx.author.id} AND `guild_id` = {server_id}"
            bal = await db.select(sql, single=True, dictlist=True)

            amount = int(amount)
            if amount > bal["wallet"]:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, You not have enough :coin:",
                )
                await ctx.respond(embed=em)
                return
            if amount < 0:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, The number must be positive",
                )
                await ctx.respond(embed=em)
                return
            if amount > MAX_AMOUNT:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, The limit is {MAX_AMOUNT} :coin:",
                )
                await ctx.respond(embed=em)
                return

            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, gamble {amount} :coin: and throw the dice",
            )
            dice1 = random.randrange(1, 6)
            dice2 = random.randrange(1, 6)
            em.add_field(
                name="",
                value=f":game_die: {ctx.author.name}, You get {dice1} and {dice2}...",
                inline=False,
            )
            dice3 = random.randrange(1, 6)
            dice4 = random.randrange(1, 6)
            em.add_field(
                name="",
                value=f":game_die: {ctx.author.name}, He gets {dice3} and {dice4}...",
                inline=False,
            )
            if dice1 > dice3 and dice2 > dice4:
                winamount = bal["wallet"] + (2 * amount)
                sql_query = f"UPDATE bank SET `wallet` = {winamount} WHERE `user_id` = {ctx.author.id} AND `guild_id` = {server_id}"
                update = await db.execute_sql(sql_query)

                em.add_field(
                    name="",
                    value=f":game_die: {ctx.author.name}, You won {amount} :coin:",
                    inline=False,
                )
            else:
                looseamount = bal["wallet"] - amount
                sql_query = f"UPDATE bank SET `wallet` = {looseamount} WHERE `user_id` = {ctx.author.id} AND `guild_id` = {server_id}"
                update = await db.execute_sql(sql_query)

                em.add_field(
                    name="",
                    value=f":game_die: {ctx.author.name}, You lose {amount} :coin:",
                    inline=False,
                )

            # Error Handler if Database Transaction doesn't work
            if update is False:
                await ctx.respond("Something went wrong, please try again later.")
                return
            # Send Message
            await ctx.respond(embed=em)
        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"[Dice Command] • {e}", exc_info=True)
            await ctx.respond(
                "Something went wrong, please try again later.", ephemeral=True
            )
            return

    @dice.error
    async def dice_cooldown(self, ctx: discord.ApplicationContext, error):
        await application_cooldown(ctx, error)

    @games.command()
    @commands.guild_only()
    async def roll(self, ctx):
        """

        Play a game of Roll a number
        """
        n = random.randrange(1, 101)
        await ctx.respond(n)

    @games.command()
    @commands.guild_only()
    async def flipcoin(self, ctx):
        """
        Just flip a Coin
        """
        n = random.randint(0, 1)
        await ctx.respond("Heads" if n == 1 else "Tails")
