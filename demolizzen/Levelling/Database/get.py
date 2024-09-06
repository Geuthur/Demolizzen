import logging

import discord
from settings import db

log = logging.getLogger("db")


async def xp(user: discord.Member, guild: discord.Guild):
    """Retrieve a user's XP from the database.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    user: `discord.Member`
        The Discord member for whom the XP is being retrieved.
    guild: `discord.Guild`
        The guild context from which to retrieve the XP.

    Returns
    -------
    int or str
        The user's XP if found, or "User Not Found!" if the user is not found.
    """
    try:
        sql = "SELECT `xp` FROM `levelling` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        val = {"user_id": user.id, "guild_id": guild.id}

        result = await db.select_var(sql, val, single=True)
        if result is None:
            return "User Not Found!"
        return result
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"[XP] • {e}")
        return


async def level(user: discord.Member, guild: discord.Guild):
    """Retrieve a user's level from the database.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    user: `discord.Member`
        The Discord member for whom the level is being retrieved.
    guild: `discord.Guild`
        The guild context from which to retrieve the level.

    Returns
    -------
    int or None
        The user's level if found, or None if the user is not found.
    """
    try:
        # Überprüfe, ob der Benutzer in der MySQL-Datenbank existiert
        sql = "SELECT `level` FROM `levelling` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        val = {"user_id": user.id, "guild_id": guild.id}
        result = await db.select_var(sql, val, single=True)
        if result is None:
            log.info("User not Found")
            return
        return result
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"[Level] • {e}")
        return


async def background(user: discord.Member, guild: discord.Guild):
    """Retrieve a user's background from the database.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    user: `discord.Member`
        The Discord member for whom the background is being retrieved.
    guild: `discord.Guild`
        The guild context from which to retrieve the background.

    Returns
    -------
    str or None
        The user's background if found, or None if the user is not found.
    """
    try:
        # Überprüfe, ob der Benutzer in der MySQL-Datenbank existiert
        sql = "SELECT `background` FROM `levelling` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        val = {"user_id": user.id, "guild_id": guild.id}
        result = await db.select_var(sql, val, single=True)
        if result is None:
            log.info("User not Found")
            return None
        return result
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"[Background] • {e}")
        return


async def border(user: discord.Member = None, guild: discord.Guild = None):
    """Retrieve a user's border from the database.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    user: `discord.Member`, optional
        The Discord member for whom the border is being retrieved.
    guild: `discord.Guild`, optional
        The guild context from which to retrieve the border.

    Returns
    -------
    int or None
        The user's border if found, or None if the user is not found.
    """
    try:
        # Überprüfe, ob der Benutzer in der MySQL-Datenbank existiert
        sql = "SELECT `border` FROM `levelling` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        val = {"user_id": user.id, "guild_id": guild.id}
        result = await db.select_var(sql, val, single=True)

        if result is None:
            log.info("User not Found")
            return None
        return result
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"[Border] • {e}")
        return


async def colour(user: discord.Member = None, guild: discord.Guild = None):
    """Retrieve a user's colour from the database.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    user: `discord.Member`, optional
        The Discord member for whom the colour is being retrieved.
    guild: `discord.Guild`, optional
        The guild context from which to retrieve the colour.

    Returns
    -------
    int or None
        The user's colour if found, or None if the user is not found.
    """
    try:
        # Überprüfe, ob der Benutzer in der MySQL-Datenbank existiert
        sql = "SELECT `xp_colour` FROM `levelling` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        val = {"user_id": user.id, "guild_id": guild.id}
        result = await db.select_var(sql, val, single=True)
        if result is None:
            log.info("User not Found")
            return
        return result
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"[Colour] • {e}")
        return


async def blur(user: discord.Member = None, guild: discord.Guild = None):
    """Retrieve a user's blur from the database.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    user: `discord.Member`, optional
        The Discord member for whom the blur is being retrieved.
    guild: `discord.Guild`, optional
        The guild context from which to retrieve the blur.

    Returns
    -------
    int or None
        The user's blur if found, or None if the user is not found.
    """
    try:
        # Überprüfe, ob der Benutzer in der MySQL-Datenbank existiert
        sql = "SELECT `blur` FROM `levelling` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
        val = {"user_id": user.id, "guild_id": guild.id}
        result = await db.select_var(sql, val, single=True)
        if result is None:
            log.info("User not Found")
            return
        return result
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"[Blur] • {e}")
        return


async def rankings(user: discord.Member = None, guild: discord.Guild = None):
    """Retrieve a user's ranking within the guild's leaderboard.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    user: `discord.Member`, optional
        The Discord member for whom the ranking is being retrieved.
    guild: `discord.Guild`, optional
        The guild context from which to retrieve the ranking.

    Returns
    -------
    int or None
        The user's ranking if found, or None if the guild is not found.
    """
    try:
        # Überprüfe, ob der Benutzer in der MySQL-Datenbank existiert
        sql = (
            "SELECT * FROM `levelling` WHERE `guild_id` = :guild_id  ORDER BY `xp` DESC"
        )
        val = {"guild_id": guild.id}
        e_rankings = await db.select_var(sql, val)
        rank = 0
        for x in e_rankings:
            rank += 1
            if user.id == x[0]:
                break
        return rank
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"[Rankings] • {e}")
        return


async def mainchannel(guild: discord.Guild = None):
    """Retrieve the main channel for a guild from the database.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    guild: `discord.Guild`, optional
        The guild for which the main channel is being retrieved.

    Returns
    -------
    str or None
        The main channel name if found, or None if the guild is not found.
    """
    try:
        # Überprüfe, ob der Benutzer in der MySQL-Datenbank existiert
        sql = f"SELECT `main_channel` FROM `levelling_serverbase` WHERE guild_id = {guild.id}"
        # val = (guild.id,)
        result = await db.select(sql, single=True)
        if result is None:
            log.debug("Server not Found")
            return
        return result
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"[MainChannel] • {e}")
        return


async def get_itemid(item_name=None):
    """Retrieve the item ID from the database based on its name.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    item_name: str, optional
        The name of the item for which the ID is being retrieved.

    Returns
    -------
    int or None
        The item ID if found, or None if the item is not found.
    """
    if item_name is None:
        log.error("Error in 'Database/get.py' - Itemname is None for 'get_itemid'")
        return
    try:
        # Überprüfe, ob Item in der MySQL-Datenbank existiert
        sql = "SELECT * FROM invTypes WHERE typeName = :typename"
        val = {"typename": item_name}
        result = await db.select_var(sql, val, True)
        if result is None:
            log.info("Item not found")
            return None
        return result
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"[Get ItemID] • {e}")
        return
