import logging

import discord
from settings import db

log = logging.getLogger("db")


async def mainchannel(guild: discord.Guild):
    """Execute a database query to remove a channel from guild.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    guild: `discord.Guild`, optional
        The guild context in which the user field is being removed.
    """
    try:
        sql = "DELETE FROM `levelling_serverbase` WHERE `guild_id` = :guild_id"
        val = {"guild_id": guild.id}
        await db.execute_sql(sql, val)
        return True
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"[MainChannel] • {e}")
        return None
