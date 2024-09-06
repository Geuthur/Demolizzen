import logging

import discord
from discord.ext.pages import Paginator
from settings import db
from settings.config import LEADERBOARD_EMBED_COLOUR

log = logging.getLogger("discord")


class LeaderboardPaginator(Paginator):
    def __init__(self, pages, timeout):
        super().__init__(pages, timeout=timeout)

    async def on_timeout(self) -> None:
        if isinstance(self.message, discord.Interaction):
            await self.message.delete()
        else:
            await self.message.delete()


# pylint: disable=unused-argument
async def leaderboard(self=None, ctx=None, guild=None):
    try:
        guild = ctx.guild
        # sort by xp desc
        sql = "SELECT * FROM levelling WHERE `guild_id` = :guild_id ORDER BY xp DESC"
        val = {"guild_id": guild.id}

        result = await db.select_var(sql, val)

        embed = discord.Embed(
            title=f":trophy: {guild}'s Leaderboard", colour=LEADERBOARD_EMBED_COLOUR
        )
        if result is None:
            return "Server Not Found!"

        if not result:
            await ctx.respond("❌ Aktuell ist die Liste nicht verfügbar")

        level = []
        pages = []
        data = []
        description = ""

        for x in result:
            values = (x[2], x[4], x[5])  # Eine Liste mit den drei Werten aus x
            data.append(values)

        for index, level in enumerate(data):
            description += (
                f"`{index + 1}.` {level[0]} `LEVEL:` {level[1]} `XP`: {level[2]}\n"
            )

            if (index + 1) % 10 == 0 or index == len(data) - 1:
                embed = discord.Embed(
                    title=f":trophy: {guild}'s Leaderboard",
                    description=description,
                    color=discord.Color.green(),
                )
                if ctx.guild.icon:
                    embed.set_thumbnail(url=ctx.guild.icon.url)
                pages.append(embed)
                description = ""

        paginator = LeaderboardPaginator(pages=pages, timeout=60)
        await paginator.respond(ctx.interaction)
    # pylint: disable=broad-except
    except Exception as e:
        log.error(f"[Leaderboard] • {e}")
        await ctx.respond(
            "Es ist ein Fehler aufgetreten, versuche es später erneut", ephemeral=True
        )
        return
