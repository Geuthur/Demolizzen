# Standard Library
import random

# Discord
import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks
from discord.ext.pages import Paginator

# Demolizzen
from demolizzen import config
from demolizzen.cogs.levelsystem._functions import CheckLevelUp
from demolizzen.config import (
    DEFAULT_BACKGROUND,
    DEFAULT_BORDER,
    DEFAULT_XP_COLOUR,
    DISCORD_EMBED_COLOR_DANGER,
    DISCORD_EMBED_COLOR_SUCCESS,
)
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen
from demolizzen.models import GuildProfile, UserProfile, UserSettings
from demolizzen.utils.functions import application_cooldown, get_command_mention


class Levelsystem(commands.Cog):
    def __init__(self, bot: "Demolizzen"):
        self.bot = bot
        self.title = "Levelsystem"
        self.alias = "levelsystem"
        self.level = CheckLevelUp(bot)
        self.check_level_system.start()

    levelsystem = SlashCommandGroup(
        "levelsystem", "Levelsystem", contexts=[discord.InteractionContextType.guild]
    )

    levelsystem_config = SlashCommandGroup(
        "levelsystem_config",
        "Levelsystem Configuration",
        default_member_permissions=discord.Permissions(manage_guild=True),
        contexts=[discord.InteractionContextType.guild],
    )

    # Check for new Guild or Members every 2 Hours
    @tasks.loop(minutes=120)
    async def check_level_system(self):
        """Periodic check for guilds and members in the bot's presence."""
        await self.check()

    @check_level_system.before_loop
    async def before_check_level_system(self):
        await self.bot.wait_until_ready()
        self.bot.logger.info("Level System Checker Ready")

    def cog_unload(self):
        self.check_level_system.cancel()

    async def check(self):
        self.bot.logger.debug("Starting periodic check for guilds and members...")
        database_guilds = [obj.guild_id async for obj in GuildProfile.objects.all()]
        bot_guild_ids = [guild.id for guild in self.bot.guilds]
        missing_guilds = set(database_guilds) - set(bot_guild_ids)

        for guild in self.bot.guilds:
            try:
                guild_profile = await GuildProfile.objects.aget(guild_id=guild.id)
            except GuildProfile.DoesNotExist:
                # Create a new levelling server base if it doesn't exist
                guild_profile = await GuildProfile.objects.acreate(
                    guild_id=guild.id, guild_name=guild.name
                )
                self.bot.logger.info(f"Added Guild {guild.name} to Database.")
            for member in guild.members:
                if not member.bot:
                    try:
                        user_profile = await UserProfile.objects.aget(
                            user_id=member.id, guild=guild_profile
                        )
                    except UserProfile.DoesNotExist:
                        user_profile = await UserProfile.objects.acreate(
                            user_id=member.id,
                            guild=guild_profile,
                            user_name=member.display_name,
                        )
                        await UserSettings.objects.acreate(
                            user=user_profile,
                            background=DEFAULT_BACKGROUND,
                            border=DEFAULT_BORDER,
                            xp_colour=DEFAULT_XP_COLOUR,
                            blur=5,
                        )
                        self.bot.logger.info(f"Added Member {member.name} to Database.")

        for guild_id in missing_guilds:
            try:
                guild_profile = await GuildProfile.objects.aget(guild_id=guild_id)
                await guild_profile.adelete()
                self.bot.logger.info(f"Removed Guild ID {guild_id} from Database.")
            except GuildProfile.DoesNotExist:
                continue

    @levelsystem_config.command(
        name="set-mention", description="Activate/Deactivate Level UP Posting"
    )
    @checks.is_guild_manager()
    async def toggle(self, ctx: discord.ApplicationContext, state: bool):
        """
        Activate/Deactivate Level UP Posting
        """
        guild_profile = await GuildProfile.objects.aget(guild_id=ctx.guild.id)
        guild_profile.mention = state

        await guild_profile.asave()
        embed = discord.Embed(
            description=f"🟢 **SUCCESS**: `📢 Level UP Posting set to: {state}`"
        )
        await ctx.respond(embed=embed)

    # Leaderboard Command
    @commands.slash_command(dm_permission=False)
    @commands.cooldown(
        3, 600, commands.BucketType.user
    )  # 10 Mal alle 10 Minuten pro Benutzer
    async def leaderboard(self, ctx: discord.ApplicationContext):
        """
        Get rank list from Server
        """
        await ctx.defer()
        guild_users = [
            member
            async for member in UserProfile.objects.filter(
                guild_id=ctx.guild.id
            ).order_by("-level", "-experience")
        ]

        if not guild_users:
            embed = discord.Embed(
                description="❌ Aktuell ist die Liste nicht verfügbar"
            )
            return await ctx.respond(embed=embed)

        embed = discord.Embed(
            title=f":trophy: {ctx.guild}'s Leaderboard",
            colour=DISCORD_EMBED_COLOR_SUCCESS,
        )

        level = []
        pages = []
        data = []
        description = ""

        for user in guild_users:
            values = (
                user.user_name,
                user.level,
                user.experience,
            )  # A list with the three values from x
            data.append(values)

        for index, level in enumerate(data):
            description += (
                f"`{index + 1}.` {level[0]} `LEVEL:` {level[1]} `XP`: {level[2]}\n"
            )

            if (index + 1) % 10 == 0 or index == len(data) - 1:
                embed = discord.Embed(
                    title=f":trophy: {ctx.guild}'s Leaderboard",
                    description=description,
                    color=discord.Color.green(),
                )
                if ctx.guild.icon:
                    embed.set_thumbnail(url=ctx.guild.icon.url)
                pages.append(embed)
                description = ""

        paginator = Paginator(pages=pages, timeout=30, disable_on_timeout=True)
        return await paginator.respond(ctx.interaction)

    # Rank Command
    @commands.slash_command(dm_permission=False)
    @commands.cooldown(
        3, 600, commands.BucketType.user
    )  # 10 Mal alle 10 Minuten pro Benutzer
    async def rank(self, ctx: discord.ApplicationContext, member: discord.Member):
        """
        Get member's rank
        """
        await ctx.defer()

        user_profile = await UserProfile.objects.select_related("settings").aget(
            user_id=member.id, guild_id=ctx.guild.id
        )

        if not user_profile:
            embed = discord.Embed(
                description=f"❌ {member.display_name} is not registered in the leveling system."
            )
            return await ctx.respond(embed=embed)

        # Generate the rank card
        card = await self.level.generate_rank_card(
            user_profile=user_profile, member=member, guild=ctx.guild
        )
        embed = discord.Embed()
        embed.set_image(url="attachment://rank_card.png")
        if card is None:
            embed = discord.Embed(
                description="❌ Error generating rank card. Please try again later."
            )
            return await ctx.respond(embed=embed)
        return await ctx.respond(embed=embed, file=card)

    @rank.error
    async def rank_cooldown(self, ctx: discord.ApplicationContext, error):
        await application_cooldown(ctx, error)

    # ---------------------------- Listener ----------------------------
    # ---------------------------- Listener ----------------------------
    # ---------------------------- Listener ----------------------------

    @commands.Cog.listener()
    async def on_message(self, ctx: discord.Message):
        if ctx.guild and not ctx.author.bot:
            # Check if the Guild Profile exists
            try:
                guild_profile = await GuildProfile.objects.aget(guild_id=ctx.guild.id)
            except GuildProfile.DoesNotExist:
                guild_profile = await GuildProfile.objects.acreate(
                    guild_id=ctx.guild.id, guild_name=ctx.guild.name
                )
                self.bot.logger.info(
                    f"Create New Guild Profile {ctx.guild.name} to Database."
                )
            # Check if the User Profile exists
            try:
                user_profile = await UserProfile.objects.select_related(
                    "settings"
                ).aget(user_id=ctx.author.id, guild_id=ctx.guild.id)
            except UserProfile.DoesNotExist:
                user_profile = await UserProfile.objects.select_related(
                    "settings"
                ).acreate(
                    user_id=ctx.author.id,
                    user_name=ctx.author.global_name,
                    guild_id=ctx.guild.id,
                )
                self.bot.logger.info(
                    f"Create New User Profile: {ctx.author.display_name.capitalize()}"
                )
            try:
                if config.XP_CHANCE is True:
                    chance_rate = config.XP_CHANCE_RATE
                    random_num = random.randint(1, chance_rate)
                    if random_num != chance_rate:
                        return

                xp_type = self.bot.config.XP_TYPE
                if xp_type.lower() == "normal":
                    to_add = config.XP_NORMAL_AMOUNT
                    user_profile.experience += to_add
                elif xp_type.lower() == "words":
                    # get the length of the message
                    res = len(ctx.content.split())
                    message_length = int(res)
                    user_profile.experience += message_length
                elif xp_type.lower() == "ranrange":
                    # get ranges from config
                    min_xp = config.XP_RANRANGE_MIN
                    max_xp = config.XP_RANRANGE_MAX
                    amount = random.randint(min_xp, max_xp)
                    user_profile.experience += amount

                # Update User Name if changed
                if user_profile.user_name != ctx.author.display_name:
                    user_profile.user_name = ctx.author.display_name

                await user_profile.asave()
                # Check if the user leveled up
                await self.level.check_level_up(
                    user_profile=user_profile,
                    guild_profile=guild_profile,
                    member=ctx.author,
                    guild=ctx.guild,
                )
                return
            # pylint: disable=broad-except
            except Exception as e:
                self.bot.logger.error(f"Fehler bei On Message: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.TextChannel):
        try:
            guild_profile = await GuildProfile.objects.aget(guild_id=channel.guild.id)
            if guild_profile is not None:
                if channel.id == guild_profile.main_channel_id:
                    # Use system (default) channel if available, else pick first available text channel
                    new_channel = None
                    if (
                        channel.guild.system_channel
                        and channel.guild.system_channel.id != channel.id
                    ):
                        new_channel = channel.guild.system_channel
                    if not new_channel:
                        channels = [
                            ch
                            for ch in await channel.guild.fetch_channels()
                            if isinstance(ch, discord.TextChannel)
                            and ch.id != channel.id
                        ]
                        if channels:
                            new_channel = channels[0]
                    if new_channel:
                        guild_profile.main_channel_id = new_channel.id
                        # Try to resolve the command for mention
                        command_mention = get_command_mention(
                            self.bot,
                            cog="Guild",
                            slash_command="guild",
                            slash_command_group="set_channel",
                        )
                        embed = discord.Embed(
                            description=(
                                f"⛔CONFIG ERROR⛔: The main channel has been deleted, Use System Channel.\n"
                                f"If you want to change the main channel, use {command_mention}"
                            ),
                            color=DISCORD_EMBED_COLOR_DANGER,
                        )
                        await new_channel.send(embed=embed)
                        await guild_profile.asave()
                    return
        except GuildProfile.DoesNotExist:
            return
