# Standard Library
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
from demolizzen.core.command_scope import CommandScope
from demolizzen.core.openapi import OpenAPI
from demolizzen.services import guilds


class Demolizzen(commands.Bot):
    """The Demolizzen bot.

    Constructing the bot has no side effects: extensions are loaded by
    :meth:`load_preload_extensions` and network resources are created by
    :meth:`start`, so the bot can be built in tests without a token or network.
    """

    def __init__(self, **kwargs):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        kwargs["command_prefix"] = "$"
        # Commands are synced only where this class says so, through
        # command_scope; py-cord's own sync knows nothing of per-server modules.
        kwargs["auto_sync_commands"] = False
        super().__init__(intents=intents, **kwargs)
        self.counter = Counter()
        self.config = config
        self.token = config.BOT_TOKEN
        self.req_perms = discord.Permissions(config.BOT_PERMISSIONS)
        self.preload_ext = config.PRELOAD_EXTENSIONS
        self.logger = logger.init_logger(debug_flag="info")
        self.launch_time = timezone.now()
        self._connected_once = False
        self._modules_loaded = False
        self.command_scope = CommandScope(self)
        self._commands_synced = False
        # Created in start(), once the event loop is running.
        self.session: aiohttp.ClientSession | None = None
        self.esi_data: OpenAPI | None = None

    def load_preload_extensions(self) -> dict[str, Exception | None]:
        """Load every configured extension.

        A failing extension is logged and does not stop the others.

        Returns
        -------
        dict[str, Exception | None]
            The extension name mapped to the error it raised, or ``None`` on success.
        """
        self._modules_loaded = True
        results: dict[str, Exception | None] = {}
        print(Green("-------- Loading Modules ---------"))
        for ext in self.preload_ext:
            try:
                self.load_extension(f"demolizzen.cogs.{ext}")
            # pylint: disable=broad-except
            except Exception as e:
                self.logger.exception(f"Failed to load extension {ext}", exc_info=e)
                print(Blue(f"- {ext.capitalize()} ❌ {e}"))
                results[ext] = e
            else:
                print(Blue(f"- {ext.capitalize()} ✅ "))
                results[ext] = None
        print(Green("-------- Finished Loading --------\n"))
        return results

    def _ensure_modules(self) -> None:
        """Load the modules unless that has been done.

        Every way of starting the bot ends up here, so it can never connect
        without its modules: a bot without modules has no commands, and
        syncing "no commands" would delete all of them at Discord.
        """
        if not self._modules_loaded:
            self.load_preload_extensions()

    def run(self, *args, **kwargs) -> None:
        """Load the modules if the caller has not, then connect and block."""
        self._ensure_modules()
        super().run(*args, **kwargs)

    async def start(self, token: str | None = None, *, reconnect: bool = True) -> None:
        """Create the HTTP session and ESI client, then log in and connect.

        py-cord has no ``setup_hook``; this is the first point where the event
        loop is running.
        """
        token = token or self.token
        if token is None:
            self.logger.critical("Token must be set in order to login.")
            raise RuntimeError("Token must be set in order to login.")

        self._ensure_modules()
        self.session = aiohttp.ClientSession()
        self.esi_data = OpenAPI(self.session)
        await super().start(token, reconnect=reconnect)

    async def close(self) -> None:
        """Stop background work and release the HTTP session. Safe to call twice."""
        if self.esi_data is not None:
            self.esi_data.close()
            self.esi_data = None
        if self.session is not None:
            await self.session.close()
            self.session = None
        await super().close()

    @cached_property
    def invite_url(self):
        # Guild commands need the applications.commands scope. Discord adds it
        # to the bot scope by itself today; naming it also repairs servers that
        # invited the bot before that.
        return discord.utils.oauth_url(
            self.user.id,
            permissions=self.req_perms,
            scopes=("bot", "applications.commands"),
        )

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

    async def on_unknown_application_command(self, interaction: discord.Interaction):
        """Answer a click on a command entry Discord no longer has.

        Without this the member only sees "The application did not respond".
        """
        data = interaction.data or {}
        command = self.command_scope.resolve_stale(
            data.get("name"), interaction.guild_id
        )
        if interaction.type is discord.InteractionType.auto_complete:
            if command is not None:
                self.dispatch("application_command_auto_complete", interaction, command)
            return
        if command is None:
            await interaction.response.send_message(
                "This command is not available here any more. If it is still "
                "listed, restart Discord (Ctrl+R).",
                ephemeral=True,
            )
            return
        interaction.command = command
        ctx = await self.get_application_context(interaction)
        await self.invoke_application_command(ctx)

    async def on_connect(self):
        if self._connected_once:
            return print("Reconnected.")
        self._connected_once = True

        print(Red("==========================================="))
        print(Red("Demolizzen - The Discord Bot for EVE Online"))
        print(Red("==========================================="))

        if self.invite_url:
            print(f"\nInvite URL: {self.invite_url}\n")

    async def on_ready(self):
        guild_count = len(self.guilds)
        users = len(list(self.get_all_members()))

        if self._commands_synced:
            # on_ready fires again after a reconnect: only follow changes.
            await self.command_scope.refresh()
        elif self.pending_application_commands:
            await self.sync_commands()
            self._commands_synced = True
        else:
            # Syncing an empty list would delete every command at Discord.
            self.logger.error(
                "No commands are loaded; the commands registered with Discord "
                "are left untouched."
            )
            print(Red("No modules are loaded: slash commands were NOT synced."))

        updated_guilds = 0
        for guild in self.guilds:
            if await guilds.rename_guild(guild.id, guild.name):
                updated_guilds += 1
        if updated_guilds > 0:
            print(f"Updated guild names for {updated_guilds} guild(s).")

        if guild_count:
            print(f"Servers: {guild_count}")
            print(f"Members: {users}")
        else:
            print("Invite me to a server!")

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f"{guild_count} Servers",
                state="Status: 🟢 No Issues",
            ),
            status=discord.Status.online,
        )

    async def sync_commands(self, *_args, **_kwargs) -> None:
        """Register every server's commands, then the global ones.

        The arguments of py-cord's method are not used: which server gets
        which command is decided by its module settings alone, see
        :mod:`demolizzen.core.command_scope`.
        """
        failed = await self.command_scope.sync_all()
        if failed:
            print(
                Red(
                    f"Slash commands could not be registered on {len(failed)} "
                    "server(s); the log names them."
                )
            )

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
        try:
            # The commands of the switchable modules are registered per server.
            await self.command_scope.refresh()
        except Exception:  # pylint: disable=broad-exception-caught
            self.logger.exception(
                f"Could not register the slash commands of {guild.name} ({guild.id})"
            )
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
