# Third Party
from asgiref.sync import sync_to_async

# Discord
import discord
from discord.ext import tasks

# Django
from django.db import Error as DatabaseError
from django.db import connection

# Demolizzen
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog


class General(BaseCog):
    key = "general"

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
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
        """Show whether the bot is healthy. Decided anew on every run, so the
        display recovers as soon as the problem is gone."""
        self.is_okay = await self.db_health_check()
        # TODO Add more checks
        if self.is_okay:
            state, status = "Status: 🟢 No Issues", discord.Status.online
        else:
            state, status = "Status: 🔴 Database Issues", discord.Status.dnd
        await self.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f"{len(self.bot.guilds)} Servers",
                state=state,
            ),
            status=status,
        )

    @status_checker.before_loop
    async def before_status_checker(self):
        await self.bot.wait_until_ready()
        self.bot.logger.info("Bot Issues Checker Ready")
