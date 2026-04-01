# Standard Library
import asyncio
import json
import logging
from http import HTTPStatus

# Third Party
from aiohttp import ClientResponse, ClientTimeout

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks
from discord.ui import View

# Django
from django.core.cache import cache

# Demolizzen
from demolizzen import __title__, __user_agent__, models
from demolizzen.constants import (
    PAGE_SIZE,
    RETRY_DELAY,
    ZKILLBOARD_R2Z2_SEQUENCE_URL,
    ZKILLBOARD_R2Z2_URL,
)
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen

from .killmailmanager import KillmailManager, Subscription

REQUESTS_TIMEOUT = ClientTimeout(connect=5, total=30)
USER_AGENT = {"User-Agent": f"{__user_agent__})"}
MAIL_LOCK = asyncio.Lock()

logger = logging.getLogger(__name__)


class MailProcessingError(Exception):
    pass


class Killmail(commands.Cog):
    """
    Killboard Fetcher - Send new Killmails from zKill
    """

    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.title = "zKillboard"
        self.alias = "killmail"
        # ZKB R2Z2 Tracking
        self.subs: dict[int, Subscription] = {}
        self.km_counter = 0
        self.sequence_id = None
        # Loops
        self.cleanup_killmail_storage.start()
        self.clean_subscriptions.start()
        self.zkillboard_watcher.start()

    killmail = SlashCommandGroup(
        "killmail",
        "zKillboard",
        contexts=[discord.InteractionContextType.guild],
        default_member_permissions=discord.Permissions(manage_guild=True),
    )

    def cog_unload(self):
        self.cleanup_killmail_storage.cancel()
        self.clean_subscriptions.cancel()
        self.zkillboard_watcher.cancel()

    @tasks.loop(minutes=360)
    async def cleanup_killmail_storage(self):
        """Clear the in-memory cache of sent killmails every 6 hours to prevent memory bloat."""
        try:
            Subscription.killmail_sent_per_channel.clear()
        # pylint: disable=broad-except
        except Exception as e:
            logger.error(f"[Loop] Killmail Cleaner • {e}")

    @tasks.loop(hours=23)
    async def clean_subscriptions(self):
        """Check if the channels for the subscriptions still exists."""
        cached_ids = [sub.channel.id for sub in self.subs.values()]
        killmail_subs = [
            s
            async for s in models.ZKillboard.objects.select_related(
                "guild", "owner"
            ).all()
        ]
        existing_ids = [sub.channel_id for sub in killmail_subs]

        # Remove subscriptions from memory that no longer exist in the database
        for cid in cached_ids:
            if cid not in existing_ids:
                rm_ids = [
                    sub_id for sub_id, sub in self.subs.items() if sub.channel.id == cid
                ]
                for rm_id in rm_ids:
                    logger.info(f"Removing stale subscription {rm_id} from memory.")
                    del self.subs[rm_id]

        if killmail_subs:
            for subscription in killmail_subs:
                channel = self.bot.get_channel(subscription.channel_id)
                if not channel:
                    await self.remove_bad_channel(subscription)
                    continue

    @clean_subscriptions.before_loop
    async def before_clean_subscriptions(self):
        await self.bot.wait_until_ready()
        logger.info("Killmail Subs Checker Ready")

    @cleanup_killmail_storage.before_loop
    async def before_cleanup_killmail_storage(self):
        await self.bot.wait_until_ready()
        logger.info("Killmail Memory Cleaner Ready")

    @tasks.loop(seconds=30, reconnect=True, overlap=False)
    async def zkillboard_watcher(self):
        """Watches the zKillboard R2Z2 endpoint for new killmails and processes them."""
        try:
            await self.listen_for_mails()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception(f"Error in zkillboard_watcher loop: {e}")

    @zkillboard_watcher.before_loop
    async def before_zkillboard_watcher(self):
        await self.bot.wait_until_ready()

        killmail_subs = [s async for s in models.ZKillboard.objects.all()]
        for subscription in killmail_subs:
            channel = self.bot.get_channel(subscription.channel_id)
            if not channel:
                await self.remove_bad_channel(subscription)
                continue

            sub = Subscription(
                subscription.pk,
                channel,
                subscription.threshold,
                subscription.losses,
                subscription.group_id,
            )
            self.subs[sub.id] = sub
        logger.info("ZKillboard Watcher Ready")

    @zkillboard_watcher.error
    async def zkillboard_watcher_error(self, error):
        logger.error(f"Error in zkillboard_watcher loop: {error}")
        self.sequence_id = (
            None  # Reset sequence ID to fetch a new one on next loop iteration
        )

    @staticmethod
    async def _wait_for_free_slot():
        """Waits for a free slot in the killmail processing to respect rate limits before making a new request."""
        retry_after = cache.get(f"{__title__.upper()}_RETRY_AT")
        if retry_after is not None:
            logger.debug(
                f"Waiting for {retry_after:.2f} seconds before retrying killmail fetch due to previous rate limit."
            )
            await asyncio.sleep(retry_after)
        await asyncio.sleep(0)  # No wait needed, return immediately

    @staticmethod
    def _too_many_requests_delay(response: ClientResponse) -> bool:
        """
        Handles HTTP 429 Too Many Requests responses from ZKB.
        If the response includes a 'Retry-After' header, sets a delay in the cache and returns True to indicate the operation should be retried later.
        If the header is missing, uses a default delay value.
        Returns False if the response status is not 429, indicating the operation can continue.
        """
        if response.status == HTTPStatus.TOO_MANY_REQUESTS:
            try:
                wait_time = int(response.headers.get("Retry-After", RETRY_DELAY))
                logger.debug(
                    "Received 429 Too Many Requests. Retrying after %s seconds.",
                    wait_time,
                )
            except (TypeError, ValueError):
                logger.debug(
                    "Received 429 Too Many Requests without Retry-After header. Waiting default %s seconds.",
                    RETRY_DELAY,
                )
                wait_time = RETRY_DELAY
            # Set the retry after time in cache
            cache.set(
                key=f"{__title__.upper()}_RETRY_AT",
                value=wait_time,
                timeout=wait_time + 60,
            )
            return True
        return False

    async def listen_for_mails(self):
        """Continuously listens for new killmails from the ZKB R2Z2 endpoint and processes them."""
        logger.debug("Listening for killmails.")
        await self._wait_for_free_slot()  # Ensure we respect any existing rate limit before starting
        self.sequence_id = await self.get_sequence_from_r2z2()

        if not self.sequence_id:
            logger.debug("No Sequence ID received from zKB R2Z2.")
            return

        while True:
            try:
                await asyncio.sleep(0.2)  # Small delay to avoid rate limiting
                result = await self.create_zkb_from_sequence(
                    sequence_id=self.sequence_id
                )
                if result == 0:
                    logger.debug("No new killmails. Pausing for 10 seconds.")
                    logger.debug(f"Killmails Processed: {self.km_counter:,}")
                    self.km_counter = 0
                    await asyncio.sleep(10)
            except (json.JSONDecodeError, KeyError):
                logger.exception("Killmail data was badly formed.")
            except MailProcessingError as e:
                logger.exception(f"Killmail Error: {e}")

    def process_mail(self, killmail_data):
        killmail = KillmailManager._create_from_zkb(
            zkb_package=killmail_data, bot=self.bot
        )
        if killmail and killmail.zkb.is_npc:
            return
        if killmail:
            asyncio.gather(*[sub.mail(killmail) for sub in self.subs.values()])

    async def get_sequence_from_r2z2(self) -> int | None:
        """Fetches and returns a sequence ID from ZKB R2Z2 endpoint.

        Returns None if no sequence is received.
        """
        await asyncio.sleep(delay=0.5)
        logger.debug("Trying to fetch sequence from ZKB R2Z2...")
        try:
            async with self.bot.session.get(
                ZKILLBOARD_R2Z2_SEQUENCE_URL,
                headers=USER_AGENT,
                timeout=REQUESTS_TIMEOUT,
            ) as response:
                data = await response.json()

                if self._too_many_requests_delay(response=response):
                    return None

                if data and "sequence" in data:
                    sequence_id = data["sequence"]
                    logger.debug("Received sequence from ZKB R2Z2: %s", sequence_id)
                    return sequence_id
        except asyncio.TimeoutError:
            logger.warning("Timeout while fetching sequence from ZKB R2Z2.")
            return None
        except Exception as exc:
            logger.error(f"Error while fetching sequence from ZKB R2Z2: {exc}")
            return None
        logger.debug("No sequence received from ZKB R2Z2.")
        return None

    async def create_zkb_from_sequence(self, sequence_id: int):
        if MAIL_LOCK.locked():
            logger.debug("Killmail: Lock is active, skipping get_new_mail call.")
            return None

        async def request_with_lock():
            async with MAIL_LOCK:
                try:
                    async with self.bot.session.get(
                        ZKILLBOARD_R2Z2_URL + str(sequence_id) + ".json",
                        timeout=REQUESTS_TIMEOUT,
                        headers=USER_AGENT,
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data and "killmail_id" in data:
                                self.process_mail(data)
                                self.km_counter += 1
                                self.sequence_id += 1
                            return 200

                        if response.status == HTTPStatus.NOT_FOUND:
                            logger.debug(
                                f"No new Killmail with sequence ID {sequence_id} found."
                            )
                            return 0

                        if response.status in [
                            HTTPStatus.GATEWAY_TIMEOUT,
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            HTTPStatus.BAD_GATEWAY,
                            HTTPStatus.INTERNAL_SERVER_ERROR,
                        ]:  # Server errors
                            logger.info(
                                f"Server error with status code {response.status} when fetching killmail with sequence ID {sequence_id}. Retrying after delay."
                            )
                            return 0

                        if self._too_many_requests_delay(response=response):
                            return 0

                        logger.info(f"Unknown HTTP-Statuscode: {response.status}")
                        return 0
                except asyncio.TimeoutError:
                    pass
                except Exception as exc:
                    raise MailProcessingError from exc
            return None

        try:
            return await asyncio.wait_for(request_with_lock(), timeout=30)
        except asyncio.TimeoutError:
            logger.warning(
                "Killmail: Anfrage hat den Lock-Timeout (30s) überschritten und wurde abgebrochen."
            )
            return None

    async def remove_bad_channel(self, subscription: models.ZKillboard):
        try:
            zk_channel = await models.ZKillboard.objects.select_related(
                "guild", "owner"
            ).aget(id=subscription.id)
        except models.ZKillboard.DoesNotExist:
            logger.error(f"Failed to remove bad channel {subscription}")
            return False
        await zk_channel.adelete()
        logger.info(f"Killmail - Bad Channel {zk_channel} removed successfully")
        return True

    @killmail.command(name="subscription")
    @option(
        "channel",
        description="The channel to show the subscriptions for",
        required=False,
    )
    async def subscription_killmail(
        self, ctx: discord.ApplicationContext, channel: discord.TextChannel
    ):
        """Show all killmail subscriptions of the guild, optional channel."""
        try:
            if channel is None:
                subscription_obj = [
                    s
                    async for s in models.ZKillboard.objects.select_related(
                        "guild"
                    ).filter(guild__guild_id=ctx.guild.id)
                ]
            else:
                subscription_obj = [
                    s
                    async for s in models.ZKillboard.objects.filter(
                        channel_id=channel.id
                    )
                ]

            if not subscription_obj:
                await ctx.respond("No subscriptions found.", ephemeral=True)
                return

            # Prepare the subscriptions as text blocks
            entries = []
            for sub in subscription_obj:
                # Channel-Name oder None
                ch = self.bot.get_channel(sub.channel_id)
                ch_name = ch.mention if ch else "None"
                line = f"`{sub.pk}`: {ch_name} | Kills"
                if sub.losses:
                    line += " and Losses"
                if sub.threshold:
                    line += f" over `{sub.threshold:,}` ISK"
                if sub.group_id and sub.group_id != 6:
                    line += f" | matching ID `{sub.group_id}`"
                entries.append(line)

            pages = [
                entries[i : i + PAGE_SIZE] for i in range(0, len(entries), PAGE_SIZE)
            ]

            if len(pages) == 1:
                embed = discord.Embed(
                    title="Killmail-Subscriptions",
                    description="\n".join(pages[0]),
                    color=discord.Color.green(),
                )
                await ctx.respond(embed=embed)
            else:

                class PaginatorView(View):
                    def __init__(self, pages):
                        super().__init__(timeout=60)
                        self.pages = pages
                        self.current = 0
                        self.message = None

                    async def update(self, interaction):
                        embed = discord.Embed(
                            title=f"Killmail-Subscriptions (Site {self.current + 1}/{len(self.pages)})",
                            description="\n".join(self.pages[self.current]),
                            color=discord.Color.green(),
                        )
                        await interaction.response.edit_message(embed=embed, view=self)

                    @discord.ui.button(
                        label="Back", style=discord.ButtonStyle.secondary
                    )
                    async def back(self, __, interaction):
                        if self.current > 0:
                            self.current -= 1
                            await self.update(interaction)

                    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
                    async def next(self, __, interaction):
                        if self.current < len(self.pages) - 1:
                            self.current += 1
                            await self.update(interaction)

                view = PaginatorView(pages)
                embed = discord.Embed(
                    title=f"Killmail-Subscriptions (Site 1/{len(pages)})",
                    description="\n".join(pages[0]),
                    color=discord.Color.green(),
                )
                await ctx.respond(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Error in subscription_killmail: {e}")
            em = discord.Embed(
                color=discord.Color.red(),
                description="An error occurred while fetching subscriptions. Please try again later.",
            )
            await ctx.respond(embed=em, ephemeral=True)
            return

    async def add_sub(
        self,
        channel_id: int,
        user_profile: models.UserProfile,
        group_id: int = 6,
        losses: bool = True,
        threshold: int = None,
    ) -> tuple[bool, bool]:
        """Add a new killmail subscription to the database and memory."""
        if threshold is None:
            threshold = 1  # Default threshold if not provided

        try:
            guild_profile = await models.GuildProfile.objects.aget(
                pk=user_profile.guild_id
            )

        except models.GuildProfile.DoesNotExist:
            logger.error(f"GuildProfile not found for user {user_profile}")
            return False, False

        sub_obj, created = await models.ZKillboard.objects.aget_or_create(
            channel_id=channel_id,
            group_id=group_id,
            owner=user_profile,
            guild=guild_profile,
            defaults={"losses": losses, "threshold": threshold},
        )

        if sub_obj is None:
            logger.debug(
                f"Failed to add subscription for channel {channel_id} with group {group_id} and threshold {threshold}"
            )
            return False, created

        if not created:
            logger.debug(
                f"Subscription already exists for channel {channel_id} with group {group_id} and threshold {threshold}"
            )
            return True, created

        sub = Subscription(
            sub_obj.pk,
            self.bot.get_channel(channel_id),
            threshold,
            losses,
            group_id,
        )
        self.subs[sub.id] = sub
        return True, created

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
    @option("threshold", description="ISK threshold", required=False)
    @option("include_losses", description="Bool: True or False", required=False)
    async def add_killmail(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel,
        match_id: int,
        threshold: int,
        include_losses: bool = False,
    ):
        """Add a new killmail subscription to a channel."""
        losses = bool(include_losses)
        try:
            user_profile = await models.UserProfile.objects.aget(
                user_id=ctx.author.id,
                guild_id=ctx.guild.id,
            )
        except models.UserProfile.DoesNotExist:
            return await ctx.respond(
                "Failed to add killmail subscription.",
                ephemeral=True,
            )

        # Check if I have permissions to send messages in the channel
        bot_member = await ctx.guild.fetch_member(self.bot.user.id)
        if not channel.permissions_for(bot_member).send_messages:
            return await ctx.respond(
                f"Killmail subscriptions cannot be added to {channel.mention}, as I lack permission to send messages there.",
                ephemeral=True,
            )

        added, created = await self.add_sub(
            channel_id=channel.id,
            user_profile=user_profile,
            group_id=match_id,
            losses=losses,
            threshold=threshold,
        )

        if not added:
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
        channel: discord.TextChannel,
        sub_id: int = None,
    ):
        """Remove all killmail subscriptions for the channel or individually remove with subscription IDs."""
        try:
            if sub_id:
                try:
                    subscription = await models.ZKillboard.objects.select_related(
                        "guild"
                    ).aget(pk=sub_id)
                except models.ZKillboard.DoesNotExist:
                    await ctx.respond(
                        f"ID {sub_id} does not match any of your killmail subscriptions.",
                        ephemeral=True,
                    )
                    return

                if subscription.guild.guild_id != ctx.guild.id:
                    await ctx.respond(
                        f"ID {sub_id} does not match any of your killmail subscriptions.",
                        ephemeral=True,
                    )
                    return

                await subscription.adelete()
                del self.subs[sub_id]
                await ctx.respond(
                    f"Killmail `{sub_id}` has been removed.",
                    ephemeral=True,
                )
                return True

            # If no Channel is provided, use the current channel
            channel = channel or ctx.channel

            # Remove all subscriptions for the channel
            deleted = [
                s async for s in models.ZKillboard.objects.filter(channel_id=channel.id)
            ]
            if not deleted:
                await ctx.respond(
                    f"No killmail subs for <#{channel.id}>.",
                    ephemeral=True,
                )
                return False

            for sub in deleted:
                await sub.adelete()

            rm_ids = [
                sub.id for sub in self.subs.values() if sub.channel.id == channel.id
            ]
            for rm_id in rm_ids:
                del self.subs[rm_id]

            await ctx.respond(
                f"All killmail subs removed for <#{channel.id}>.\nYou may encounter additional killmails in the message queue that have already been submitted and partially processed.",
                ephemeral=True,
            )
        # pylint: disable=broad-except
        except Exception as e:
            logger.error(f"Error in remove_killmail: {e}")
            await ctx.respond(
                "An error occurred, please try again later.",
                ephemeral=True,
            )
            return
