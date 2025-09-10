# Standard Library
import asyncio
import json
from urllib.parse import quote_plus

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks

# Demolizzen
from demolizzen import __github_url__, __title__, __version__, models
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen
from demolizzen.utils.functions import application_cooldown

from .objects import KillmailManager, Subscription

REQUESTS_TIMEOUT = 30
REDISQ_LOCK_TIMEOUT = 5
TTW_TIMEOUT = 5  # Time to wait for new mails in seconds
ZKILLBOARD_URL = "https://zkillredisq.stream/listen.php"

MAIL_LOCK = asyncio.Lock()

# ------------- Fork from Firetail and continued Coding ---------------


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
        self.subs = {}
        self.ws_task = None
        self.km_counter = 0
        self.km_fetched = 0
        self.prepare = self.bot.loop.create_task(self.prepare_subs())
        self.cleanup_killmail_storage.start()
        self.clean_subscriptions.start()

    killmail = SlashCommandGroup(
        "killmail", "zKillboard", contexts=[discord.InteractionContextType.guild]
    )

    def cog_unload(self):
        self.cleanup_killmail_storage.cancel()
        self.clean_subscriptions.cancel()
        self.ws_task.cancel()

    @tasks.loop(minutes=360)
    async def cleanup_killmail_storage(self):
        """Clear the in-memory cache of sent killmails every 6 hours to prevent memory bloat."""
        try:
            Subscription.killmail_sent_per_channel.clear()
        # pylint: disable=broad-except
        except Exception as e:
            self.bot.logger.error(f"[Loop] Killmail Cleaner • {e}")

    @tasks.loop(hours=23)
    async def clean_subscriptions(self):
        """Check if the channels for the subscriptions still exists."""
        killmail_subs = [
            s
            async for s in models.ZKillboard.objects.select_related(
                "guild", "owner"
            ).all()
        ]
        if killmail_subs:
            for subscription in killmail_subs:
                channel = self.bot.get_channel(subscription.channel_id)
                if not channel:
                    await self.remove_bad_channel(subscription)
                    continue

    @clean_subscriptions.before_loop
    async def before_clean_subscriptions(self):
        await self.bot.wait_until_ready()
        self.bot.logger.info("Killmail Subs Checker Ready")

    @cleanup_killmail_storage.before_loop
    async def before_cleanup_killmail_storage(self):
        await self.bot.wait_until_ready()
        self.bot.logger.info("Killmail Memory Cleaner Ready")

    async def add_sub(
        self,
        channel_id: int,
        user_profile: models.UserProfile,
        group_id: int = 6,
        losses: bool = True,
        threshold: int = None,
    ):
        if threshold is None:
            threshold = 1  # Default threshold if not provided

        try:
            guild_profile = await models.GuildProfile.objects.aget(
                pk=user_profile.guild_id
            )

        except models.GuildProfile.DoesNotExist:
            self.bot.logger.error(f"GuildProfile not found for user {user_profile}")
            return False

        sub_obj = await models.ZKillboard.objects.acreate(
            channel_id=channel_id,
            losses=losses,
            threshold=threshold,
            owner=user_profile,
            guild=guild_profile,
            group_id=group_id,
        )
        if sub_obj is None:
            self.bot.logger.error(
                f"Failed to add subscription for channel {channel_id} with group {group_id} and threshold {threshold}"
            )
            return False

        sub = Subscription(
            sub_obj.pk,
            self.bot.get_channel(channel_id),
            threshold,
            losses,
            group_id,
        )
        self.subs[sub.id] = sub
        return True

    async def prepare_subs(self):
        await self.bot.wait_until_ready()
        self.bot.logger.debug("Preparing killmail subs.")

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

        self.ws_task = self.bot.loop.create_task(self.listen_for_mails())

    def process_mail(self, killmail_data):
        killmail = KillmailManager._create_from_zkb(
            zkb_package=killmail_data, esi_data=self.bot.esi_data
        )
        if killmail and killmail.zkb.is_npc:
            return
        if killmail:
            asyncio.gather(*[sub.mail(killmail) for sub in self.subs.values()])

    async def listen_for_mails(self):
        self.bot.logger.debug("Listening for killmails.")
        while True:
            try:
                result = await self.get_new_mail_with_status()
                await asyncio.sleep(1)  # Small delay to avoid rate limiting
                if result == 0:
                    self.bot.logger.info("No new killmails. Pausing for 1 minute.")
                    self.bot.logger.info(f"Killmails Processed: {self.km_counter:,}")
                    self.km_fetched = 0
                    await asyncio.sleep(60)
            except (json.JSONDecodeError, KeyError):
                self.bot.logger.exception("Killmail data was badly formed.")
            except MailProcessingError as e:
                self.bot.logger.exception(f"Killmail Error: {e}")

    async def get_new_mail_with_status(self):
        params = {
            "queueID": quote_plus(f"demolizzen_{self.bot.user.id}"),
            "ttw": TTW_TIMEOUT,
        }
        headers = {
            "User-Agent": f"{__title__}/{__version__} ({__github_url__})",
        }

        if MAIL_LOCK.locked():
            self.bot.logger.debug(
                "Killmail: Lock is active, skipping get_new_mail call."
            )
            return None

        async def request_with_lock():
            async with MAIL_LOCK:
                try:
                    async with self.bot.session.get(
                        ZKILLBOARD_URL,
                        params=params,
                        headers=headers,
                        timeout=REQUESTS_TIMEOUT,
                    ) as resp:
                        status_code = resp.status
                        if status_code == 200:
                            data = await resp.json()
                            # self.bot.logger.debug(json.dumps(data.get("package", {}), indent=4))

                            if data["package"]:
                                self.km_counter += 1
                                self.km_fetched += 1
                                self.process_mail(data["package"])
                            return 200

                        if status_code == 0:
                            return 0

                        if status_code in [522, 504, 502, 500]:  # Server errors
                            self.bot.logger.info(f"HTTP-Statuscode {status_code}")
                            return 0

                        if status_code == 429:
                            self.bot.logger.info(f"HTTP-Statuscode {status_code}")
                            self.bot.logger.info(f"{resp}")
                            return 0
                        self.bot.logger.info(
                            f"Unbekannter HTTP-Statuscode: {status_code}"
                        )
                        return 0
                except asyncio.TimeoutError:
                    pass
                except Exception as exc:
                    raise MailProcessingError from exc
            return None

        try:
            return await asyncio.wait_for(request_with_lock(), timeout=30)
        except asyncio.TimeoutError:
            self.bot.logger.warning(
                "Killmail: Anfrage hat den Lock-Timeout (30s) überschritten und wurde abgebrochen."
            )
            return None

    async def remove_bad_channel(self, subscription: models.ZKillboard):
        try:
            zk_channel = await models.ZKillboard.objects.select_related(
                "guild", "owner"
            ).aget(id=subscription.id)
        except models.ZKillboard.DoesNotExist:
            self.bot.logger.error(f"Failed to remove bad channel {subscription}")
            return False
        await zk_channel.adelete()
        self.bot.logger.info(
            f"Killmail - Bad Channel {zk_channel} removed successfully"
        )
        return True

    @killmail.command(name="subscription")
    async def km(
        self, ctx: discord.ApplicationContext, *, channel: discord.TextChannel = None
    ):
        """
        Show the current channel's killmail subscriptions.
        """

        try:
            channel = channel or ctx.channel
            subscription_obj = [
                s async for s in models.ZKillboard.objects.filter(channel_id=channel.id)
            ]

            subs = []
            sub_text = ""

            if subscription_obj:
                for subscription in subscription_obj:
                    sub_text += f"`{subscription.pk}`: Kills"
                    if subscription.losses:
                        sub_text += " and Losses"
                    if subscription.threshold:
                        sub_text += f" over `{subscription.threshold:,}` ISK - "
                    if subscription.group_id and subscription.group_id != 6:
                        sub_text += f" matching ID `{subscription.group_id}`\n"

            if not subscription_obj:
                sub_text = "There's no subs for this channel."

            subs.append(sub_text)
            embed = discord.Embed(
                title=f"Killmails for <#{channel.id}>",
                description=sub_text,
                color=discord.Color.green(),
            )
            await ctx.respond(embed=embed)
        # pylint: disable=broad-except
        except Exception as e:
            self.bot.logger.error(f"[KM Subscription Command] • {e}")
            em = discord.Embed(
                color=discord.Color.red(),
                description="❌ An error occurred, please try again later.",
            )
            await ctx.respond(embed=em, ephemeral=True)
            return

    @km.error
    async def command_cooldown(self, ctx: discord.ApplicationContext, error):
        await application_cooldown(ctx, error)

    @killmail.command(name="add")
    @checks.is_mod()
    @option("match_id", description="Alliance ID, Corp ID, Region ID or System ID")
    @option("threshold", description="ISK threshold", required=False)
    @option("include_losses", description="Bool: True or False", required=False)
    async def add_killmail(
        self,
        ctx: discord.ApplicationContext,
        match_id: int,
        threshold: int,
        include_losses: bool = False,
    ):
        """
        Add a new killmail subscription to the channel.
        """
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

        added = await self.add_sub(
            channel_id=ctx.channel.id,
            user_profile=user_profile,
            group_id=match_id,
            losses=losses,
            threshold=threshold,
        )
        if not added:
            await ctx.respond(
                "Failed to add killmail subscription.",
                ephemeral=True,
            )
            return
        await ctx.respond("Killmail subscription added!", ephemeral=True)

    @killmail.command(name="clear")
    @checks.is_mod()
    @option("sub_id", description="Subscription ID", required=False)
    async def killmail_clear(self, ctx: discord.ApplicationContext, sub_id: int = None):
        """
        Clear all killmails for the channel or individually remove with subscription IDs.
        """
        try:
            if sub_id:
                try:
                    subscription = await models.ZKillboard.objects.aget(pk=sub_id)
                except models.ZKillboard.DoesNotExist:
                    await ctx.respond(
                        f"ID {sub_id} does not match any of your killmail subscriptions.",
                        ephemeral=True,
                    )
                    return

                if not subscription:
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

            deleted = [
                s
                async for s in models.ZKillboard.objects.filter(
                    channel_id=ctx.channel.id
                )
            ]
            if not deleted:
                await ctx.respond(
                    f"No killmail subs for <#{ctx.channel.id}>.",
                    ephemeral=True,
                )
                return False

            for sub in deleted:
                await sub.adelete()

            rm_ids = [
                sub.id for sub in self.subs.values() if sub.channel.id == ctx.channel.id
            ]
            for rm_id in rm_ids:
                del self.subs[rm_id]

            await ctx.respond(
                f"All killmail subs removed for <#{ctx.channel.id}>.\nYou may encounter additional killmails in the message queue that have already been submitted and partially processed.",
                ephemeral=True,
            )
        # pylint: disable=broad-except
        except Exception as e:
            self.bot.logger.error(f"[Clear Command] • {e}")
            await ctx.respond(
                "Es ist ein Fehler aufgetreten, versuche es später erneut",
                ephemeral=True,
            )
            return

    @killmail.command(name="counter")
    async def killmail_counter(self, ctx):
        """
        Show how many Killmails already Processed
        """
        await ctx.respond(f"Killmails Processed: `{self.km_counter:,}`")

    @killmail_counter.error
    async def killmail_cooldown(self, ctx, error):
        await application_cooldown(ctx, error)
