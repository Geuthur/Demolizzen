# Standard Library
from io import BytesIO

# Third Party
import requests
from asgiref.sync import sync_to_async
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Discord
import discord

# Django
from django.db import transaction

# Demolizzen
from demolizzen import config
from demolizzen.config import (
    DEFAULT_BACKGROUND,
    DEFAULT_BORDER,
    DEFAULT_XP_COLOUR,
)
from demolizzen.core.bot import Demolizzen
from demolizzen.models import GuildProfile, UserProfile, UserSettings
from demolizzen.utils.functions import translate


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
        # Skip if no permission to send messages
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
                settings = await UserSettings.objects.aget(user=user_profile)
            except UserSettings.DoesNotExist:
                await UserSettings.objects.acreate(
                    user=user_profile,
                    background=DEFAULT_BACKGROUND,
                    border=DEFAULT_BORDER,
                    xp_colour=DEFAULT_XP_COLOUR,
                    blur=5,
                )
                settings = await UserSettings.objects.aget(user=user_profile)

            user_xp = user_profile.experience
            user_level = self.calculate_level(user_xp)
            user_xp -= self.calculate_xp_for_level(user_level)
            if user_profile.level != user_level:

                def sync_save():
                    with transaction.atomic():
                        user_profile.level = user_level
                        user_profile.save()

                await sync_to_async(sync_save)()

                # Deactivate Level Up Banner Posting
                if not guild_profile.mention:
                    return False

                background = self._render_level_up_background_with_settings(
                    settings, member
                )
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

    def _render_level_up_background_with_settings(
        self, settings, member: discord.Member
    ):
        """Get the level up background with user settings."""
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

        response = requests.get(str(member.display_avatar.url))
        profile = (
            Image.open(BytesIO(response.content)).convert("RGBA").resize((200, 200))
        )
        mask = Image.new("L", (200, 200), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, 200, 200), fill=255)
        profile.putalpha(mask)

        border_path = settings.border
        border = self.load_image_url_or_path(border_path).resize((210, 210))
        border_mask = Image.new("L", (210, 210), 0)
        draw = ImageDraw.Draw(border_mask)
        draw.ellipse((0, 0, 210, 210), fill=255)
        border.putalpha(border_mask)

        background.paste(border, (40, 30), border)
        background.paste(profile, (45, 35), profile)
        return background

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
