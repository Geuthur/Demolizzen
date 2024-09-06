import logging

import discord
from settings import db
from settings.config import DEFAULT_BACKGROUND, DEFAULT_BORDER, DEFAULT_XP_COLOUR

log = logging.getLogger("db")


async def userfield(member: discord.Member):
    """Execute a database query to add a user.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    member: `discord.Member`
        The Discord member for whom the user field is being added.
    guild: `discord.Guild`, optional
        The guild context in which the user field is being added.
    """
    try:
        sql = "INSERT INTO `levelling` (`guild_id`, `user_name`, `user_id`, `level`, `xp`, `background`, `xp_colour`, `blur`, `border`) VALUES (:guild_id, :user_name, :user_id, :level, :xp, :background, :xp_colour, :blur, :border)"
        val = {
            "guild_id": member.guild.id,
            "user_name": str(member.display_name.capitalize()),
            "user_id": member.id,
            "level": 1,
            "xp": 0,
            "background": DEFAULT_BACKGROUND,
            "xp_colour": DEFAULT_XP_COLOUR,
            "blur": 5,
            "border": DEFAULT_BORDER,
        }
        await db.execute_sql(sql, val)
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"[UserField] • {e}")
        return None


async def mainchannel(guild: discord.Guild, channel: discord.TextChannel):
    """Execute a database query to add a channel to a guild.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    member: `discord.Member`
        The Discord member for whom the user field is being added.
    guild: `discord.Guild`
        The guild context in which the user field is being added.
    """
    try:
        sql = "INSERT INTO `levelling_serverbase` (`guild_id`, `main_channel`) VALUES (:guild_id, :main_channel)"
        val = {"guild_id": guild.id, "main_channel": channel.name}
        await db.execute_sql(sql, val)
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"[MainChannel] • {e}")
        return None
