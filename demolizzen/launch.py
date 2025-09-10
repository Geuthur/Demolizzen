# Standard Library
import os

# Django
import django

# flake8: noqa E402
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "demolizzen.settings")
django.setup()

# Demolizzen
from demolizzen.core.bot import Demolizzen


def run_bot():
    bot = Demolizzen()
    bot.run()


if __name__ == "__main__":
    run_bot()
