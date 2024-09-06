import logging

import discord
from settings import db

log = logging.getLogger("db")


async def xp(user: discord.Member, guild: discord.Guild, amount):
    """Add XP to a user from the database.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    user: `discord.Member`
        The Discord member for whom the XP is being retrieved.
    guild: `discord.Guild`
        The guild context from which to retrieve the XP.
    amount: int
        The amount of XP to add to the user.

    Returns
    -------
    int or str
        The user's XP if found, or "User Not Found!" if the user is not found.
    """
    try:
        sql = f"SELECT `xp` FROM `levelling` WHERE `user_id` = {user.id} AND `guild_id` = {guild.id}"
        result = await db.select(sql)
        if result is None:
            log.info("User Not Found!")
            return
        # Addiere die XP
        sql = f"UPDATE `levelling` SET `xp` = xp + {amount} WHERE `user_id` = {user.id} AND `guild_id` = {guild.id}"
        await db.execute_sql(sql)
        return
    # pylint: disable=broad-except
    except Exception as e:
        log.error("Add [XP] - %s", e)
        return


async def level(user: discord.Member, guild: discord.Guild, amount):
    """Add Level to a user from the database.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    user: `discord.Member`, optional
        The Discord member for whom the Level is being retrieved.
    guild: `discord.Guild`, optional
        The guild context from which to retrieve the Level.
    amount: int, optional
        The amount of Level to add to the user.

    Returns
    -------
    int or str
        The user's Level if found, or "User Not Found!" if the user is not found.
    """
    try:
        # Überprüfe, ob der Benutzer in der MySQL-Datenbank existiert
        sql = f"SELECT `level` FROM `levelling` WHERE `user_id` = {user.id} AND `guild_id` = {guild.id}"
        val = (
            user.id,
            guild.id,
        )
        result = await db.select(sql)
        if result is None:
            log.info("User Not Found!")
            return
        # Addiere das Level
        sql = f"UPDATE `levelling` SET `level` = level + {amount} WHERE `user_id` = {user.id} AND `guild_id` = {guild.id}"
        # sql = "UPDATE `levelling` SET `level` = level + %s WHERE `user_id` = %s AND `guild_id` = %s"
        val = (
            amount,
            user.id,
            guild.id,
        )
        await db.execute_sql(sql, val)
        return
    # pylint: disable=broad-exception-caught
    except Exception as e:
        log.error(f"[Level] • {e}")
        return
