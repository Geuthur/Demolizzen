import asyncio
import logging
import os
from urllib.parse import quote

# Secure Configs for Github
from dotenv import load_dotenv
from sqlalchemy import TIMESTAMP, BigInteger, Column, Float, Integer, String, Text, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.declarative import declarative_base

load_dotenv()

DATABASE_HOST = os.getenv("DATABASE_HOST")
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_NAME = os.getenv("DATABASE_NAME")

DATABASE_HOST_WEBSITE = os.getenv("DATABASE_HOST_WEBSITE")
DATABASE_USER_WEBSITE = os.getenv("DATABASE_USER_WEBSITE")
DATABASE_PASSWORD_WEBSITE = os.getenv("DATABASE_PASSWORD_WEBSITE")
DATABASE_NAME_WEBSITE = os.getenv("DATABASE_NAME_WEBSITE")

DATABASE_PASSWORD_ENCODED = quote(DATABASE_PASSWORD)
DATABASE_PASSWORD_WEBSITE_ENCODED = quote(DATABASE_PASSWORD_WEBSITE)

LOCK = asyncio.Lock()

TESTMODE = os.getenv("TESTMODE")

log = logging.getLogger("db")
log_test = logging.getLogger("testing")

Base = declarative_base()


class Bank(Base):
    __tablename__ = "bank"
    user_id = Column(BigInteger, primary_key=True)
    user_name = Column(String(255, collation="utf8mb3_general_ci"))
    wallet = Column(BigInteger, nullable=False, server_default="0")
    bank = Column(BigInteger, nullable=False, server_default="0")
    guild_id = Column(BigInteger, primary_key=True)


class Daily(Base):
    __tablename__ = "daily"
    user_id = Column(BigInteger, primary_key=True)
    user_name = Column(Text(collation="utf8mb3_general_ci"), nullable=False)
    last_claim = Column(
        String(70, collation="utf8mb3_general_ci"), nullable=False, server_default="0"
    )
    streak = Column(Integer, nullable=False, server_default="0")
    guild_id = Column(BigInteger, primary_key=True)


class Levelling(Base):
    __tablename__ = "levelling"
    user_id = Column(BigInteger, primary_key=True)
    user_name = Column(Text(collation="utf8mb3_general_ci"))
    guild_id = Column(BigInteger, primary_key=True)
    level = Column(BigInteger)
    xp = Column(BigInteger)
    background = Column(Text)
    xp_colour = Column(Text)
    blur = Column(Integer)
    border = Column(Text)


class LevellingServerbase(Base):
    __tablename__ = "levelling_serverbase"
    guild_id = Column(BigInteger, primary_key=True)
    main_channel = Column(Text, nullable=True)
    active = Column(Integer, nullable=False, server_default="1")


class Mining(Base):
    __tablename__ = "mining"
    user_id = Column(BigInteger, primary_key=True)
    user_name = Column(String(255, collation="utf8mb3_general_ci"), nullable=False)
    cooldown = Column(String(80, collation="utf8mb3_general_ci"), server_default="0")
    chance = Column(Integer, server_default="0")
    loan = Column(Integer, server_default="0")
    claimed = Column(Integer, server_default="1")
    schiff = Column(String(50, collation="utf8mb3_general_ci"), server_default="0")
    insurance = Column(Integer, server_default="0")
    type = Column(String(50, collation="utf8mb3_general_ci"), server_default="normal")
    guild_id = Column(BigInteger, primary_key=True)


class Raiding(Base):
    __tablename__ = "raiding"
    user_id = Column(BigInteger, primary_key=True)
    user_name = Column(String(255, collation="utf8mb3_general_ci"), nullable=False)
    cooldown = Column(
        String(80, collation="utf8mb3_general_ci"), nullable=False, server_default="0"
    )
    chance = Column(Integer, nullable=False, server_default="0")
    loan = Column(Integer, nullable=False, server_default="0")
    claimed = Column(Integer, nullable=False, server_default="1")
    schiff = Column(
        String(50, collation="utf8mb3_general_ci"), nullable=False, server_default="0"
    )
    insurance = Column(Integer, nullable=False, server_default="0")
    type = Column(
        String(50, collation="utf8mb3_general_ci"),
        nullable=False,
        server_default="normal",
    )
    guild_id = Column(BigInteger, primary_key=True)


class Working(Base):
    __tablename__ = "working"
    user_id = Column(BigInteger, primary_key=True)
    user_name = Column(String(255, collation="utf8mb3_general_ci"), nullable=False)
    cooldown = Column(
        String(80, collation="utf8mb3_general_ci"), nullable=False, server_default="0"
    )
    chance = Column(Integer, nullable=False, server_default="0")
    loan = Column(Integer, nullable=False, server_default="0")
    claimed = Column(Integer, nullable=False, server_default="1")
    guild_id = Column(BigInteger, primary_key=True)


class Bag(Base):
    __tablename__ = "bag"
    user_id = Column(BigInteger, primary_key=True)
    user_name = Column(String(255, collation="utf8mb3_general_ci"), nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    item_name = Column(String(255, collation="utf8mb3_general_ci"), nullable=False)
    item_quantity = Column(Integer, nullable=False)
    type = Column(String(70, collation="utf8mb3_general_ci"), nullable=False)


class EveShop(Base):
    __tablename__ = "eve_shop"
    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    price = Column(BigInteger, nullable=False)
    description = Column(Text, nullable=False)
    insurance = Column(Text, nullable=True)
    type = Column(Text, nullable=False)
    shop = Column(Text, nullable=True)


# EVE Killmail Module


class ZKillboard(Base):
    __tablename__ = "zKillboard"
    id = Column(Integer, primary_key=True)
    channelid = Column(BigInteger, nullable=False)
    serverid = Column(BigInteger, nullable=False)
    groupid = Column(BigInteger, nullable=True)
    ownerid = Column(BigInteger, nullable=False)
    losses = Column(Text, nullable=True)
    threshold = Column(BigInteger, nullable=False)


# Token System


class AccessTokens(Base):
    __tablename__ = "access_tokens"
    id = Column(Integer, primary_key=True)
    character_id = Column(BigInteger, nullable=False)
    discord_id = Column(BigInteger, nullable=False)
    refresh_token = Column(Text, nullable=False)
    access_token = Column(Text, default=None)
    expires = Column(BigInteger, default=None)


# Caching System


class EveCharnameCache(Base):
    __tablename__ = "eve_charname_cache"
    character_id = Column(Integer, primary_key=True)
    char_name = Column(String(64, collation="utf8mb4_unicode_ci"), nullable=False)


class EvePricecache(Base):
    __tablename__ = "eve_pricecache"
    item_name = Column(String(255, collation="utf8mb4_unicode_ci"), primary_key=True)
    price = Column(Float, nullable=False)
    buy = Column(Float, nullable=True)
    tradehub = Column(Integer, nullable=False)
    expiration = Column(TIMESTAMP, nullable=False)


# Erstelle eine Engine und binde die Klassen an die Tabellen
if TESTMODE == "True":
    print("Testmode is Active")
    DISCORD_ENGINE = create_async_engine(
        f"mysql+aiomysql://{DATABASE_USER}:{DATABASE_PASSWORD_ENCODED}@{DATABASE_HOST}/{DATABASE_NAME}",
        echo=True,
    )
    VOW_ENGINE = create_async_engine(
        f"mysql+aiomysql://{DATABASE_USER_WEBSITE}:{DATABASE_PASSWORD_WEBSITE_ENCODED}@{DATABASE_HOST_WEBSITE}/{DATABASE_NAME_WEBSITE}",
        echo=True,
    )
else:
    DISCORD_ENGINE = create_async_engine(
        f"mysql+aiomysql://{DATABASE_USER}:{DATABASE_PASSWORD_ENCODED}@{DATABASE_HOST}/{DATABASE_NAME}",
        echo=False,
    )
    VOW_ENGINE = create_async_engine(
        f"mysql+aiomysql://{DATABASE_USER_WEBSITE}:{DATABASE_PASSWORD_WEBSITE_ENCODED}@{DATABASE_HOST_WEBSITE}/{DATABASE_NAME_WEBSITE}",
        echo=False,
    )


# Erstelle eine asynchrone Funktion, um die Tabellen zu erstellen
async def create_tables():
    async with DISCORD_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Erstelle eine asynchrone Funktion, um die Tabellen zu erstellen
async def connect_check():
    # pylint: disable=global-statement
    global DISCORD_ENGINE, VOW_ENGINE
    # Überprüfe, ob die Verbindung aktiv ist
    if not await is_connection_active(DISCORD_ENGINE):
        log.error("Datenbankverbindung nicht aktiv. Stelle Verbindung her.")
        DISCORD_ENGINE = create_async_engine(
            f"mysql+aiomysql://{DATABASE_USER}:{DATABASE_PASSWORD_ENCODED}@{DATABASE_HOST}/{DATABASE_NAME}",
            echo=False,
        )
        VOW_ENGINE = create_async_engine(
            f"mysql+aiomysql://{DATABASE_USER_WEBSITE}:{DATABASE_PASSWORD_WEBSITE_ENCODED}@{DATABASE_HOST_WEBSITE}/{DATABASE_NAME_WEBSITE}",
            echo=False,
        )
    else:
        return True


async def get_db(alias):
    if alias == "vow":
        return VOW_ENGINE
    return DISCORD_ENGINE


# Starte die asynchrone Funktion im nicht-asynchronen Kontext
loop = asyncio.get_event_loop()
loop.run_until_complete(create_tables())


async def is_connection_active(engine):
    try:
        async with engine.connect():
            return True
    # pylint: disable=broad-except
    except Exception:
        return False


# Select Operations


async def select(
    sql,
    single=False,
    dictlist=False,
    database=DISCORD_ENGINE,
    max_retries=3,
    retry_delay=5,
):
    """
    Execute a given SELECT query on the database.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    sql: `str`
        SQL statement to be executed.
    single: `bool`, optional
        Indicates if a single row and single column is to be returned.
        Default is `False`.
    db: `DB.Connection`, optional
        The database connection. Not required, unless not using
        the default database.
    dictlist: `bool`, optional
        Return rows as dictionaries with column names as keys.
        Default is `False`.

    Returns
    -------
    List[Tuple[Any]], Any
        If not `single`, returns a list of tuples containing all returned
        record values.
        If `single`, returns the first value from the first record.
        If no records are returned, it returns None.
    """
    exception_occurred = False

    for attempt in range(max_retries + 1):
        try:
            # Check Connection
            await connect_check()

            # Verwende die asynchrone Sitzung, um eine Verbindung zu erstellen
            async with database.begin() as session:
                cursor = await session.execute(text(sql))
                column_names = cursor.keys()
                if dictlist:
                    if single:
                        data = cursor.fetchone()
                        # pylint: disable=unnecessary-comprehension
                        data = (
                            {column: value for column, value in zip(column_names, data)}
                            if data
                            else None
                        )
                    else:
                        data = cursor.fetchall()
                        # Extrahiere die Spaltennamen

                        # Erstelle eine Liste von Dictionaries, wobei die Schlüssel die Spaltennamen sind
                        # pylint: disable=unnecessary-comprehension
                        data = [
                            {column: value for column, value in zip(column_names, row)}
                            for row in data
                        ]
                else:
                    if single:
                        data = cursor.fetchone()
                        data = data[0] if data else None
                    else:
                        data = cursor.fetchall()
                        data = data if data else None
            if exception_occurred:
                log.debug(f"Select {sql} wurde erfolgreich abgerufen")
            return data
        # pylint: disable=broad-except
        except Exception as e:
            exception_occurred = True
            if attempt == max_retries:
                log.error(
                    "Fehler bei der Datenbankoperation - Select SQL: %s - SQL Command: %s",
                    e,
                    sql,
                )
            if attempt < max_retries:
                log.debug(
                    f"Versuch {attempt + 1} von {max_retries}. Warte {retry_delay} Sekunden vor dem erneuten Versuch."
                )
                await asyncio.sleep(retry_delay)
    return False


async def select_var(
    sql,
    var,
    single=False,
    dictlist=False,
    database=DISCORD_ENGINE,
    max_retries=3,
    retry_delay=5,
):
    """
    Execute a SELECT query on the database with placeholder variables.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    sql : str
        The SQL statement to be executed.
    var : tuple
        A tuple of values to replace placeholders in the SQL statement.
    single : bool, optional
        Indicates whether to return a single value (first column, first row).
        Default is False.
    db : DB.Connection, optional
        The database connection. This parameter is not required unless you're
        using a non-default database connection.
    dictlist : bool, optional
        Specifies whether to return results as a list of dictionaries with
        column names as keys. Default is False.

    Returns
    -------
    list of tuples, any
        If not in single mode, returns a list of tuples containing all
        returned record values.
        If in single mode, returns the first value from the first record.
        If no records are returned, returns None.
    """
    exception_occurred = False

    for attempt in range(max_retries + 1):
        try:
            # Check Connection
            await connect_check()

            # Verwende die asynchrone Sitzung, um eine Verbindung zu erstellen
            async with database.begin() as session:

                cursor = await session.execute(text(sql), var)
                column_names = cursor.keys()

                if dictlist:
                    if single:
                        data = cursor.fetchone()
                        # pylint: disable=unnecessary-comprehension
                        data = (
                            {column: value for column, value in zip(column_names, data)}
                            if data
                            else None
                        )
                    else:
                        data = cursor.fetchall()
                        # Extrahiere die Spaltennamen

                        # Erstelle eine Liste von Dictionaries, wobei die Schlüssel die Spaltennamen sind
                        # pylint: disable=unnecessary-comprehension
                        data = [
                            {column: value for column, value in zip(column_names, row)}
                            for row in data
                        ]

                else:
                    if single:
                        data = cursor.fetchone()
                        data = data[0] if data else None
                    else:
                        data = cursor.fetchall()
                        data = data if data else None
            if exception_occurred:
                log.debug(f"Select Var{sql} - {var} wurde erfolgreich abgerufen")
            return data
        # pylint: disable=broad-except
        except Exception as e:
            exception_occurred = True
            if attempt == max_retries:
                log.error(
                    f"Fehler bei der Datenbankoperation - Select Var SQL: {e} - SQL Command: {sql}"
                )
            if attempt < max_retries:
                log.debug(
                    f"Versuch {attempt + 1} von {max_retries}. Warte {retry_delay} Sekunden vor dem erneuten Versuch."
                )
                await asyncio.sleep(retry_delay)
    return False


async def check_user(user, guild, table, database=DISCORD_ENGINE):
    """
    Check user record in the specified database table.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    user: `ctx.author`
        The user information to be checked to the database.
    guild: `ctx.guild.id`
        The guild information where the user belongs.
    table: `str`
        The name of the table where the user record will be inserted.
    db: `Connection`, optional
        The database connection. This parameter is not required unless you're
        using a non-default database connection.
    Returns
    -------
        Entry
            Returns the record values.
            If no records are returned, returns None.
    """
    try:
        # Check Connection
        await connect_check()

        # Verwende die asynchrone Sitzung, um eine Verbindung zu erstellen
        async with database.begin() as session:
            result = await session.execute(
                text(
                    f"SELECT * FROM `{table}` WHERE `user_id` = {user.id} AND `guild_id` = {guild}"
                )
            )

            data = result.fetchone()

            data = data[0] if data else None

            return data
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"Fehler bei der Datenbankoperation - Check User: {e}")
        return False


# Execute Operations (With Transaction)
# Execute Operations (With Transaction)


async def execute_sql(
    sql, var=None, database=DISCORD_ENGINE, max_retries=3, retry_delay=5
):
    """
    Execute a given SQL query on the database with optional placeholder variable support.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    sql : str
        The SQL statement to be executed.
    var : tuple, optional
        A tuple of values to replace placeholders in the SQL statement.
    db : Connection, optional
        The database connection. This parameter is not required unless you're
        using a non-default database connection.

    Returns
    -------
    True if Successful
    """
    exception_occurred = False
    for attempt in range(max_retries + 1):
        try:
            # Check Connection
            await connect_check()

            # Verwende die asynchrone Sitzung, um eine Verbindung zu erstellen
            async with database.begin() as session:
                if var:
                    check = await session.execute(text(sql), var)
                else:
                    check = await session.execute(text(sql))
                if exception_occurred:
                    log.debug(f"Execute {sql} - {var} wurde erfolgreich ausgeführt")
                return check
        # pylint: disable=broad-except
        except Exception as e:
            exception_occurred = True
            if attempt == max_retries:
                log.error(
                    f"Fehler bei der Datenbankoperation - Execute SQL: {e} - SQL Command: {sql} - {var}"
                )
            if attempt < max_retries:
                log.debug(
                    f"Versuch {attempt + 1} von {max_retries}. Warte {retry_delay} Sekunden vor dem erneuten Versuch."
                )
                await asyncio.sleep(retry_delay)
    return False


async def executemany_sql(sql, database=DISCORD_ENGINE, max_retries=3, retry_delay=5):
    """
    Execute a batch SQL querys on the database with optional placeholder variable support.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    sql : str
        The SQL statement to be executed.
    db : Connection, optional
        The database connection. This parameter is not required unless you're
        using a non-default database connection.

    Returns
    -------
    True if Successful
    """
    exception_occurred = False
    for attempt in range(max_retries + 1):
        try:
            # Check Connection
            await connect_check()

            # Verwende die asynchrone Sitzung, um eine Verbindung zu erstellen
            async with database.begin() as session:
                # Überprüfe, ob ein Datensatz mit den gleichen Werten bereits existiert
                for query in sql:
                    try:
                        await session.execute(text(query))
                    # pylint: disable=broad-except
                    except Exception as e:
                        if "Duplicate entry" in str(e):
                            log.debug(
                                f"Fehler bei der Datenbankoperation - Einzelne Query: {e} - SQL Command: {query}"
                            )
                            continue
                        # Hier könnten Sie spezifisch auf einen Fehler in dieser Iteration reagieren
                        log.error(
                            f"Fehler bei der Datenbankoperation - Einzelne Query: {e} - SQL Command: {query}"
                        )
                        continue

                if exception_occurred:
                    log.debug(f"Executemany {sql} wurde erfolgreich ausgeführt")
                return True
        # pylint: disable=broad-except
        except Exception as e:
            exception_occurred = True
            if attempt == max_retries:
                log.error(
                    f"Fehler bei der Datenbankoperation - Execute Many: {e} - SQL Command: {sql}"
                )
            if attempt < max_retries:
                log.debug(
                    f"Versuch {attempt + 1} von {max_retries}. Warte {retry_delay} Sekunden vor dem erneuten Versuch."
                )
                await asyncio.sleep(retry_delay)
    return False


async def executemany_var_sql(
    sql, parameters, database=DISCORD_ENGINE, max_retries=3, retry_delay=5
):
    """
    Execute a batch SQL querys on the database with optional placeholder variable support.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    sql : str
        The SQL statement to be executed.
    parameters : tuple, optional
        A tuple of values to replace placeholders in the SQL statement.
    db : Connection, optional
        The database connection. This parameter is not required unless you're
        using a non-default database connection.

    Returns
    -------
    True if Successful
    """
    exception_occurred = False
    for attempt in range(max_retries + 1):
        try:
            # Check Connection
            await connect_check()

            # Verwende die asynchrone Sitzung, um eine Verbindung zu erstellen
            async with database.begin() as session:
                # Überprüfe, ob ein Datensatz mit den gleichen Werten bereits existiert
                check = await session.execute(text(sql), parameters)
                if exception_occurred:
                    log.debug(
                        f"Executemany Var {sql} - {parameters} wurde erfolgreich ausgeführt"
                    )
                return check
        # pylint: disable=broad-except
        except Exception as e:
            exception_occurred = True
            if attempt == max_retries:
                log.error(
                    f"Fehler bei der Datenbankoperation - Execute Many Var: {e} - SQL Command: {sql} - {parameters}"
                )
            if attempt < max_retries:
                log.debug(
                    f"Versuch {attempt + 1} von {max_retries}. Warte {retry_delay} Sekunden vor dem erneuten Versuch."
                )
                await asyncio.sleep(retry_delay)
    return False


# Create Operations
# Create Operations


async def create_user(
    user, guild, table, database=DISCORD_ENGINE, max_retries=3, retry_delay=5
):
    """
    Create a new user record in the specified database table.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    user: `ctx.author`
        The user information to be added to the database.
    guild: `ctx.guild.id`
        The guild information where the user belongs.
    table: `str`
        The name of the table where the user record will be inserted.
    db: `Connection Engine`, optional
        The database connection. This parameter is not required unless you're
        using a non-default database connection.
    """
    exception_occurred = False
    for attempt in range(max_retries + 1):
        try:
            # Check Connection
            await connect_check()

            # Verwende die asynchrone Sitzung, um eine Verbindung zu erstellen
            async with database.begin() as session:

                # Überprüfe, ob ein Datensatz mit den gleichen Werten bereits existiert
                existing_user = await session.execute(
                    text(
                        f"SELECT * FROM `{table}` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
                    ),
                    {"user_id": user.id, "guild_id": guild},
                )
                column_names = existing_user.keys()
                existing_user = existing_user.fetchone()

                if existing_user:
                    # Eintrag existiert bereits, gibt die vorhandenen Daten zurück
                    # pylint: disable=unnecessary-comprehension
                    result = (
                        {
                            column: value
                            for column, value in zip(column_names, existing_user)
                        }
                        if existing_user
                        else None
                    )
                else:
                    # Eintrag existiert nicht, führe den INSERT durch
                    await session.execute(
                        text(
                            f"INSERT INTO `{table}` (`user_id`, `guild_id`, `user_name`) VALUES (:user_id, :guild_id, :user_name)"
                        ),
                        {
                            "user_id": user.id,
                            "guild_id": guild,
                            "user_name": user.display_name.capitalize(),
                        },
                    )

                    # Hole alle Werte des eingefügten Benutzers ab
                    result = await session.execute(
                        text(
                            f"SELECT * FROM `{table}` WHERE `user_id` = :user_id AND `guild_id` = :guild_id"
                        ),
                        {"user_id": user.id, "guild_id": guild},
                    )
                    result = result.fetchone()
                    # pylint: disable=unnecessary-comprehension
                    result = (
                        {column: value for column, value in zip(column_names, result)}
                        if result
                        else None
                    )

                if exception_occurred:
                    log.debug("Create User - wurde erfolgreich ausgeführt")
                return result
        # pylint: disable=broad-except
        except Exception as e:
            exception_occurred = True
            if attempt == max_retries:
                log.exception(f"Fehler bei der Datenbankoperation - Create User: {e}")
            if attempt < max_retries:
                log.debug(
                    f"Versuch {attempt + 1} von {max_retries}. Warte {retry_delay} Sekunden vor dem erneuten Versuch."
                )
                await asyncio.sleep(retry_delay)
    return False


async def create_user_new(
    user, guild, database=DISCORD_ENGINE, max_retries=3, retry_delay=5
):
    exception_occurred = False
    for attempt in range(max_retries + 1):
        try:
            # Check Connection
            await connect_check()

            # Verwende die Session-Klasse, um eine Verbindung zu erstellen
            async with database.begin() as session:
                # Überprüfe, ob ein Datensatz mit den gleichen Werten bereits existiert
                await session.execute(
                    Raiding.__table__.insert().values(
                        user_id=user.id,
                        guild_id=guild,
                        user_name=user.display_name.capitalize(),
                    )
                )
                await session.execute(
                    Mining.__table__.insert().values(
                        user_id=user.id,
                        guild_id=guild,
                        user_name=user.display_name.capitalize(),
                    )
                )
                await session.execute(
                    Working.__table__.insert().values(
                        user_id=user.id,
                        guild_id=guild,
                        user_name=user.display_name.capitalize(),
                    )
                )
                await session.execute(
                    Daily.__table__.insert().values(
                        user_id=user.id,
                        guild_id=guild,
                        user_name=user.display_name.capitalize(),
                    )
                )
                await session.execute(
                    Bank.__table__.insert().values(
                        user_id=user.id,
                        guild_id=guild,
                        user_name=user.display_name.capitalize(),
                    )
                )
                if exception_occurred:
                    log.debug("Create User New - wurde erfolgreich ausgeführt")
                return True
        # pylint: disable=broad-except
        except Exception as e:
            exception_occurred = True
            if attempt == max_retries:
                log.error(f"Fehler bei der Datenbankoperation - Create User New: {e}")
            if attempt < max_retries:
                log.debug(
                    f"Versuch {attempt + 1} von {max_retries}. Warte {retry_delay} Sekunden vor dem erneuten Versuch."
                )
                await asyncio.sleep(retry_delay)
    return False


# Remove Operations
# Remove Operations


async def remove_user(
    user, guild, table, database=DISCORD_ENGINE, max_retries=3, retry_delay=5
):
    """
    Remove a user record in the specified database table.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    user: `ctx.author` or `member`
        The user information to be removed from the database.
    guild: `ctx.guild.id`
        The guild information where the user belongs.
    table: `str`
        The name of the table where the user record will be removed.
    db: `Connection`, optional
        The database connection. This parameter is not required unless you're
        using a non-default database connection.
    """
    exception_occurred = False
    for attempt in range(max_retries + 1):
        try:
            # Check Connection
            await connect_check()

            async with database.begin() as session:
                sql = await session.execute(
                    text(
                        f"DELETE FROM `{table}` WHERE `user_id` = {user.id} AND `guild_id` = {guild}"
                    )
                )
                if exception_occurred:
                    log.debug(f"Remove User {sql} - wurde erfolgreich ausgeführt")
                return
        # pylint: disable=broad-except
        except Exception as e:
            exception_occurred = True
            if attempt == max_retries:
                log.error(
                    f"Fehler bei der Datenbankoperation - Remove User: {e} - SQL Command: {sql}"
                )
            if attempt < max_retries:
                log.debug(
                    f"Versuch {attempt + 1} von {max_retries}. Warte {retry_delay} Sekunden vor dem erneuten Versuch."
                )
                await asyncio.sleep(retry_delay)

    return False


async def remove_user_new(
    user, guild, database=DISCORD_ENGINE, max_retries=3, retry_delay=5
):
    """
    Remove a user record in the specified database table.

    Access is controlled with a coroutine wrapper, so this function
    must be awaited when used.

    Parameters
    ----------
    user: `ctx.author` or `member`
        The user information to be removed from the database.
    guild: `ctx.guild.id`
        The guild information where the user belongs.
    db: `Connection`, optional
        The database connection. This parameter is not required unless you're
        using a non-default database connection.
    """
    exception_occurred = False
    for attempt in range(max_retries + 1):
        try:
            # Check Connection
            await connect_check()

            async with database.begin() as session:
                await session.execute(
                    text(
                        f"DELETE FROM `raiding` WHERE `user_id` = {user.id} AND `guild_id` = {guild}"
                    )
                )
                await session.execute(
                    text(
                        f"DELETE FROM `mining` WHERE `user_id` = {user.id} AND `guild_id` = {guild}"
                    )
                )
                await session.execute(
                    text(
                        f"DELETE FROM `working` WHERE `user_id` = {user.id} AND `guild_id` = {guild}"
                    )
                )
                await session.execute(
                    text(
                        f"DELETE FROM `daily` WHERE `user_id` = {user.id} AND `guild_id` = {guild}"
                    )
                )
                await session.execute(
                    text(
                        f"DELETE FROM `bank` WHERE `user_id` = {user.id} AND `guild_id` = {guild}"
                    )
                )
                if exception_occurred:
                    log.debug("Remove User New - wurde erfolgreich ausgeführt")
                return True
        # pylint: disable=broad-except
        except Exception as e:
            exception_occurred = True
            if attempt == max_retries:
                log.error(f"Fehler bei der Datenbankoperation - Remove User New: {e}")
            if attempt < max_retries:
                log.debug(
                    f"Versuch {attempt + 1} von {max_retries}. Warte {retry_delay} Sekunden vor dem erneuten Versuch."
                )
                await asyncio.sleep(retry_delay)

    return False
