# Third Party
from asgiref.sync import sync_to_async

# Discord
import discord
from discord.ext import commands, tasks

# Django
from django.db import DatabaseError, connection

# Demolizzen
from demolizzen.core.bot import Demolizzen


class General(commands.Cog):
    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.status_checker.start()
        self.is_okay = True

    def cog_unload(self):
        self.status_checker.cancel()

    async def db_health_check(self):
        @sync_to_async
        def check():
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                return True
            except DatabaseError as e:
                self.bot.logger.error(f"DB-Check failed: {e}")
                return False

        return await check()

    @tasks.loop(hours=1)
    async def status_checker(self):
        guilds = len(self.bot.guilds)
        if not await self.db_health_check():
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=f"{guilds} Servers",
                    state="Status: 🔴 Database Issues",
                ),
                status=discord.Status.dnd,
            )
            self.is_okay = False
        # TODO Add more checks
        if self.is_okay:
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=f"{guilds} Servers",
                    state="Status: 🟢 No Issues",
                ),
                status=discord.Status.online,
            )

    @status_checker.before_loop
    async def before_status_checker(self):
        await self.bot.wait_until_ready()
        self.bot.logger.info("Bot Issues Checker Ready")
