import os
from collections import Counter
from datetime import datetime

import aiohttp
import aiomysql
import discord
from dateutil.relativedelta import relativedelta
from discord.ext import commands
from dotenv import load_dotenv
from settings import config
from settings.esi import ESI

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_HOST = os.getenv("DATABASE_HOST")
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_NAME = os.getenv("DATABASE_NAME")


class Demolizzen(commands.Bot):
    def __init__(self, **kwargs):
        # Deine intents definieren
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        self.counter = Counter()
        self.core_dir = os.path.dirname(os.path.realpath(__file__))
        self.config = config
        self.bot_users = []
        self.token = BOT_TOKEN
        self.req_perms = discord.Permissions(config.BOT_PERMISSIONS)
        self.preload_ext = config.PRELOAD_EXTENSIONS
        kwargs["command_prefix"] = "$"
        super().__init__(intents=intents, **kwargs)
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.esi_data = ESI(self.session)
        self.db = aiomysql.connect(
            host=DATABASE_HOST,
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            db=DATABASE_NAME,
        )
        self.db_vow = aiomysql.connect(
            host=DATABASE_HOST,
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            db=DATABASE_NAME,
        )

    @discord.utils.cached_property
    def invite_url(self):
        invite_url = discord.utils.oauth_url(self.user.id, permissions=self.req_perms)
        return invite_url

    @property
    def uptime(self):
        return relativedelta(datetime.utcnow(), self.launch_time)

    @property
    def uptime_str(self):
        uptime = self.uptime
        year_str, month_str, day_str, hour_str = ("",) * 4
        if uptime.years >= 1:
            year_str = f"{uptime.years}y "
        if uptime.months >= 1 or year_str:
            month_str = f"{uptime.months}m "
        if uptime.days >= 1 or month_str:
            d_unit = "d" if month_str else " days"
            day_str = f"{uptime.days}{d_unit} "
        if uptime.hours >= 1 or day_str:
            h_unit = ":" if month_str else " hrs"
            hour_str = f"{uptime.hours}{h_unit}"
        m_unit = "" if month_str else " mins"
        mins = uptime.minutes if month_str else f" {uptime.minutes}"
        secs = "" if day_str else f" {uptime.seconds} secs"
        min_str = f"{mins}{m_unit}{secs}"

        uptime_str = "".join((year_str, month_str, day_str, hour_str, min_str))

        return uptime_str
