import logging

import discord
import Levelling.Database.insert
from settings import db

log = logging.getLogger("db")


async def xp(user: discord.Member, guild: discord.Guild, amount):
    """Execute a database query to update a user's XP.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    user: `discord.Member`
        The Discord member for whom the XP is being updated.
    guild: `discord.Guild`
        The guild context in which the XP is being updated.
    amount: `int`
        The amount of XP to add or subtract.
    """
    try:
        sql = "SELECT `xp` FROM `levelling` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        val = {"user_id": user.id, "guild_id": guild.id}
        result = await db.select_var(sql, val)
        if result is None:
            log.info("User Not Found!")
            return
        # Addiere die XP
        newamount = result + amount
        sql = "UPDATE `levelling` SET `xp` = :xp WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        val = {"xp": newamount, "user_id": user.id, "guild_id": guild.id}
        await db.execute_sql(sql, val)
        return
    # pylint: disable=broad-except
    except Exception as e:
        log.error("Set [XP] - %s", e)
        return


async def level(user: discord.Member, guild: discord.Guild, amount):
    """Execute a database query to update a user's level.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    user: `discord.Member`, optional
        The Discord member for whom the Level is being updated.
    guild: `discord.Guild`, optional
        The guild context in which the Level is being updated.
    amount: `int`, optional
        The amount of Level to add or subtract.
    """
    try:
        # Überprüfe, ob der Benutzer in der MySQL-Datenbank existiert
        sql = "SELECT `level` FROM `levelling` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        val = {"user_id": user.id, "guild_id": guild.id}
        result = await db.select_var(sql, val)
        if result is None:
            log.info("User Not Found!")
            return

        # Addiere das Level
        sql = "UPDATE `levelling` SET `level` = :level WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        val = {"level": amount, "user_id": user.id, "guild_id": guild.id}
        await db.execute_sql(sql, val)
        return
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"[Level] • {e}")
        return


async def mainchannel(guild: discord.Guild, channel: discord.TextChannel):
    """Set the main channel for a guild in the database.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    guild: `discord.Guild`
        The guild for which the main channel is being set.
    channel: `discord.TextChannel`
        The text channel to set as the main channel.

    Returns
    -------
    bool
        True if the main channel was successfully set, False otherwise.
    """
    try:
        sql = "UPDATE `levelling_serverbase` SET `main_channel` = :main_channel WHERE `guild_id` = :guild_id"
        val = {"main_channel": channel.name, "guild_id": guild.id}
        mc = await db.execute_sql(sql, val)
        if mc == 0:
            await Levelling.Database.insert.mainchannel(guild=guild, channel=channel)
        return True
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"[MainChannel] • {e}")
        return
