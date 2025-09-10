# Standard Library
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Demolizzen
from demolizzen import __package_name__
from demolizzen.config import LOGS_DIR, TESTMODE

LOG_PATH = Path(LOGS_DIR)
LOG_PATH.mkdir(exist_ok=True)

LOG_FORMAT = logging.Formatter(
    "%(asctime)s %(levelname)s [%(pathname)s:%(lineno)d] [%(module)s] %(message)s",
    datefmt="[%Y-%m-%d %H:%M:%S]",
)


def init_logger(debug_flag=None):
    logger = logging.getLogger(__package_name__)

    # File Handler
    fh = RotatingFileHandler(
        filename=Path(LOG_PATH, f"{__package_name__}.log"),
        encoding="utf-8",
        mode="a",
        maxBytes=400000,
        backupCount=20,
    )
    fh.setFormatter(LOG_FORMAT)
    logger.addHandler(fh)

    # Stream Handler (Console)
    sh = logging.StreamHandler()
    sh.setFormatter(LOG_FORMAT)
    logger.addHandler(sh)

    # Level je nach debug_flag
    if debug_flag == "debug":
        level = logging.DEBUG
    elif debug_flag == "info":
        level = logging.INFO
    elif debug_flag == "normal":
        level = logging.WARNING
    else:
        level = logging.ERROR

    logger.setLevel(level)
    logging.getLogger().setLevel(level)  # Root-Logger
    logging.getLogger("discord").setLevel(level)  # Discord-Logger

    if TESTMODE == "True":
        logger.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("discord").setLevel(logging.DEBUG)
        logger.debug("Logger initialized in TESTMODE with DEBUG level.")
    return logger
