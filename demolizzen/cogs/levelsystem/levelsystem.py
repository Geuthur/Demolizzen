# Standard Library
import random
from io import BytesIO

# Third Party
import requests
from asgiref.sync import sync_to_async
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Discord
import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks
from discord.ext.pages import Paginator

# Django
from django.db import transaction

# Demolizzen
from demolizzen import config
from demolizzen.config import (
    DEFAULT_BACKGROUND,
    DEFAULT_BORDER,
    DEFAULT_XP_COLOUR,
    LEADERBOARD_EMBED_COLOUR,
)
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen
from demolizzen.models import GuildProfile, UserProfile, UserSettings
from demolizzen.utils.functions import application_cooldown, translate


class LeaderboardPaginator(Paginator):
    def __init__(self, pages, timeout):
        super().__init__(pages, timeout=timeout)

    async def on_timeout(self) -> None:
        if isinstance(self.message, discord.Interaction):
            await self.message.delete()
        else:
            await self.message.delete()


class CheckLevelUp:
    def __init__(self, bot: "Demolizzen"):
        self.bot = bot

    def calculate_level(self, xp: float) -> float:
        """Calculate the level based on the given XP."""
        level = 0
        while True:
            if xp < (
                (config.XP_PER_LEVEL / 2 * (level**2))
                + (config.XP_PER_LEVEL / 2 * level)
            ):
                break
            level += 1
        return level

    def calculate_xp_for_level(self, level: int) -> float:
        """Calculate the XP required for a specific level."""
        return (config.XP_PER_LEVEL / 2 * (level - 1) ** 2) + (
            config.XP_PER_LEVEL / 2 * (level - 1)
        )

    def _render_level_up_background(self, user: UserProfile, member: discord.Member):
        # Hintergrundbilder laden und bearbeiten (URL oder Pfad)
        background = self.load_image_url_or_path(config.LEVEL_UP_BACKGROUND).resize(
            (900, 270)
        )
        background = background.filter(
            ImageFilter.GaussianBlur(radius=config.LEVEL_UP_BLUR)
        )
        background2 = self.load_image_url_or_path(
            config.LEVEL_UP_BACKGROUND_SHADE
        ).resize((900, 270))
        background2 = background2.filter(
            ImageFilter.GaussianBlur(radius=config.LEVEL_UP_BLUR)
        )
        background.paste(background2, (0, 0), background2)

        # Profilbild laden und rund machen
        response = requests.get(str(member.display_avatar.url))
        profile = (
            Image.open(BytesIO(response.content)).convert("RGBA").resize((200, 200))
        )
        mask = Image.new("L", (200, 200), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, 200, 200), fill=255)
        profile.putalpha(mask)

        # Border laden und rund machen
        border_path = user.settings.border
        border = self.load_image_url_or_path(border_path).resize((210, 210))
        border_mask = Image.new("L", (210, 210), 0)
        draw = ImageDraw.Draw(border_mask)
        draw.ellipse((0, 0, 210, 210), fill=255)
        border.putalpha(border_mask)

        background.paste(border, (40, 30), border)
        background.paste(profile, (45, 35), profile)
        return background

    def _draw_level_up_text(
        self, background: Image, member: discord.Member, user_level: int, user_xp: int
    ):
        # Fonts laden (Pfad ggf. anpassen)
        poppins_big = ImageFont.load_default(size=70)
        poppins_mediam = ImageFont.load_default(size=50)
        poppins_regular = ImageFont.load_default(size=30)
        draw = ImageDraw.Draw(background)
        draw.text(
            (600, 50),
            "LEVEL UP!",
            font=poppins_big,
            fill="white",
            anchor="mm",
            stroke_width=2,
            stroke_fill="black",
        )
        draw.text(
            (600, 100),
            str(member.display_name.capitalize()),
            font=poppins_regular,
            fill="white",
            anchor="mm",
            stroke_width=2,
            stroke_fill="black",
        )
        draw.text(
            (600, 150),
            f"LEVEL {user_level:,}",
            font=poppins_mediam,
            fill="white",
            anchor="mm",
            stroke_width=2,
            stroke_fill="black",
        )
        draw.text(
            (600, 190),
            f"{translate(user_xp)}/{translate(int(config.XP_PER_LEVEL * 2 * ((1 / 2) * user_level)))} XP",
            font=poppins_regular,
            fill="white",
            anchor="mm",
            stroke_width=2,
            stroke_fill="black",
        )
        return background

    def _get_level_up_channel(
        self,
        guild_profile: GuildProfile,
        member: discord.Member,
        guild: discord.Guild,
    ):
        if guild_profile.main_channel is None:
            channel = guild.system_channel
        else:
            channel = discord.utils.get(
                member.guild.channels, name=guild_profile.main_channel
            )
            if channel is None:
                channel = guild.system_channel
                if channel is None:
                    return None
        return channel

    async def _send_level_up_card(
        self,
        channel: discord.TextChannel,
        member: discord.Member,
        img_bytes: BytesIO,
        embed: discord.Embed,
    ):
        if channel.permissions_for(channel.guild.me).send_messages:
            card = discord.File(fp=img_bytes, filename="level_card.png")
            embed.set_image(url="attachment://level_card.png")
            content = ""
            if config.LEVEL_UP_PING is True:
                content = f"{member.mention},"
            await channel.send(file=card, embed=embed, content=content)
            return True
        # If bot cannot send messages, notify the owner
        owner = channel.guild.owner
        await owner.send(
            f"Level System Permission Error on Server ***{channel.guild.name}*** - I'm not able to send messages to ***{channel.name}***, Please configure with /mc set or disable it with /mc banner"
        )
        return False

    def load_image_url_or_path(self, path_or_url):
        if str(path_or_url).startswith("http://") or str(path_or_url).startswith(
            "https://"
        ):
            response = requests.get(path_or_url)
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert("RGBA")
        return Image.open(path_or_url).convert("RGBA")

    async def check_level_up(
        self,
        user_profile: UserProfile,
        guild_profile: GuildProfile,
        member: discord.Member,
        guild: discord.Guild,
    ):
        """Check if a user has leveled up and generate a rank card if so."""
        try:
            if not user_profile or not guild_profile:
                return
            try:
                assert user_profile.settings
            except UserSettings.DoesNotExist:
                await UserSettings.objects.acreate(
                    user=user_profile,
                    background=DEFAULT_BACKGROUND,
                    border=DEFAULT_BORDER,
                    xp_colour=DEFAULT_XP_COLOUR,
                    blur=5,
                )
                # Reload user_profile to get the new settings
                user_profile = await UserProfile.objects.select_related(
                    "settings"
                ).aget(user_id=member.id, guild_id=guild.id)

            user_xp = user_profile.experience
            user_level = self.calculate_level(user_xp)
            user_xp -= self.calculate_xp_for_level(user_level)
            if user_profile.level != user_level:

                def sync_save():
                    with transaction.atomic():
                        user_profile.level = user_level
                        user_profile.save()

                await sync_to_async(sync_save)()

                # Check if Guild mentions are enabled
                if not guild_profile.mention:
                    return False

                background = self._render_level_up_background(user_profile, member)
                background = self._draw_level_up_text(
                    background, member, user_level, user_xp
                )

                img_bytes = BytesIO()
                background.save(img_bytes, format="PNG")
                img_bytes.seek(0)
                embed = discord.Embed()
                channel = self._get_level_up_channel(
                    guild_profile=guild_profile, member=member, guild=guild
                )
                if channel is None:
                    return False
                return await self._send_level_up_card(channel, member, img_bytes, embed)
            return False
        except Exception as e:  # pylint: disable=broad-except
            self.bot.logger.error(f"Error checking level up: {e}", exc_info=True)

    # pylint: disable=too-many-statements
    async def generate_rank_card(
        self, user_profile: UserProfile, member: discord.Member, guild: discord.Guild
    ):
        """Generate a rank card for a user in a guild."""
        try:
            assert user_profile.settings
        except UserSettings.DoesNotExist:
            await UserSettings.objects.acreate(
                user=user_profile,
                background=DEFAULT_BACKGROUND,
                border=DEFAULT_BORDER,
                xp_colour=DEFAULT_XP_COLOUR,
                blur=5,
            )
            # Reload user_profile to get the new settings
            user_profile = await UserProfile.objects.select_related("settings").aget(
                user_id=member.id, guild_id=guild.id
            )

        xp = user_profile.experience
        level = self.calculate_level(xp)
        xp -= self.calculate_xp_for_level(level)
        next_level_xp = int(config.XP_PER_LEVEL * 2 * ((1 / 2) * level))
        percentage = int((xp / next_level_xp) * 100)

        # Hintergrund laden und bearbeiten
        if str(user_profile.settings.background).startswith("http"):
            response = requests.get(str(user_profile.settings.background))
            background_image = Image.open(BytesIO(response.content)).convert("RGBA")
        else:
            background_image = Image.open(
                str(user_profile.settings.background)
            ).convert("RGBA")
        background = background_image.resize((1050, 300))
        if int(user_profile.settings.blur) > 0:
            background = background.filter(
                ImageFilter.GaussianBlur(radius=int(user_profile.settings.blur))
            )

        # Profilbild laden und bearbeiten
        response = requests.get(member.display_avatar.url)
        profile_image = Image.open(BytesIO(response.content)).convert("RGBA")
        profile = profile_image.resize((200, 210))
        # Border laden und bearbeiten
        if str(user_profile.settings.border).startswith("http"):
            response = requests.get(str(user_profile.settings.border))
            border_image = Image.open(BytesIO(response.content)).convert("RGBA")
        else:
            border_image = Image.open(str(user_profile.settings.border)).convert("RGBA")
        border = border_image.resize((210, 220))

        # Fonts laden (Pfad ggf. anpassen)
        font_25 = ImageFont.load_default(size=25)  # Normal font for level and XP
        font_40_bold = ImageFont.load_default(size=40)  # Bold font for rank
        font_60_bold = ImageFont.load_default(size=60)  # Bold font for name

        # Border und Profilbild einfügen
        background.paste(border, (30, 40), border)
        background.paste(profile, (35, 45), profile)

        draw = ImageDraw.Draw(background)

        # Text zeichnen
        if config.NAME_COLOUR is True:
            draw.text(
                (260, 40),
                f"{member.name.capitalize()}",
                font=font_60_bold,
                fill=user_profile.settings.xp_colour,
                stroke_fill="black",
                stroke_width=1,
            )
            draw.text(
                (700, 40),
                f"EXP: {translate(user_profile.experience)}",
                font=font_60_bold,
                fill=user_profile.settings.xp_colour,
                stroke_fill="black",
                stroke_width=1,
            )
            draw.text(
                (270, 150),
                f"Level: {level:,}",
                font=font_25,
                fill=user_profile.settings.xp_colour,
            )
        else:
            draw.text(
                (250, 40), f"{member.display_name}", font=font_60_bold, fill="white"
            )
            draw.text(
                (870, 190),
                f"#{user_profile.get_users_rank(member.id, guild.id):,}",
                font=font_40_bold,
                fill="white",
                stroke_fill="black",
                stroke_width=1,
            )
            draw.text((270, 150), f"Level: {level:,}", font=font_25, fill="white")

        # Rechteck (XP-Bar-Hintergrund)
        bar_x, bar_y, bar_w, bar_h, bar_r = 260, 190, 600, 40, 20
        # Hintergrund der Bar (dunkel)
        draw.rounded_rectangle(
            (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h),
            radius=bar_r,
            fill=(40, 40, 40, 180),
        )
        # XP-Bar (farbig)
        if percentage > 5:
            fill_w = int(bar_w * (percentage / 100))
            draw.rounded_rectangle(
                (bar_x, bar_y, bar_x + fill_w, bar_y + bar_h),
                radius=bar_r,
                fill=user_profile.settings.xp_colour,
            )

        # XP-Text rechts
        draw.text(
            (845, 145),
            f"Remaining: {translate(xp)} / {translate(next_level_xp)}",
            font=font_25,
            fill="white",
            anchor="ra",
            stroke_fill="black",
            stroke_width=1,
        )

        # Bild in Bytes speichern und als Discord-File zurückgeben
        output = BytesIO()
        background.save(output, format="PNG")
        output.seek(0)
        card = discord.File(fp=output, filename="rank_card.png")

        return card


class Levelsystem(commands.Cog):
    def __init__(self, bot: "Demolizzen"):
        self.bot = bot
        self.title = "Levelsystem"
        self.alias = "levelsystem"
        self.level = CheckLevelUp(bot)
        self.check_level_system.start()

    mc = SlashCommandGroup(
        "mc", "Levelsystem", contexts=[discord.InteractionContextType.guild]
    )

    # Update Shop every 2 Hours
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

    @mc.command()
    @checks.is_botmanager()
    async def set(self, ctx: discord.ApplicationContext, channel: discord.TextChannel):
        """
        Set Main Channel for Bots Interaction
        """
        guild_profile = await GuildProfile.objects.aget(guild_id=ctx.guild.id)
        guild_profile.main_channel = channel.id
        await guild_profile.asave()
        embed = discord.Embed(
            description=f"🟢 **SUCCESS**: `📢 Main Channel set to: {guild_profile.main_channel}`"
        )
        return await ctx.respond(embed=embed)

    @mc.command()
    @checks.is_botmanager()
    async def remove(self, ctx: discord.ApplicationContext):
        """
        Remove Main Channel for Bots Interaction
        """
        guild_profile = await GuildProfile.objects.aget(guild_id=ctx.guild.id)

        if guild_profile.main_channel is None:
            embed = discord.Embed(
                description="🟡 **INFO**: `📢 Bot already react to all Channels`"
            )
            await ctx.respond(embed=embed)
            return

        # Remove all channels from the levelling server base
        guild_profile.main_channel = None
        await guild_profile.asave()
        embed = discord.Embed(
            description="🟢 **SUCCESS**: `📢 Bot react to all Channels`"
        )
        await ctx.respond(embed=embed)

    @mc.command()
    @checks.is_botmanager()
    async def banner(self, ctx: discord.ApplicationContext, state: bool):
        """
        Activate/Deactivate Level UP Banner
        """
        guild_profile = await GuildProfile.objects.aget(guild_id=ctx.guild.id)
        guild_profile.mention = state

        await guild_profile.asave()
        embed = discord.Embed(
            description=f"🟢 **SUCCESS**: `📢 Level UP Banner mention set to: {state}`"
        )
        await ctx.respond(embed=embed)

    # Leaderboard Command
    @commands.slash_command(dm_permission=False)
    @checks.is_in_channel()
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
            title=f":trophy: {ctx.guild}'s Leaderboard", colour=LEADERBOARD_EMBED_COLOUR
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

        paginator = LeaderboardPaginator(pages=pages, timeout=60)
        return await paginator.respond(ctx.interaction)

    # Rank Command
    @commands.slash_command(dm_permission=False)
    @checks.is_in_channel()
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
    async def on_ready(self):
        await self.bot.wait_until_ready()
        if config.LOADER_TYPE.lower() == "startup":
            # pylint: disable=too-many-function-args
            await self.check(self)

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

    # on guild join
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        # Check if levelling server base exists
        try:
            guild_profile = await GuildProfile.objects.aget(guild_id=guild.id)
            if guild_profile:
                self.bot.logger.debug(
                    f"Levelling Serverbase for {guild.name} already exists, skipping creation."
                )
                return
        except GuildProfile.DoesNotExist:
            # Create levelling server base
            guild_profile = await GuildProfile.objects.acreate(
                guild_id=guild.id, guild_name=guild.name
            )

            # Create levelling records for all members
            member_ids = [member.id for member in guild.members if not member.bot]
            existing_ids = await UserProfile.objects.filter(
                user_id__in=member_ids, guild_id=guild.id
            ).values_list("user_id", flat=True)

            new_members = [
                member
                for member in guild.members
                if member.id not in existing_ids and not member.bot
            ]
            new_user_profiles = []
            new_settings = []
            for member in new_members:
                new_user_profiles.append(
                    UserProfile(
                        user_id=member.id, guild_id=guild.id, user_name=member.name
                    )
                )
                new_settings.append(
                    UserSettings(user_id=member.id, user__guild_id=guild.id)
                )
            if new_user_profiles:
                await UserProfile.objects.abulk_create(new_user_profiles)
            if new_settings:
                await UserSettings.objects.abulk_create(new_settings)
        self.bot.logger.info(
            f"Levelling records for {guild.name} created successfully."
        )

    # on guild leave
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        # Delete levelling records for all members
        try:
            guild_profile = await GuildProfile.objects.aget(guild_id=guild.id)
            if guild_profile is not None:
                await guild_profile.adelete()
                self.bot.logger.info(
                    f"Levelling records for guild {guild.name} ({guild.id}) deleted successfully."
                )
        except GuildProfile.DoesNotExist:
            self.bot.logger.debug(
                f"Levelling records for guild {guild.name} ({guild.id}) do not exist."
            )
            return

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.TextChannel):
        try:
            guild_profile = await GuildProfile.objects.aget(guild_id=channel.guild.id)
            if guild_profile is not None:
                if channel.name == guild_profile.main_channel:
                    # get random channel in guild
                    channels = await channel.guild.fetch_channels()
                    new_channel = channels[0]
                    guild_profile.main_channel = new_channel.id
                    self.bot.logger.info(
                        f"Main channel for {channel.guild.name} set to {new_channel.name}"
                    )
                    await guild_profile.asave()
                    return
        except GuildProfile.DoesNotExist:
            return
