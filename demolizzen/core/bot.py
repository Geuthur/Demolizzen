# Standard Library
import asyncio
import os
import sys
import traceback
from collections import Counter
from functools import cached_property

# Third Party
import aiohttp
from pycolorise.colors import Blue, Green, Red

# Discord
import discord
from discord.ext import commands

# Django
from django.utils import timezone

# Demolizzen
from demolizzen import config, logger
from demolizzen.core.esi import ESI
from demolizzen.models.guild import GuildProfile


class Demolizzen(commands.Bot):
    def __init__(self, **kwargs):
        # Deine intents definieren
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        kwargs["command_prefix"] = "$"
        super().__init__(intents=intents, **kwargs)
        self.counter = Counter()
        self.core_dir = os.path.dirname(os.path.realpath(__file__))
        self.config = config
        self.bot_users = []
        self.token = config.BOT_TOKEN
        self.req_perms = discord.Permissions(config.BOT_PERMISSIONS)
        self.preload_ext = config.PRELOAD_EXTENSIONS
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.esi_data = ESI(self.session)
        self.logger = logger.init_logger(debug_flag="info")
        self.launch_time = timezone.now()

        print(Green("-------- Loading Modules ---------"))
        for ext in self.preload_ext:
            try:
                self.load_extension(f"demolizzen.cogs.{ext}")
                print(Blue(f"- {ext.capitalize()} ✅ "))
            # pylint: disable=broad-except
            except Exception as e:
                self.logger.exception(f"Failed to load extension {ext}", exc_info=e)
                print(Blue(f"- {ext.capitalize()} ❌ {e}"))
        print(Green("-------- Finished Loading --------\n"))
        loop = asyncio.get_event_loop()
        if self.token is None:
            self.logger.critical("Token must be set in order to login.")
            sys.exit(1)
        try:
            loop.run_until_complete(self.start(self.token))
        # pylint: disable=broad-except
        except Exception as e:
            self.logger.critical("Fatal exception", exc_info=e)

    @cached_property
    def invite_url(self):
        invite_url = discord.utils.oauth_url(self.user.id, permissions=self.req_perms)
        return invite_url

    @property
    def uptime(self):
        return timezone.now() - self.launch_time

    @property
    def uptime_str(self):
        uptime = self.uptime
        days = uptime.days
        seconds = uptime.seconds
        years, days = divmod(days, 365)
        months, days = divmod(days, 30)
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if years:
            parts.append(f"{years}y ")
        if months:
            parts.append(f"{months}m ")
        if days:
            parts.append(f"{days}d ")
        if hours:
            parts.append(f"{hours}h ")
        if minutes:
            parts.append(f"{minutes}min ")
        if seconds or not parts:
            parts.append(f"{seconds}s")
        return "".join(parts).strip()

    async def on_interaction(self, interaction: discord.Interaction):
        try:
            await self.process_application_commands(interaction)
        except Exception as e:
            self.logger.error(f"Interaction Failed {e}", stack_info=True)

    async def on_connect(self):
        if hasattr(self, "launch_time"):
            return print("Reconnected.")

        if not hasattr(self, "launch_time"):
            self.launch_time = timezone.now()

        print(Red("==========================================="))
        print(Red("Demolizzen - The Discord Bot for EVE Online"))
        print(Red("==========================================="))

        if self.invite_url:
            print(f"\nInvite URL: {self.invite_url}\n")

    async def on_ready(self):
        guilds = len(self.guilds)
        users = len(list(self.get_all_members()))

        await self.sync_commands()

        updated_guilds = 0
        for guild in self.guilds:
            try:
                guild_profile = await GuildProfile.objects.aget(guild_id=guild.id)
                if guild.name != guild_profile.guild_name:
                    guild_profile.guild_name = guild.name
                    updated_guilds += 1
                    await guild_profile.asave()
            except GuildProfile.DoesNotExist:
                pass
        if updated_guilds > 0:
            print(f"Updated guild names for {updated_guilds} guild(s).")

        if guilds:
            print(f"Servers: {guilds}")
            print(f"Members: {users}")
        else:
            print("Invite me to a server!")

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f"{guilds} Servers",
                state="Status: 🟢 No Issues",
            ),
            status=discord.Status.online,
        )

    async def sync_commands(self, *args, **kwargs):
        try:
            return await super(__class__, self).sync_commands(*args, **kwargs)
        except discord.Forbidden as e:
            self.logger.error("-----------------------------------------------------")
            self.logger.error("Demolizzen was Unable to Sync Slash Commands!!!!")
            self.logger.error(
                "Please ensure your bot was invited to the server with the correct scopes"
            )
            self.logger.error("")
            self.logger.error("To redo your scopes,")
            self.logger.error("1. Refresh Scopes with this link:")
            self.logger.error(f"{self.invite_url}")
            self.logger.error(
                "2. Move the bots role to top of the roles tree if its not there already"
            )
            self.logger.error("3. Restart Bot")
            self.logger.error("-----------------------------------------------------")
            self.logger.error(e)

    async def send_resp(
        self, ctx: discord.ApplicationContext, exp: discord.DiscordException
    ):
        """
        Send a response to the user based on the exception type.

        Parameters
        ----------
        ctx : discord.ApplicationContext
            The context of the interaction.
        exp : discord.DiscordException
            The exception that occurred.
        """
        await self._safe_respond(ctx, str(exp), ephemeral=True)

    async def _safe_respond(
        self,
        ctx: discord.ApplicationContext,
        content: str,
        ephemeral: bool = True,
    ) -> None:
        """
        Safely respond to an interaction, checking if it has already been responded to.

        Parameters
        ----------
        ctx : discord.ApplicationContext
            The context of the interaction.
        content : str
            The content to send in the response.
        ephemeral : bool, optional
            Whether the response should be ephemeral (only visible to the user), by default True.
        """
        interaction = getattr(ctx, "interaction", None)
        if not interaction:
            return

        try:
            if interaction.is_expired():
                return
        except AttributeError:
            pass

        try:
            if interaction.response.is_done():
                await ctx.followup.send(content=content, ephemeral=ephemeral)
            else:
                await ctx.respond(content=content, ephemeral=ephemeral)
        except (discord.errors.NotFound, discord.errors.InteractionResponded):
            return

    async def on_application_command_error(
        self, context: discord.ApplicationContext, exception: discord.DiscordException
    ) -> None:
        if isinstance(exception, commands.CheckFailure):
            await self.send_resp(context, exception)
        elif isinstance(exception, commands.MissingPermissions):
            await self.send_resp(context, exception)
        elif isinstance(exception, commands.CommandOnCooldown):
            await self.send_resp(context, exception)
        elif isinstance(exception, discord.errors.CheckFailure):
            pass  # Silently ignore these errors.
        else:  # Catch everything, and close out the interactions gracefully.
            cmd_name = getattr(
                getattr(context, "command", None), "qualified_name", None
            )
            user_id = getattr(getattr(context, "user", None), "id", None)
            guild_id = getattr(getattr(context, "guild", None), "id", None)
            interaction_data = getattr(
                getattr(context, "interaction", None), "data", None
            )
            self.logger.error(
                f"Application Command failed cmd={cmd_name} user={user_id} guild={guild_id} data={interaction_data}"
            )
            self.logger.error(f"Unknown Error {exception}")
            self.logger.error(
                "".join(
                    traceback.format_exception(
                        type(exception), exception, exception.__traceback__
                    )
                )
            )
            await self._safe_respond(
                context,
                "Something Went Wrong, Please try again Later.",
                ephemeral=True,
            )

    async def on_guild_join(self, guild: discord.Guild):
        owner = guild.owner
        em = discord.Embed(
            title="Demolizzen - EVE Online Discord Bot",
            color=discord.Color.teal(),
            description="",
        )
        em.add_field(
            name="",
            value=f"Hello **{owner.display_name}**, thank you choosing me as EVE Online Assistant.",
            inline=False,
        )
        em.add_field(
            name="",
            value="If you have any Question to me please use `/help` on your Server.",
            inline=False,
        )
        em.add_field(
            name="",
            value="I recommend to set the main channel for my interactions with `/guild set_channel`",
            inline=False,
        )
        em.add_field(
            name="",
            value="If there is any errors or something that not work let me know!",
            inline=False,
        )
        em.add_field(
            name="",
            value="Be sure that the bot has enough permission you can check it with `/guild perms_guild`",
            inline=False,
        )
        em.add_field(
            name="",
            value="Visit my Discovery Page: https://discord.com/discovery/applications/990582360103870495",
            inline=False,
        )
        em.add_field(
            name="",
            value="Support Discord: https://discord.gg/WrHzA4rnxA",
            inline=False,
        )
        try:
            await owner.send(embed=em)
        except discord.Forbidden:
            self.logger.warning(
                f"Could not send guild join message to owner of guild {guild.name} ({guild.id})"
            )
