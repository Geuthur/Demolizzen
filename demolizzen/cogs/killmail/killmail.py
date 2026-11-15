"""zKillboard feed: posts new killmails into the channels that subscribed to them."""

# Standard Library
import asyncio
import logging
import time

# Third Party
from aiohttp import ClientTimeout

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks
from discord.ui import View

# Demolizzen
from demolizzen import USER_AGENT_TEXT
from demolizzen.constants import PAGE_SIZE
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog
from demolizzen.services import guilds, killmails
from demolizzen.services.errors import GuildNotRegistered
from demolizzen.services.killmails import SubscriptionRule

from ._feed import KillmailFeed
from .killmailmanager import KillmailManager

REQUESTS_TIMEOUT = ClientTimeout(connect=5, total=30)
USER_AGENT = {"User-Agent": USER_AGENT_TEXT}
PAUSED_NOTICE = (
    "Killmail feed for <#{channel_id}> is paused: I cannot send messages there."
)

logger = logging.getLogger(__name__)


class _Pages(View):
    """Back and Next buttons for a long subscription list."""

    def __init__(self, pages: list[list[str]]):
        super().__init__(timeout=60)
        self.pages = pages
        self.current = 0

    def embed(self) -> discord.Embed:
        title = "Killmail-Subscriptions"
        if len(self.pages) > 1:
            title += f" (Site {self.current + 1}/{len(self.pages)})"
        return discord.Embed(
            title=title,
            description="\n".join(self.pages[self.current]),
            color=discord.Color.green(),
        )

    async def _show(self, interaction: discord.Interaction, page: int):
        if 0 <= page < len(self.pages):
            self.current = page
            await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, __, interaction: discord.Interaction):
        await self._show(interaction, self.current - 1)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next(self, __, interaction: discord.Interaction):
        await self._show(interaction, self.current + 1)


class Killmail(BaseCog):
    """
    Killboard Fetcher - Send new Killmails from zKill
    """

    key = "killmail"

    # Killmails that are looked up and posted at the same time. When all slots
    # are taken the feed waits, so nothing piles up while ESI or Discord is slow.
    MAX_DELIVERIES = 5
    DELIVERY_TIMEOUT = 120
    # A channel that refused a message although the permissions look right is
    # not tried again for this many seconds.
    RETRY_REFUSED_AFTER = 300
    # Killmail ids remembered to recognise one the feed delivers twice.
    REMEMBERED_KILLMAILS = 5000

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
        self.title = "zKillboard"
        self.alias = "killmail"
        self.rules: dict[int, SubscriptionRule] = {}
        self.feed = KillmailFeed(
            lambda: getattr(self.bot, "session", None),
            self.handle_killmail,
            headers=USER_AGENT,
            timeout=REQUESTS_TIMEOUT,
        )
        self._deliveries: set[asyncio.Task] = set()
        self._slots = asyncio.Semaphore(self.MAX_DELIVERIES)
        self._seen: dict[int, None] = {}
        # Channels whose members were told that the feed is paused.
        self._paused: set[int] = set()
        self._retry_at: dict[int, float] = {}
        # Loops
        self.check_subscriptions.start()
        self.zkillboard_watcher.start()

    killmail = SlashCommandGroup(
        "killmail",
        "zKillboard",
        contexts=[discord.InteractionContextType.guild],
        default_member_permissions=discord.Permissions(manage_guild=True),
    )

    def cog_unload(self):
        self.check_subscriptions.cancel()
        self.zkillboard_watcher.cancel()
        for delivery in list(self._deliveries):
            delivery.cancel()

    # ------------------------------------------------------------------ upkeep

    async def load_rules(self) -> None:
        """Read all subscriptions from the database."""
        self.rules = {rule.id: rule for rule in await killmails.load_rules()}

    async def _forget_channel(self, channel_id: int) -> None:
        """Remove the subscriptions of a channel that no longer exists."""
        removed = await killmails.remove_for_channel(channel_id)
        for subscription_id in removed:
            self.rules.pop(subscription_id, None)
        self._paused.discard(channel_id)
        self._retry_at.pop(channel_id, None)
        logger.info(
            "Removed %s killmail subscriptions of deleted channel %s.",
            len(removed),
            channel_id,
        )

    def _channel_is_gone(self, rule: SubscriptionRule) -> bool:
        """Whether the channel was deleted. A guild that is unreachable right
        now says nothing about its channels."""
        guild = self.bot.get_guild(rule.guild_id)
        if guild is None or guild.unavailable:
            return False
        return self.bot.get_channel(rule.channel_id) is None

    # Cleanup must run whether or not the guild had the module enabled.
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        """Remove all subscriptions for a guild when the bot leaves it."""
        removed = await killmails.remove_for_guild(guild.id)
        for subscription_id in removed:
            self.rules.pop(subscription_id, None)
        logger.info(
            "Removed %s killmail subscriptions for guild %s on leave.",
            len(removed),
            guild.id,
        )

    @tasks.loop(hours=23)
    async def check_subscriptions(self):
        """Reload the subscriptions and drop those of deleted channels."""
        try:
            await self.load_rules()
            gone = {
                rule.channel_id
                for rule in self.rules.values()
                if self._channel_is_gone(rule)
            }
            for channel_id in gone:
                await self._forget_channel(channel_id)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Killmail subscription check failed")

    @check_subscriptions.before_loop
    async def before_check_subscriptions(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=KillmailFeed.SUCCESS_DELAY)
    async def zkillboard_watcher(self):
        """Fetch the next killmail and wait as long as the feed asks for."""
        await asyncio.sleep(await self.feed.step())

    @zkillboard_watcher.before_loop
    async def before_zkillboard_watcher(self):
        await self.bot.wait_until_ready()
        try:
            await self.load_rules()
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Killmail subscriptions could not be loaded")
        logger.info("ZKillboard Watcher Ready")

    # ---------------------------------------------------------------- delivery

    def _is_new(self, killmail_id: int) -> bool:
        if killmail_id in self._seen:
            return False
        self._seen[killmail_id] = None
        if len(self._seen) > self.REMEMBERED_KILLMAILS:
            del self._seen[next(iter(self._seen))]
        return True

    async def handle_killmail(self, data: dict) -> None:
        """Check a killmail from the feed against all subscriptions and post it.

        Nothing is looked up for a killmail that no channel asked for.
        """
        killmail = KillmailManager._create_from_zkb(zkb_package=data, bot=self.bot)
        if killmail is None or killmail.zkb.is_npc or not self.rules:
            return
        if not self._is_new(killmail.id):
            return
        targets = await self._targets(killmail)
        if not targets:
            return

        await self._slots.acquire()
        delivery = asyncio.create_task(self._deliver(killmail, targets))
        self._deliveries.add(delivery)
        delivery.add_done_callback(self._deliveries.discard)

    async def _targets(self, killmail: KillmailManager) -> dict[int, bool]:
        """The channels that get the killmail, and whether it is a loss there."""
        region_id = await self.bot.esi_data.get_region_id(killmail.solar_system_id)
        facts = killmail.facts(region_id)
        targets: dict[int, bool] = {}
        enabled: dict[int, bool] = {}
        for rule in list(self.rules.values()):
            if not killmails.matches(rule, facts):
                continue
            if rule.guild_id not in enabled:
                enabled[rule.guild_id] = await self.is_enabled(rule.guild_id)
            if not enabled[rule.guild_id]:
                continue
            targets[rule.channel_id] = targets.get(
                rule.channel_id, False
            ) or killmails.is_loss(rule, facts)
        return targets

    async def _deliver(self, killmail: KillmailManager, targets: dict[int, bool]):
        try:
            await asyncio.wait_for(
                self._post(killmail, targets), timeout=self.DELIVERY_TIMEOUT
            )
        except TimeoutError:
            logger.warning(
                "Killmail %s was not delivered within %s seconds.",
                killmail.id,
                self.DELIVERY_TIMEOUT,
            )
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Killmail %s could not be delivered.", killmail.id)
        finally:
            self._slots.release()

    async def _post(self, killmail: KillmailManager, targets: dict[int, bool]):
        channels = []
        for channel_id, is_loss in targets.items():
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                # Deleted or not reachable right now; the daily check decides.
                continue
            if not self._can_send(channel):
                await self._pause(channel)
                continue
            if time.monotonic() < self._retry_at.get(channel_id, 0):
                continue
            channels.append((channel, is_loss))
        if not channels:
            return

        await killmail.enrich()
        for channel, is_loss in channels:
            await self._send(killmail, channel, is_loss)

    async def _send(self, killmail: KillmailManager, channel, is_loss: bool):
        try:
            await channel.send(embed=killmail.build_embed(is_loss))
        except discord.Forbidden:
            self._retry_at[channel.id] = time.monotonic() + self.RETRY_REFUSED_AFTER
            await self._pause(channel)
        except discord.NotFound:
            await self._forget_channel(channel.id)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception(
                "Killmail %s could not be sent to channel %s.",
                killmail.id,
                channel.id,
            )
        else:
            self._paused.discard(channel.id)
            self._retry_at.pop(channel.id, None)

    @staticmethod
    def _can_send(channel, embeds: bool = True) -> bool:
        me = channel.guild.me
        if me is None:
            return True
        permissions = channel.permissions_for(me)
        return bool(
            permissions.view_channel
            and permissions.send_messages
            and (permissions.embed_links or not embeds)
        )

    async def _pause(self, channel) -> None:
        """Stop posting into a channel the bot may not write to.

        The subscription stays; the guild is told once. Posting resumes by
        itself as soon as a message gets through again.
        """
        if channel.id in self._paused:
            return
        self._paused.add(channel.id)
        logger.info(
            "Killmail feed for channel %s in guild %s is paused: no permission.",
            channel.id,
            channel.guild.id,
        )
        try:
            await self._notify_paused(channel)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception(
                "Could not announce the paused killmail feed of channel %s.",
                channel.id,
            )

    async def _notify_paused(self, channel) -> None:
        guild = channel.guild
        main_channel_id = await guilds.get_main_channel(guild.id)
        candidates = (
            self.bot.get_channel(main_channel_id) if main_channel_id else None,
            guild.system_channel,
        )
        for candidate in candidates:
            if candidate is None or candidate.id == channel.id:
                continue
            if not self._can_send(candidate, embeds=False):
                continue
            try:
                await candidate.send(PAUSED_NOTICE.format(channel_id=channel.id))
            except discord.HTTPException:
                continue
            return

    # ---------------------------------------------------------------- commands

    def _describe(self, rule: SubscriptionRule) -> str:
        channel = self.bot.get_channel(rule.channel_id)
        line = f"`{rule.id}`: {channel.mention if channel else 'None'} | Kills"
        if rule.losses:
            line += " and Losses"
        if rule.threshold:
            line += f" over `{rule.threshold:,}` ISK"
        if rule.group_id:
            line += f" | matching ID `{rule.group_id}`"
        return line

    @killmail.command(name="subscription")
    @option(
        "channel",
        description="The channel to show the subscriptions for",
        required=False,
    )
    async def subscription_killmail(
        self, ctx: discord.ApplicationContext, channel: discord.TextChannel = None
    ):
        """Show all killmail subscriptions of the guild, optional channel."""
        rules = await killmails.rules_for_guild(ctx.guild.id)
        if channel is not None:
            rules = [rule for rule in rules if rule.channel_id == channel.id]
        if not rules:
            await ctx.respond("No subscriptions found.", ephemeral=True)
            return

        entries = [self._describe(rule) for rule in rules]
        view = _Pages(
            [entries[i : i + PAGE_SIZE] for i in range(0, len(entries), PAGE_SIZE)]
        )
        if len(view.pages) == 1:
            await ctx.respond(embed=view.embed())
        else:
            await ctx.respond(embed=view.embed(), view=view)

    @killmail.command(name="add")
    @checks.is_guild_manager()
    @option(
        "channel", description="The channel to add the subscription to", required=True
    )
    @option(
        "match_id",
        description="Alliance ID, Corp ID, Region ID or System ID",
        required=True,
    )
    @option("threshold", description="ISK threshold", required=False, min_value=0)
    @option("include_losses", description="Bool: True or False", required=False)
    async def add_killmail(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel,
        match_id: int,
        threshold: int = None,
        include_losses: bool = False,
    ):
        """Add a new killmail subscription to a channel."""
        if not self._can_send(channel):
            await ctx.respond(
                f"Killmail subscriptions cannot be added to {channel.mention}, as I lack permission to send messages there.",
                ephemeral=True,
            )
            return

        try:
            rule, created = await killmails.add_subscription(
                ctx.guild.id,
                ctx.author.id,
                ctx.author.name,
                channel.id,
                match_id,
                threshold=threshold,
                losses=bool(include_losses),
            )
        except GuildNotRegistered:
            await ctx.respond(
                "Failed to add killmail subscription, please try again later.",
                ephemeral=True,
            )
            return

        if not created:
            await ctx.respond(
                "A subscription with the same parameters already exists for this channel.",
                ephemeral=True,
            )
            return
        self.rules[rule.id] = rule
        await ctx.respond("Killmail subscription added!", ephemeral=True)

    @killmail.command(name="remove")
    @checks.is_guild_manager()
    @option(
        "channel",
        description="The channel to remove the subscription from",
        required=False,
    )
    @option("sub_id", description="Subscription ID", required=False)
    async def remove_killmail(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel = None,
        sub_id: int = None,
    ):
        """Remove all killmail subscriptions for the channel or individually remove with subscription IDs."""
        if sub_id:
            if not await killmails.remove_subscription(sub_id, ctx.guild.id):
                await ctx.respond(
                    f"ID {sub_id} does not match any of your killmail subscriptions.",
                    ephemeral=True,
                )
                return
            self.rules.pop(sub_id, None)
            await ctx.respond(f"Killmail `{sub_id}` has been removed.", ephemeral=True)
            return

        # If no Channel is provided, use the current channel
        channel = channel or ctx.channel
        removed = await killmails.remove_for_channel(channel.id)
        if not removed:
            await ctx.respond(f"No killmail subs for <#{channel.id}>.", ephemeral=True)
            return
        for subscription_id in removed:
            self.rules.pop(subscription_id, None)
        self._paused.discard(channel.id)
        self._retry_at.pop(channel.id, None)
        await ctx.respond(
            f"All killmail subs removed for <#{channel.id}>.\nYou may encounter additional killmails in the message queue that have already been submitted and partially processed.",
            ephemeral=True,
        )
