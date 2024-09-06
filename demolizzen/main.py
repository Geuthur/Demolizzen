import asyncio
import os
import sys

# Add the root directory of your project to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import bot, events
from pycolorise.colors import Blue, Green
from settings import logger

sys.dont_write_bytecode = True


def run_demolizzen():
    demolizzen = bot.Demolizzen()
    events.init_events(demolizzen)
    # debug_flag args: debug, info or empty then it runs on production
    demolizzen.logger = logger.init_logger(debug_flag="info")
    demolizzen.load_extension("core.commands")
    print(Green("-------- Loading Modules ---------"))
    for ext in demolizzen.preload_ext:
        try:
            demolizzen.load_extension(f"Cogs.{ext}")
            print(Blue(f"- {ext.capitalize()} ✅ "))
        # pylint: disable=broad-except
        except Exception as e:
            print(Blue(f"- {ext.capitalize()} ❌ {e}"))
    print(Green("-------- Finished Loading --------\n"))
    loop = asyncio.get_event_loop()
    if demolizzen.token is None:
        demolizzen.logger.critical("Token must be set in order to login.")
        sys.exit(1)
    try:
        loop.run_until_complete(demolizzen.start(demolizzen.token))
    # pylint: disable=broad-except
    except Exception as e:
        demolizzen.logger.critical("Fatal exception", exc_info=e)


def main():
    run_demolizzen()


if __name__ == "__main__":
    main()
