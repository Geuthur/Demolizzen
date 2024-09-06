import asyncio
import json
import logging

import discord
import websockets
from core import checks
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks
from settings import db
from settings.functions import application_cooldown, convert_to_bool

from .objects import Mail, Subscription

log = logging.getLogger("killboard")
log_test = logging.getLogger("testing")

REQUESTS_TIMEOUT = 30

get_new_mail_lock = asyncio.Lock()

# ------------- Fork from Firetail and continued Coding ---------------


class MailProcessingError(Exception):
    pass


class Killmail(commands.Cog):
    """
    Killboard Fetcher - Send new Killmails from zKill
    """

    def __init__(self, bot):
        self.bot = bot
        self.title = "zKillboard"
        self.alias = "killmail"
        self.subs = {}
        self.ws_task = None
        self.km_counter = 0
        self.prepare = self.bot.loop.create_task(self.prepare_subs())
        self.clean_killmailvar.start()
        self.clean_subscriptions.start()

    killmail = SlashCommandGroup(
        "killmail", "zKillboard", contexts=[discord.InteractionContextType.guild]
    )

    def cog_unload(self):
        self.clean_killmailvar.cancel()
        self.clean_subscriptions.cancel()
        self.ws_task.cancel()

    @tasks.loop(minutes=360)
    async def clean_killmailvar(self):
        log.debug("Killmail Unique Checker Ready")
        try:
            Subscription.killmail_sent_per_channel.clear()
        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"[Loop] Killmail Cleaner • {e}")

    @tasks.loop(hours=23)
    async def clean_subscriptions(self):
        log.debug("Killmail Subs Checker Ready")
        try:
            killboard_subs = await self.get_subs()
            if killboard_subs:
                for sub_data in killboard_subs:
                    _, channel_id, _, losses, threshold, ownerid, group_id = sub_data
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        await self.remove_bad_channel(
                            channel_id, _, losses, threshold, ownerid, group_id
                        )
                        continue
        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"[Loop] Killmail Subscription Checker • {e}")

    @clean_subscriptions.before_loop
    async def before_daily_update(self):
        await self.bot.wait_until_ready()

    @staticmethod
    async def get_subs(*, channel_id: int = None, sub_id: int = None):
        sql = "SELECT id, channelid, serverid, losses, threshold, ownerid, groupid FROM zKillboard"
        if sub_id:
            sql += " WHERE id = :id"
            result = await db.select_var(sql, {"id": sub_id})
            if result:
                return result[0]
            return None

        if channel_id:
            sql += " WHERE channelid = :channel_id"
            return await db.select_var(sql, {"channel_id": channel_id})

        return await db.select(sql)

    async def add_sub(
        self,
        channel_id: int,
        server_id: int,
        owner_id: int,
        group_id: int = 6,
        losses: str = "true",
        threshold: int = 1,
    ):
        sql = "INSERT INTO zKillboard (channelid, serverid, groupid, ownerid, losses, threshold) VALUES (:channelid, :serverid, :groupid, :ownerid, :losses, :threshold)"
        val = {
            "channelid": channel_id,
            "serverid": server_id,
            "groupid": group_id,
            "ownerid": owner_id,
            "losses": losses,
            "threshold": {threshold or 1},
        }
        id_ = await db.execute_sql(sql, val)
        sub = Subscription(
            id_,
            self.bot.get_channel(channel_id),
            threshold,
            convert_to_bool(losses),
            group_id,
        )
        self.subs[sub.id] = sub

    async def prepare_subs(self):
        await self.bot.wait_until_ready()
        log.debug("Preparing killmail subs.")

        killboard_subs = await self.get_subs()
        for sub_data in killboard_subs:
            id_, channel_id, _, losses, threshold, ownerid, group_id = sub_data
            channel = self.bot.get_channel(channel_id)
            if not channel:
                await self.remove_bad_channel(
                    channel_id, _, losses, threshold, ownerid, group_id
                )
                continue

            sub = Subscription(
                id_, channel, threshold, convert_to_bool(losses), group_id
            )
            self.subs[sub.id] = sub

        self.ws_task = self.bot.loop.create_task(self.listen_for_mails())

    def process_mail(self, killmail_data):
        killmail_data["killmail"]["zkb"] = killmail_data["zkb"]
        mail = Mail(killmail_data["killmail"], self.bot.esi_data)
        if mail.npc:
            return
        asyncio.gather(*[sub.mail(mail) for sub in self.subs.values()])

    def process_mail_websocket(self, killmail_data):
        mail = Mail(killmail_data, self.bot.esi_data)
        if mail.npc:
            return
        asyncio.gather(*[sub.mail(mail) for sub in self.subs.values()])

    async def listen_for_mails(self):
        log.debug("Listening for killmails.")
        while True:
            try:
                # Redis - Store Killmails 3 Hours
                await self.get_new_mail()
                # Websocket - Fetch Killmails while connected
                # await self.get_new_mail_websocket()
            except (json.JSONDecodeError, KeyError):
                log.exception("Killmail data was badly formed.")
            except MailProcessingError as e:
                log.exception(f"Killmail Error: {e}")

    # Get Killmail's over the Redisq Endpoint - Unstable Reachable - But Remind's your already recieved kms
    async def get_new_mail(self):
        # Lock - Prevent 429 Error
        async with get_new_mail_lock:
            url = "https://redisq.zkillboard.com/listen.php"

            params = {
                "queueID": f"demolizzen_{self.bot.user.id}",
                "ttw": 5,
            }

            headers = {
                "User-Agent": "Demolizzen v0.5.6",
            }
            try:
                # log_test.info("Get New Mail")
                async with self.bot.session.get(
                    url, params=params, headers=headers, timeout=REQUESTS_TIMEOUT
                ) as resp:
                    status_code = resp.status  # Hier wird der HTTP-Statuscode abgerufen
                    # log_test.info(f"HTTP-Statuscode: {status_code}")
                    # log_test.info(resp)
                    if status_code == 200:
                        data = await resp.json()
                        # log_test.debug(json.dumps(data['package'], indent=4))
                        if data["package"]:
                            log_test.debug("Killmail Data Fetched")
                            self.km_counter += 1
                            self.process_mail(data["package"])
                    elif status_code == 0:
                        log.info("Keine neuen Daten")
                        log.info("Warte 1 Minute...")
                        await asyncio.sleep(60)
                    elif status_code in [522, 504, 502, 500]:
                        log.info(f"HTTP-Statuscode {status_code}")
                        log.info("Warte 30 Minuten...")
                        await asyncio.sleep(1800)
                    elif status_code == 429:
                        log.info(f"HTTP-Statuscode {status_code}")
                        log.info(f"{resp}")
                        log.info("Warte 30 Minuten...")
                        await asyncio.sleep(1800)
                    else:
                        log.info(f"Unbekannter HTTP-Statuscode: {status_code}")
                        log.info("Warte 15 Minuten...")
                        await asyncio.sleep(900)
            except asyncio.TimeoutError:
                pass
            # pylint: disable=broad-except
            except Exception:
                # pylint:: disable=raise-missing-from
                raise MailProcessingError

    # Get Killmails over the Websocket Endpoint - Good Reachable but only Fetch at the Point it started.
    async def get_new_mail_websocket(self):
        error_count = 0
        while True:
            try:
                uri = "wss://zkillboard.com/websocket/"
                async with websockets.connect(uri) as websocket:
                    subscription_message = json.dumps(
                        {"action": "sub", "channel": "killstream"}
                    )
                    await websocket.send(subscription_message)
                    response = await websocket.recv()

                    data = json.loads(response)

                    # Log Killmails
                    log.debug(json.dumps(data, indent=4))

                    self.km_counter += 1
                    self.process_mail_websocket(data)
                    error_count = 0
                    log.debug(f"Received {self.km_counter} new killmails.")
            # pylint: disable=broad-except
            except Exception as e:
                if error_count > 3:
                    log.info(f"Error: {e}")
                error_count += 1
                await asyncio.sleep(30)

    @staticmethod
    async def remove_bad_channel(
        channel_id, serverid, losses, threshold, ownerid, group_id
    ):
        sql = "DELETE FROM zKillboard WHERE channelid = (:channelid)"
        values = {"channelid": channel_id}
        await db.execute_sql(sql, values)
        log.error(
            f"Killmail - Bad Channel {channel_id} removed successfully - Server: {serverid} -  Owner: {ownerid} - Group: {group_id} - Losses: {losses} - Threshold: {threshold}"
        )

    @killmail.command(name="subscription")
    async def km(
        self, ctx: discord.ApplicationContext, *, channel: discord.TextChannel = None
    ):
        """
        Show the current channel's killmail subscriptions.
        """

        try:
            channel = channel or ctx.channel
            subs_data = await self.get_subs(channel_id=channel.id)

            subs = []
            sub_text = ""

            if subs_data:
                for sub_data in subs_data:
                    id_, _, _, losses, threshold, _, group_id = sub_data
                    sub_text += f"`{id_}`: Kills"
                    if convert_to_bool(losses):
                        sub_text += " and Losses"
                    if threshold:
                        sub_text += f" over `{threshold:,}` ISK - "
                    if group_id and group_id != 6:
                        sub_text += f" matching ID `{group_id}`\n"

            if not subs_data:
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
            log.error(f"[KM Subscription Command] • {e}")
            em = discord.Embed(
                color=discord.Color.red(),
                description="❌ An error occurred, please try again later.",
            )
            await ctx.respond(embed=em, ephemeral=True, delete_after=10)
            return

    @km.error
    async def command_cooldown(self, ctx, error):
        await application_cooldown(ctx, error)

    @killmail.command(name="add")
    @checks.is_mod()
    @option("match_id", description="Alliance ID, Corp ID, Region ID or System ID")
    @option("threshold", description="ISK threshold", required=False)
    @option("include_losses", description="Bool: True or False", required=False)
    async def add_killmail(
        self, ctx, match_id: int, threshold: int, include_losses: bool = False
    ):
        """
        Add a new killmail subscription to the channel.
        """
        losses = "true" if include_losses else "false"
        await self.add_sub(
            ctx.channel.id, ctx.guild.id, ctx.author.id, match_id, losses, threshold
        )
        await ctx.respond("Killmail subscription added!", delete_after=15)

    @killmail.command(name="clear")
    @checks.is_mod()
    @option("sub_id", description="Subscription ID", required=False)
    async def killmail_clear(self, ctx: discord.ApplicationContext, sub_id: int = None):
        """
        Clear all killmails for the channel or individually remove with subscription IDs.
        """
        try:
            if sub_id:
                sub = await self.get_subs(sub_id=sub_id)

                if not sub:
                    await ctx.respond(
                        f"ID {sub_id} does not match any of your killmail subscriptions.",
                        ephemeral=True,
                    )
                    return
                _, _, server_id, _, _, _ = sub
                if server_id != ctx.guild.id:
                    await ctx.respond(
                        f"ID {sub_id} does not match any of your killmail subscriptions.",
                        ephemeral=True,
                    )
                    return
                sql = "DELETE FROM zKillboard WHERE id = :id"
                await db.execute_sql(sql, {"id": sub_id})
                del self.subs[sub_id]
                await ctx.respond(
                    f"Killmail `{sub_id}` has been removed.", delete_after=15
                )
                return

            sql = "DELETE FROM zKillboard WHERE channelid = :channelid"
            await db.execute_sql(sql, {"channelid": ctx.channel.id})

            rm_ids = []
            for sub in self.subs.values():
                if sub.channel.id == ctx.channel.id:
                    rm_ids.append(sub.id)
            for rm_id in rm_ids:
                del self.subs[rm_id]

            await ctx.respond(
                f"All killmail subs removed for <#{ctx.channel.id}>.\nYou may encounter additional killmails in the message queue that have already been submitted and partially processed.",
                ephemeral=True,
                delete_after=15,
            )
        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"[Clear Command] • {e}")
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
