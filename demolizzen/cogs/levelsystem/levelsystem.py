# Standard Library
import asyncio
import logging

# Discord
import discord
from discord.ext import commands
from discord.ext.pages import Paginator

# Demolizzen
from demolizzen import config
from demolizzen.cogs.levelsystem._cards import (
    AssetError,
    AssetLoader,
    render_level_up_card,
    render_rank_card,
)
from demolizzen.config import DISCORD_EMBED_COLOR_DANGER
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog, guild_listener
from demolizzen.services import guilds, levels
from demolizzen.utils.functions import get_command_mention

logger = logging.getLogger(__name__)


class Levelsystem(BaseCog):
    """Earn experience by chatting and climb the server's leaderboard."""

    key = "levelsystem"

    def __init__(self, bot: "Demolizzen"):
        super().__init__(bot)
        self.title = "Levelsystem"
        self.alias = "levelsystem"
        # Images are fetched through the bot's HTTP session, which exists once
        # the bot has started.
        self.assets = AssetLoader(lambda: self.bot.session)

    # ---------------------------- Commands ----------------------------

    @commands.slash_command(contexts=[discord.InteractionContextType.guild])
    @commands.cooldown(3, 600, commands.BucketType.user)
    async def leaderboard(self, ctx: discord.ApplicationContext):
        """
        Get rank list from Server
        """
        await ctx.defer()
        board = await levels.leaderboard(ctx.guild.id)
        if not board:
            embed = discord.Embed(description="❌ The list is currently not available")
            return await ctx.respond(embed=embed)

        pages = []
        description = ""
        for index, (name, level, experience) in enumerate(board):
            description += (
                f"`{index + 1}.` {name} `LEVEL:` {level} `XP`: {experience}\n"
            )
            if (index + 1) % 10 == 0 or index == len(board) - 1:
                embed = discord.Embed(
                    title=f":trophy: {ctx.guild}'s Leaderboard",
                    description=description,
                    color=discord.Color.green(),
                )
                if ctx.guild.icon:
                    embed.set_thumbnail(url=ctx.guild.icon.url)
                pages.append(embed)
                description = ""

        paginator = Paginator(pages=pages, timeout=30, disable_on_timeout=True)
        return await paginator.respond(ctx.interaction)

    @commands.slash_command(contexts=[discord.InteractionContextType.guild])
    @commands.cooldown(3, 600, commands.BucketType.user)
    async def rank(self, ctx: discord.ApplicationContext, member: discord.Member):
        """
        Get member's rank
        """
        await ctx.defer()
        data = await levels.get_card_data(ctx.guild.id, member.id)
        if data is None:
            embed = discord.Embed(
                description=f"❌ {member.display_name} is not registered in the leveling system."
            )
            return await ctx.respond(embed=embed)

        try:
            background, border, avatar = await asyncio.gather(
                self.assets.load(data.background),
                self.assets.load(data.border),
                self.assets.load(str(member.display_avatar.url), cache=False),
            )
            progress = levels.progress(data.experience)
            # Drawing is CPU work; keep it off the event loop.
            image = await asyncio.to_thread(
                render_rank_card,
                background,
                avatar,
                border,
                name=member.name.capitalize(),
                experience=data.experience,
                level=progress.level,
                into_level=progress.into_level,
                needed=progress.needed,
                percent=progress.percent,
                colour=data.xp_colour,
                blur=data.blur,
                rank=data.rank,
            )
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.warning("Rank card for %s failed: %r", member.id, error)
            embed = discord.Embed(
                description="❌ Error generating rank card. Please try again later."
            )
            return await ctx.respond(embed=embed)

        embed = discord.Embed()
        embed.set_image(url="attachment://rank_card.png")
        return await ctx.respond(
            embed=embed, file=discord.File(fp=image, filename="rank_card.png")
        )

    # ---------------------------- Listener ----------------------------

    @guild_listener()
    async def on_message(self, message: discord.Message):
        """Give experience for messages written in a server."""
        if message.guild is None or message.author.bot:
            return
        # Decide first whether this message earns anything; most do not, and
        # those must not cost a database query.
        amount = levels.message_xp(len(message.content.split()))
        if amount <= 0:
            return
        try:
            result = await levels.add_xp(
                message.guild.id,
                message.guild.name,
                message.author.id,
                message.author.display_name,
                amount,
            )
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Adding experience for %s failed", message.author.id)
            return
        if result.leveled_up:
            await self._announce_level_up(message.author, result)

    async def _announce_level_up(self, member: discord.Member, result) -> None:
        """Post the level-up card. Experience and level are booked either way."""
        guild = member.guild
        try:
            announcement = await levels.get_announcement(guild.id)
            if not announcement.enabled:
                return
            channel = None
            if announcement.channel_id:
                channel = guild.get_channel(announcement.channel_id)
            channel = channel or guild.system_channel
            if channel is None:
                return
            if not channel.permissions_for(guild.me).send_messages:
                return

            data = await levels.get_card_data(guild.id, member.id)
            background, shade, border, avatar = await asyncio.gather(
                self.assets.load(config.LEVEL_UP_BACKGROUND),
                self.assets.load(config.LEVEL_UP_BACKGROUND_SHADE),
                self.assets.load(data.border),
                self.assets.load(str(member.display_avatar.url), cache=False),
            )
            progress = levels.progress(result.experience)
            image = await asyncio.to_thread(
                render_level_up_card,
                background,
                shade,
                avatar,
                border,
                name=member.display_name.capitalize(),
                level=progress.level,
                xp_into_level=progress.into_level,
            )
            embed = discord.Embed()
            embed.set_image(url="attachment://level_card.png")
            await channel.send(
                file=discord.File(fp=image, filename="level_card.png"),
                embed=embed,
                content=f"{member.mention}," if config.LEVEL_UP_PING is True else "",
            )
        except AssetError as error:
            logger.warning("Level-up card for %s skipped: %s", member.id, error)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Level-up card for %s failed", member.id)

    @guild_listener()
    async def on_guild_channel_delete(self, channel: discord.TextChannel):
        """Pick a new main channel when the current one was deleted."""
        try:
            guild = channel.guild
            if channel.id != await guilds.get_main_channel(guild.id):
                return
            # Use the system channel if available, else the first text channel
            new_channel = None
            if guild.system_channel and guild.system_channel.id != channel.id:
                new_channel = guild.system_channel
            if not new_channel:
                candidates = [
                    ch
                    for ch in await guild.fetch_channels()
                    if isinstance(ch, discord.TextChannel) and ch.id != channel.id
                ]
                if candidates:
                    new_channel = candidates[0]
            if not new_channel:
                return

            await guilds.set_main_channel(guild.id, new_channel.id)
            command_mention = get_command_mention(
                self.bot,
                cog="Guild",
                slash_command="guild",
                slash_command_group="set_channel",
            )
            embed = discord.Embed(
                description=(
                    f"⛔CONFIG ERROR⛔: The main channel has been deleted, Use System Channel.\n"
                    f"If you want to change the main channel, use {command_mention}"
                ),
                color=DISCORD_EMBED_COLOR_DANGER,
            )
            await new_channel.send(embed=embed)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Repairing the main channel failed")
