import logging
import random

import discord
import Levelling.Database.add
import Levelling.Database.check
import Levelling.Database.get
import Levelling.Database.insert
import Levelling.Database.Leaderboard.leaderboard
import Levelling.Database.RankCard.rankcard
import Levelling.Database.remove
import Levelling.Database.set
from core import checks
from discord.commands import SlashCommandGroup
from discord.ext import commands
from settings import config, db
from settings.functions import application_cooldown

log = logging.getLogger("main")
log_events = logging.getLogger("events")


class Levelsystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.title = "Levelsystem"
        self.alias = "levelsystem"

    mc = SlashCommandGroup(
        "mc", "Levelsystem", contexts=[discord.InteractionContextType.guild]
    )

    async def check(self):
        """
        Perform a periodic check for guilds and members in the bot's presence.

        This method iterates through all the guilds the bot is a member of and performs
        several checks:
        - It checks if each guild exists in the database and adds it if not.
        - It checks if each non-bot member in a guild exists in the database and adds them if not.

        Notes
        -----
        - This method is designed to be executed periodically to ensure that the bot has up-to-date
          information about the guilds and members it is associated with.
        - It checks both the existence of guilds and individual members in the database, adding them
          if they are not found.
        - The checks are performed to ensure that guilds and members are properly tracked for
          features like leveling.
        """
        for guild in self.bot.guilds:
            guild_exist = await db.select_var(
                "SELECT * FROM levelling_serverbase where guild_id = :guild_id",
                {"guild_id": guild.id},
                single=True,
            )
            if guild_exist is None:
                sql = "INSERT INTO levelling_serverbase (guild_id, main_channel) VALUES (:guild_id, :main_channel)"
                await db.execute_sql(sql, {"guild_id": guild.id, "main_channel": None})
                log.info(f"[User-Check] Added Guild {guild.name} to Database.")
            for member in guild.members:
                if not member.bot:
                    result = await db.select_var(
                        "SELECT * FROM levelling WHERE user_id = %s AND guild_id = %s",
                        (member.id, guild.id),
                        single=True,
                    )
                    if result is None:
                        sql = "INSERT INTO levelling (guild_id, user_id, name, level, xp, background, xp_colour, blur, border) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
                        val = (
                            guild.id,
                            member.id,
                            str(member),
                            1,
                            0,
                            config.DEFAULT_BACKGROUND,
                            config.DEFAULT_XP_COLOUR,
                            0,
                            config.DEFAULT_BORDER,
                        )
                        await db.execute_sql(sql, val)
                        log.info(
                            f"[User-Check] Added Member {member.name} to Database."
                        )
                    else:
                        continue

    @mc.command()
    @checks.is_botmanager()
    async def set(self, ctx, channel: discord.TextChannel):
        """
        Set Main Channel for Bots Interaction
        """
        try:
            await Levelling.Database.set.mainchannel(guild=ctx.guild, channel=channel)
            embed = discord.Embed(
                description=f"🟢 **SUCCESS**: `📢 Main Channel set to: {await Levelling.Database.get.mainchannel(guild=ctx.guild)}`"
            )
            await ctx.respond(embed=embed)

        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"[MainChannel Set Command] • {e}", exc_info=True)
            embed = discord.Embed(
                description="🔴 **ERROR**: `Failed to set Main Channel`"
            )
            await ctx.respond(embed=embed)
            return

    @mc.command()
    @checks.is_botmanager()
    async def remove(self, ctx: discord.ApplicationContext):
        """
        Remove Main Channel for Bots Interaction
        """
        if await Levelling.Database.get.mainchannel(guild=ctx.guild) is None:
            embed = discord.Embed(
                description="🟡 **INFO**: `📢 Bot already react to all Channels`"
            )
            await ctx.respond(embed=embed)
            return
        try:
            remove = await Levelling.Database.remove.mainchannel(guild=ctx.guild)
            if not remove:
                embed = discord.Embed(
                    description="🔴 **ERROR**: `Incorrect Usage - /mc remove`"
                )
                await ctx.respond(embed=embed)
            embed = discord.Embed(
                description="🟢 **SUCCESS**: `📢 Bot react to all Channels`"
            )
            await ctx.respond(embed=embed)
        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"[MainChannel Remove Command] • {e}", exc_info=True)
            embed = discord.Embed(
                description="🔴 **ERROR**: `Failed to remove Main Channel`"
            )
            await ctx.respond(embed=embed)
            return

    @mc.command()
    @checks.is_botmanager()
    async def banner(self, ctx: discord.ApplicationContext, state: bool):
        """
        Activate/Deactivate Level UP Banner
        """
        try:
            sql = f"UPDATE levelling_serverbase SET `active` = {state} WHERE `guild_id` = {ctx.guild.id}"
            await db.execute_sql(sql)
            embed = discord.Embed(
                description=f"🟢 **SUCCESS**: `📢 Level UP Banner mention set to: {state}`"
            )
            await ctx.respond(embed=embed)
        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"[MainChannel Banner Command] • {e}", exc_info=True)
            embed = discord.Embed(
                description="🔴 **ERROR**: `Failed to set Level UP Banner mention`"
            )
            await ctx.respond(embed=embed)
            return

    # Leaderboard Command
    @commands.slash_command(dm_permission=False)
    @checks.is_in_channel()
    @commands.cooldown(
        3, 600, commands.BucketType.user
    )  # 10 Mal alle 10 Minuten pro Benutzer
    async def leaderboard(self, ctx: discord.ApplicationContext):
        """
        Get rank list from Server
        """
        await ctx.defer()

        try:
            await Levelling.Database.Leaderboard.leaderboard.leaderboard(
                self=self, ctx=ctx, guild=ctx.guild
            )
        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"[Leaderboard Command] • {e}", exc_info=True)

    @leaderboard.error
    async def command_cooldown(self, ctx: discord.ApplicationContext, error):
        await application_cooldown(ctx, error)

    # Rank Command
    @commands.slash_command(dm_permission=False)
    @checks.is_in_channel()
    @commands.cooldown(
        3, 600, commands.BucketType.user
    )  # 10 Mal alle 10 Minuten pro Benutzer
    async def rank(
        self, ctx: discord.ApplicationContext, member: discord.Member = None
    ):
        """
        Get your rank or another member's rank
        """
        await ctx.defer()
        try:
            rank = await Levelling.Database.RankCard.rankcard.generate(
                user=member, guild=ctx.guild
            )
            embed = discord.Embed()
            embed.set_image(url="attachment://rank_card.png")
            await ctx.respond(file=rank, embed=embed)
        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"[Rank Command] • {e}", exc_info=True)
            embed = discord.Embed(description=":x: **Error**: `User not Found`")
            await ctx.respond(embed=embed)

    @rank.error
    async def rank_cooldown(self, ctx: discord.ApplicationContext, error):
        await application_cooldown(ctx, error)

    # ---------------------------- Listener ----------------------------
    # ---------------------------- Listener ----------------------------
    # ---------------------------- Listener ----------------------------

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.wait_until_ready()
        if config.LOADER_TYPE.lower() == "startup":
            # pylint: disable=too-many-function-args
            await self.check(self)

    @commands.Cog.listener()
    async def on_message(self, ctx):
        if ctx.guild and not ctx.author.bot:
            try:
                if config.LOADER_TYPE.lower() == "message":
                    user_check = await Levelling.Database.get.xp(
                        user=ctx.author, guild=ctx.guild
                    )
                    if user_check == "User Not Found!":
                        log_events.info(
                            f"Create New User: {ctx.author.display_name.capitalize()}"
                        )
                        await Levelling.Database.insert.userfield(member=ctx.author)
                if config.XP_CHANCE is True:
                    chance_rate = config.XP_CHANCE_RATE
                    random_num = random.randint(1, chance_rate)
                    if random_num != chance_rate:
                        return

                xp_type = self.bot.config.XP_TYPE
                if xp_type.lower() == "normal":
                    to_add = config.XP_NORMAL_AMOUNT
                    await Levelling.Database.add.xp(
                        user=ctx.author, guild=ctx.guild, amount=to_add
                    )
                elif xp_type.lower() == "words":
                    # get the length of the message
                    res = len(ctx.content.split())
                    message_length = int(res)
                    await Levelling.Database.add.xp(
                        user=ctx.author, guild=ctx.guild, amount=message_length
                    )
                elif xp_type.lower() == "ranrange":
                    # get ranges from config
                    min_xp = config.XP_RANRANGE_MIN
                    max_xp = config.XP_RANRANGE_MAX
                    amount = random.randint(min_xp, max_xp)
                    await Levelling.Database.add.xp(
                        user=ctx.author, guild=ctx.guild, amount=amount
                    )
                await Levelling.Database.check.levelup(user=ctx.author, guild=ctx.guild)
            # pylint: disable=broad-except
            except Exception as e:
                log.error(f"Fehler bei On Message: {e}")

    # on guild join
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        log.info(f"Bot wurde von Server: {guild.id} - {guild.name} hinzugefügt.")
        try:
            sql = "REPLACE INTO levelling_serverbase (`guild_id`, `main_channel`) VALUES (:guild_id, :main_channel);"
            val = {"guild_id": guild.id, "main_channel": None}
            await db.execute_sql(sql, val)

            # For loop Execute
            newmembers = []
            query = "INSERT INTO `levelling` (`guild_id`, `user_name`, `user_id`, `level`, `xp`, `background`, `xp_colour`, `blur`, `border`) VALUES (:guild_id, :user_name, :user_id, :level, :xp, :background, :xp_colour, :blur, :border)"
            for member in guild.members:
                if not member.bot:
                    newmembers.append(
                        (
                            guild.id,
                            str(member.display_name.capitalize()),
                            member.id,
                            1,
                            0,
                            config.DEFAULT_BACKGROUND,
                            config.DEFAULT_XP_COLOUR,
                            0,
                            config.DEFAULT_BORDER,
                        )
                    )
                else:
                    continue
            sql_parameters = [query for query in newmembers if query is not None]
            await db.executemany_var_sql(query, sql_parameters)
            log_events.info("Create User - Levelsystem - On Guild Join Completed")
        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"[Listener] On Guild Join • {e}")
            return

    # on guild leave
    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        log.info(f"Bot wurde von Server: {guild.id} - {guild.name} entfernt.")
        try:
            removemembers = []
            query = "DELETE FROM `levelling` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
            for member in guild.members:
                if not member.bot:
                    removemembers.append((member.id, guild.id))
                else:
                    continue
            sql_parameters = [query for query in removemembers if query is not None]
            await db.executemany_var_sql(query, sql_parameters)
            log_events.info("Remove User - Levelsystem - On Guild Remove Completed")
        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"[Listener] On Guild Remove • {e}")
            return

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        try:
            channels = await Levelling.Database.get.mainchannel(guild=channel.guild)
            if channels:
                if channel.name in channels:
                    # get random channel in guild
                    channel = await channel.guild.fetch_channels()
                    channel = channel[0]
                    await Levelling.Database.set.mainchannel(
                        guild=channel.guild, channel=channel
                    )
                    return
        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"[Listener] On Guild Channel Remove • {e}")
            return
