import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import better_exceptions

from demolizzen.settings.config import LOGS_DIR

better_exceptions.hook()

LOG_PATH = Path(LOGS_DIR)
LOG_PATH.mkdir(exist_ok=True)

LOG_FORMAT = logging.Formatter(
    "%(asctime)s %(levelname)s %(module)s %(funcName)s %(lineno)d: %(message)s",
    datefmt="[%Y-%m-%d %H:%M:%S]",
)


def create_fh(name: str):
    """Create a logging filehandler based on given file path."""

    fh = RotatingFileHandler(
        filename=Path(LOG_PATH, f"{name}.log"),
        encoding="utf-8",
        mode="a",
        maxBytes=400000,
        backupCount=20,
    )
    fh.setFormatter(LOG_FORMAT)
    return fh


def init_logger(debug_flag=None):

    logging.getLogger().setLevel(logging.INFO)

    discord_log = logging.getLogger("discord")
    discord_log.addHandler(create_fh("discord"))

    demolizzen_log = logging.getLogger("demolizzen")
    demolizzen_log.addHandler(create_fh("demolizzen"))

    main_log = logging.getLogger("main")
    main_log.addHandler(create_fh("main"))

    killboard_log = logging.getLogger("killboard")
    killboard_log.addHandler(create_fh("killboard"))

    test_log = logging.getLogger("testing")
    test_log.addHandler(create_fh("testing"))

    db_log = logging.getLogger("db")
    db_log.addHandler(create_fh("db"))

    events = logging.getLogger("events")
    events.addHandler(create_fh("events"))

    if debug_flag == "debug":
        discord_log.setLevel(logging.DEBUG)
        demolizzen_log.setLevel(logging.DEBUG)
        main_log.setLevel(logging.DEBUG)
        killboard_log.setLevel(logging.DEBUG)
        db_log.setLevel(logging.DEBUG)
        test_log.setLevel(logging.DEBUG)
        events.setLevel(logging.DEBUG)
    elif debug_flag == "info":
        discord_log.setLevel(logging.WARNING)
        demolizzen_log.setLevel(logging.WARNING)
        main_log.setLevel(logging.INFO)
        killboard_log.setLevel(logging.INFO)
        db_log.setLevel(logging.INFO)
        test_log.setLevel(logging.INFO)
        events.setLevel(logging.INFO)
    elif debug_flag == "normal":
        discord_log.setLevel(logging.ERROR)
        demolizzen_log.setLevel(logging.WARNING)
        main_log.setLevel(logging.ERROR)
        killboard_log.setLevel(logging.ERROR)
        db_log.setLevel(logging.ERROR)
        test_log.setLevel(logging.DEBUG)
        events.setLevel(logging.ERROR)
    else:
        discord_log.setLevel(logging.ERROR)
        demolizzen_log.setLevel(logging.WARNING)
        main_log.setLevel(logging.ERROR)
        killboard_log.setLevel(logging.ERROR)
        db_log.setLevel(logging.ERROR)
        test_log.setLevel(logging.DEBUG)
        events.setLevel(logging.ERROR)

    demolizzen_log.addHandler(logging.StreamHandler())

    return demolizzen_log


def change_logger(debug_flag=None):
    discord_log = logging.getLogger("discord")
    demolizzen_log = logging.getLogger("demolizzen")
    main_log = logging.getLogger("main")
    killboard_log = logging.getLogger("killboard")
    test_log = logging.getLogger("testing")
    db_log = logging.getLogger("db")

    if debug_flag == "debug":
        discord_log.setLevel(logging.DEBUG)
        demolizzen_log.setLevel(logging.DEBUG)
        main_log.setLevel(logging.DEBUG)
        killboard_log.setLevel(logging.DEBUG)
        db_log.setLevel(logging.DEBUG)
        test_log.setLevel(logging.DEBUG)
    elif debug_flag == "info":
        discord_log.setLevel(logging.INFO)
        demolizzen_log.setLevel(logging.WARNING)
        main_log.setLevel(logging.INFO)
        killboard_log.setLevel(logging.INFO)
        db_log.setLevel(logging.INFO)
        test_log.setLevel(logging.INFO)
    elif debug_flag == "normal":
        discord_log.setLevel(logging.ERROR)
        demolizzen_log.setLevel(logging.WARNING)
        main_log.setLevel(logging.ERROR)
        killboard_log.setLevel(logging.ERROR)
        db_log.setLevel(logging.ERROR)
        test_log.setLevel(logging.DEBUG)
    else:
        discord_log.setLevel(logging.ERROR)
        demolizzen_log.setLevel(logging.WARNING)
        main_log.setLevel(logging.ERROR)
        killboard_log.setLevel(logging.ERROR)
        db_log.setLevel(logging.ERROR)
        test_log.setLevel(logging.DEBUG)
