# Standard Library
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Demolizzen
from demolizzen.config import LOGS_DIR, TESTMODE

LOG_PATH = Path(LOGS_DIR)
LOG_PATH.mkdir(exist_ok=True)


class ProjectPathFormatter(logging.Formatter):
    def format(self, record):
        project_root = str(Path(__file__).parent.parent)
        if record.pathname.startswith(project_root):
            record.pathname = record.pathname[len(project_root) + 1 :]
        record.module = record.module.capitalize()
        return super().format(record)


# Format: [YYYY-MM-DD HH:MM:SS] [LEVEL] [COG] [MESSAGE]
LOG_FORMAT = ProjectPathFormatter(
    "%(asctime)s %(levelname)s [%(pathname)s:%(lineno)d] [%(module)s] %(message)s",
    datefmt="[%Y-%m-%d %H:%M:%S]",
)


def init_logger(debug_flag=None):
    root_logger = logging.getLogger()

    if not root_logger.handlers:
        # File Handler für App-Logs
        fh = RotatingFileHandler(
            filename=Path(LOG_PATH, f"{__package__}.log"),
            encoding="utf-8",
            mode="a",
            maxBytes=400000,
            backupCount=20,
        )
        fh.setFormatter(LOG_FORMAT)
        root_logger.addHandler(fh)

        # Stream Handler (Console)
        sh = logging.StreamHandler()
        sh.setFormatter(LOG_FORMAT)
        root_logger.addHandler(sh)

        # Own Handler für discord.py
        discord_fh = RotatingFileHandler(
            filename=Path(LOG_PATH, "discord.log"),
            encoding="utf-8",
            mode="a",
            maxBytes=400000,
            backupCount=10,
        )
        discord_fh.setFormatter(LOG_FORMAT)
        discord_logger = logging.getLogger("discord")
        discord_logger.handlers.clear()
        discord_logger.addHandler(discord_fh)
        discord_logger.propagate = (
            False  # Ensure no propagation to root logger (no console)
        )

    # Level je nach debug_flag
    if debug_flag == "debug":
        level = logging.DEBUG
    elif debug_flag == "info":
        level = logging.INFO
    elif debug_flag == "normal":
        level = logging.WARNING
    else:
        level = logging.ERROR

    root_logger.setLevel(level)
    logging.getLogger("discord").setLevel(level)

    if TESTMODE == "True":
        root_logger.setLevel(logging.DEBUG)
        logging.getLogger("discord").setLevel(logging.INFO)
        root_logger.debug("Logger initialized in TESTMODE with DEBUG level.")
    return root_logger
