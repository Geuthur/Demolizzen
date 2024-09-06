import logging

import discord
from discord.ext import commands, tasks
from settings.db import connect_check

log = logging.getLogger("main")
log_test = logging.getLogger("testing")


class General(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.activity_updater.start()
        self.status_checker.start()
        self.status = True

    def cog_unload(self):
        self.activity_updater.cancel()
        self.status_checker.cancel()

    @tasks.loop(hours=23)
    async def activity_updater(self):
        log.debug("Activity Updater Ready")
        try:
            guilds = len(self.bot.guilds)
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=f"{guilds} Servers",
                    state="Status: 🟢 No Issues",
                ),
                status=discord.Status.online,
            )
        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"[Loop] Activity Updater - {e}")

    @tasks.loop(hours=1)
    async def status_checker(self):
        log.debug("Bot Available Checker Ready")
        try:
            guilds = len(self.bot.guilds)
            if not await connect_check():
                await self.bot.change_presence(
                    activity=discord.Activity(
                        type=discord.ActivityType.listening,
                        name=f"{guilds} Servers",
                        state="Status: 🔴 Database Issues",
                    ),
                    status=discord.Status.dnd,
                )
                self.status = False
            # TODO Add more checks
            if self.status:
                await self.bot.change_presence(
                    activity=discord.Activity(
                        type=discord.ActivityType.listening,
                        name=f"{guilds} Servers",
                        state="Status: 🟢 No Issues",
                    ),
                    status=discord.Status.online,
                )
        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"[Loop] Bot Available Checker - {e}")

    @status_checker.before_loop
    async def before_status_checker(self):
        await self.bot.wait_until_ready()

    @activity_updater.before_loop
    async def before_activity_updater(self):
        await self.bot.wait_until_ready()
