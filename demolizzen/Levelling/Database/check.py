import logging

import discord
import Levelling.Database.add
import Levelling.Database.get
import Levelling.Database.insert
import Levelling.Database.set
from discord import File
from easy_pil import Editor, Font, load_image
from settings import db, functions
from settings.config import (
    LEVEL_UP_BACKGROUND,
    LEVEL_UP_BACKGROUND_SHADE,
    LEVEL_UP_BLUR,
    LEVEL_UP_PING,
    XP_PER_LEVEL,
)

log = logging.getLogger("db")


# pylint: disable=too-many-statements
async def levelup(user: discord.Member, guild: discord.Guild):
    """
    This function is called when a user levels up in a Discord server. It calculates the user's current level based on their experience points (XP), compares it to the previous level, and creates a notification to celebrate the level-up. The notification includes an image displaying the new level, the username, and the current XP values.

    Parameters:
        - user: discord.Member - The user who has leveled up.
        - guild: discord.Guild - The Discord server (Guild) where the user is located.

    How It Works:
    The function checks if the user and the server (Guild) are defined. Then, it calculates the user's current level based on their experience points (XP). If the level has increased, a level-up notification is created. This notification includes an image with the new level, the username, and the current XP values. The notification is sent to the server channel.

    The representation of the level-up image is done using image editing functions such as adding a background, profile picture, text, and shapes.

    Notes:
    - The function uses configuration variables like `XP_PER_LEVEL`, `LEVEL_UP_BACKGROUND`, `LEVEL_UP_BLUR`, etc., to customize the appearance of the level-up notification.
    - You can send the notification to a specific server channel by using the `mainChannel` function to retrieve the server's main channel.
    - If `level_up_ping` is set to `True`, the user is mentioned in the notification.

    """
    try:

        user_xp = await Levelling.Database.get.xp(user=user, guild=guild)
        lvl = 0

        while True:
            if user_xp < ((XP_PER_LEVEL / 2 * (lvl**2)) + (XP_PER_LEVEL / 2 * lvl)):
                break
            lvl += 1

        user_xp -= (XP_PER_LEVEL / 2 * ((lvl - 1) ** 2)) + (
            XP_PER_LEVEL / 2 * (lvl - 1)
        )
        if await Levelling.Database.get.level(user=user, guild=guild) != lvl:
            await Levelling.Database.set.level(user=user, guild=guild, amount=lvl)

            background_image = load_image(LEVEL_UP_BACKGROUND)
            background = (
                Editor(background_image).resize((900, 270)).blur(amount=LEVEL_UP_BLUR)
            )
            background_image2 = load_image(LEVEL_UP_BACKGROUND_SHADE)
            background2 = (
                Editor(background_image2).resize((900, 270)).blur(amount=LEVEL_UP_BLUR)
            )
            background.paste(background2, (0, 0))

            profile_image = load_image(str(user.display_avatar.url))
            profile = Editor(profile_image).resize((200, 200)).circle_image()

            poppins_big = Font.poppins(variant="bold", size=50)
            poppins_mediam = Font.poppins(variant="bold", size=40)
            poppins_regular = Font.poppins(variant="regular", size=30)

            border_image = load_image(
                await Levelling.Database.get.border(user=user, guild=guild)
            )
            border = Editor(border_image).resize((210, 210)).circle_image()
            background.paste(border, (40, 30))
            background.paste(profile, (45, 35))

            background.text(
                (600, 50),
                "LEVEL UP!",
                font=poppins_big,
                color="white",
                align="center",
                stroke_width=2,
                stroke_fill="black",
            )
            background.text(
                (600, 100),
                str(user.display_name.capitalize()),
                font=poppins_regular,
                color="white",
                align="center",
                stroke_width=2,
                stroke_fill="black",
            )
            background.text(
                (600, 150),
                f"LEVEL {lvl:,}",
                font=poppins_mediam,
                color="white",
                align="center",
                stroke_width=2,
                stroke_fill="black",
            )
            background.text(
                (600, 190),
                f"{functions.translate(user_xp)}/{functions.translate(int(XP_PER_LEVEL * 2 * ((1 / 2) * lvl)))} XP",
                font=poppins_regular,
                color="white",
                align="center",
                stroke_width=2,
                stroke_fill="black",
            )

            embed = discord.Embed()

            # Check if mention is enabled
            sql = f"SELECT `active` FROM `levelling_serverbase` WHERE guild_id = {guild.id}"
            status = await db.select(sql, single=True)

            if status == 0:
                return

            member = user
            if await Levelling.Database.get.mainchannel(guild=guild) is None:
                channel = guild.system_channel
            else:
                channel = discord.utils.get(
                    member.guild.channels,
                    name=await Levelling.Database.get.mainchannel(guild=member.guild),
                )
                if channel is None:
                    channel = guild.system_channel
            if channel is None:
                return
            if LEVEL_UP_PING is True:
                if channel.permissions_for(channel.guild.me).send_messages:
                    await channel.send(f"{user.mention},")
                else:
                    owner = channel.guild.owner
                    await owner.send(
                        f"Level System Permission Error on Server ***{channel.guild.name}*** - I'm not able to send messages to ***{channel.name}***, Please configure with /mc set or disable it with /mc banner"
                    )

            card = File(fp=background.image_bytes, filename="level_card.png")
            embed.set_image(url="attachment://level_card.png")
            if channel.permissions_for(channel.guild.me).send_messages:
                await channel.send(file=card, embed=embed)
    # pylint: disable=broad-exception-caught
    except Exception as e:
        log.error(f"[Level UP] • {e}", exc_info=True)
