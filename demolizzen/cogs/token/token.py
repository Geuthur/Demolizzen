# Standard Library
import time
from typing import Any

# Third Party
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError
from oauthlib.oauth2.rfc6749.errors import (
    InvalidClientError,
    InvalidClientIdError,
    InvalidGrantError,
    InvalidTokenError,
    MissingTokenError,
)
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks
from discord.ui import Button, View

# Demolizzen
from demolizzen import models
from demolizzen.core.bot import Demolizzen
from demolizzen.utils.functions import application_cooldown

OTOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
TOKEN_JWK_SET_URL = "https://login.eveonline.com/oauth/jwks"
TOKEN_JWT_AUDIENCE = "EVE Online"


class Token(commands.Cog):
    """
    ESI Token System - Testing Phase - ** Use at your own risk! **
    How to use: You can use https://hell-rider.de/refresh_token or you need a Developer that know how to get Refresh_Token
    You need a valid Refresh Token from EVE-Online to use Token needed Commands!
    """

    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.session = bot.session
        self.config = bot.config
        self.title = "Token"
        self.alias = "token"
        self.client_id = self.config.TOKENS["client_id"]
        self.secret_id = self.config.TOKENS["secret"]

        self.token_refresh.start()

    token = SlashCommandGroup(
        "token", "Token", contexts=[discord.InteractionContextType.guild]
    )

    def cog_unload(self):
        self.token_refresh.cancel()

    @tasks.loop(minutes=21)
    async def token_refresh(self):
        """Refresh expired tokens every 21 minutes."""
        try:
            await self._refresh()
        # pylint: disable=broad-except
        except Exception as e:
            self.bot.logger.error("ERROR: %s", str(e))

    @token_refresh.before_loop
    async def before_token_refresh(self):
        await self.bot.wait_until_ready()
        self.bot.logger.info("Token Refresher Ready")

    async def _refresh(self, runs: int = 0):
        tokens = [token async for token in models.AccessToken.objects.all()]

        if tokens:
            items = []
            for token in tokens:
                if token.expires_at is not None and token.expires_at < time.time():
                    new_token, success = await self.refresh_access_token(
                        token, self.client_id, self.secret_id
                    )
                    if success is False:
                        continue
                    token.access_token = new_token["access_token"]
                    token.expires_at = float(new_token["expires_in"]) + time.time()
                    token.has_token_error = False
                    token.error_message = None
                    items.append(token)
                    runs += 1
            if items:
                await models.AccessToken.objects.abulk_update(
                    items,
                    fields=[
                        "access_token",
                        "expires_at",
                        "has_token_error",
                        "error_message",
                    ],
                )
            self.bot.logger.debug("Refreshed %s tokens", runs)
            runs = 0
        else:
            self.bot.logger.debug("No tokens found.")

    def _decode_jwt(self, jwt_token: dict, jwk_set: dict, issuer: Any):
        """
        Helper function to decide the JWT access token supplied by EVE SSO
        """
        self.bot.logger.debug("Start Decode")
        token_data = jwt.decode(
            jwt_token,
            jwk_set,
            algorithms=jwk_set["alg"],
            audience=TOKEN_JWT_AUDIENCE,
            issuer=issuer,
        )
        token_detail = token_data.get("sub", None).split(":")
        token_data["character_id"] = int(token_detail[2])
        token_data["token_type"] = token_detail[0].lower()
        self.bot.logger.debug(token_data)
        return token_data

    async def validate_access_token(self, token: str):
        """
        Validate a JWT token retrieved from the EVE SSO.
        :param token: A JWT token originating from the EVE SSO v2
        :return: :class:`dict` The contents of the validated JWT token if
            there are no validation errors
        """

        async with self.session.get(TOKEN_JWK_SET_URL) as res:
            res.raise_for_status()
            data = await res.json()

        try:
            jwk_sets = data["keys"]
        except KeyError as e:
            self.bot.logger.warning(
                "Something went wrong when retrieving the JWK set. "
                "The returned payload did not have the expected key %s.\n"
                "Payload returned from the SSO looks like: %s",
                e,
                data,
            )
            return None

        jwk_set = [item for item in jwk_sets if item["alg"] == "RS256"].pop()
        try:
            return self._decode_jwt(
                token, jwk_set, ("login.eveonline.com", "https://login.eveonline.com")
            )
        except ExpiredSignatureError:
            self.bot.logger.warning("The JWT token has expired")
            return None
        except JWTError as e:
            self.bot.logger.warning("The JWT signature was invalid: %s", e)
            return None

    # Token Handling
    async def refresh_access_token(
        self, token: models.AccessToken, client_id: str, client_secret: str
    ):
        # Encode the CLIENT_ID and CLIENT_SECRET in Base64
        session = OAuth2Session(client_id)
        auth = HTTPBasicAuth(client_id, client_secret)

        try:
            new_token = session.refresh_token(
                OTOKEN_URL, refresh_token=token.refresh_token, auth=auth
            )
            self.bot.logger.debug("Retrieved new token from SSO servers.")
        except InvalidGrantError as e:
            # this token is gone forever
            self.bot.logger.debug("Refresh impossible for %s: %s", token, e)
            token.has_token_error = True
            token.error_message = str(e)
            await token.asave()
            return token, False
        except (InvalidTokenError, InvalidClientIdError) as e:
            # these may be recoverable?
            self.bot.logger.debug(
                "Character: %s, The access token provided is expired, revoked, malformed, "
                "or invalid for other reasons: %s",
                token,
                e,
            )
            token.has_token_error = True
            token.error_message = str(e)
            await token.asave()
            return token, False
        except MissingTokenError as e:
            self.bot.logger.debug("Missing token for %s: %s", token, e)
            token.has_token_error = True
            token.error_message = str(e)
            await token.asave()
            return token, False
        except InvalidClientError:
            self.bot.logger.error(
                "ESI client ID and secret rejected by remote. Cannot refresh."
            )
            token.has_token_error = True
            token.error_message = "Invalid client ID or secret."
            await token.asave()
            return token, False
        return new_token, True

    @token.command(name="add")
    @commands.cooldown(3, 1800, commands.BucketType.user)  # 30 Minuten
    @option("character_id", description="Put Character ID here")
    @option("token", description="Put Refresh Token here")
    async def token_add(
        self, ctx: discord.ApplicationContext, character_id: int, refresh_token: str
    ):
        """
        Add ESI Token to Discord Bot.
        """

        self.bot.logger.debug("Starting token refresh process.")
        try:
            user = await models.UserProfile.objects.aget(
                user_id=ctx.author.id, guild_id=ctx.guild.id
            )
        except models.UserProfile.DoesNotExist:
            return await ctx.respond(
                f"{ctx.author.mention}, No user profile found, can't Add Token without Profile.",
                ephemeral=True,
            )

        new_token, __ = await models.AccessToken.objects.aget_or_create(
            user=user,
            character_id=character_id,
            refresh_token=refresh_token,
        )

        if not new_token:
            return await ctx.respond(
                "ERROR: Failed to create or retrieve token.", ephemeral=True
            )

        # Validate and refresh the token
        token, success = await self.refresh_access_token(
            new_token, self.client_id, self.secret_id
        )

        if success is False:
            return await ctx.respond(
                f"ERROR: Failed to add token: {token.error_message}.", ephemeral=True
            )

        try:
            # Get Token Information
            token_data = await self.validate_access_token(token["access_token"])

            if token_data is not None:
                # Validate Character ID
                if new_token.character_id != token_data["character_id"]:
                    await models.AccessToken.objects.adelete(new_token)
                    return await ctx.respond(
                        "ERROR: Character ID does not match the token data.",
                        ephemeral=True,
                    )

            new_token.access_token = token["access_token"]
            new_token.expires_at = float(token["expires_in"]) + time.time()
            new_token.has_token_error = False
            new_token.error_message = None

            await new_token.asave()
        except Exception as e:  # pylint: disable=broad-except
            self.bot.logger.debug(
                f"Error adding refresh token for {ctx.author.name}: {e}"
            )
            return await ctx.respond(
                "ERROR: Failed to add refresh token.", ephemeral=True
            )

        self.bot.logger.info(f"Token - {ctx.author.name} added a refresh token.")
        await ctx.respond(
            f"{ctx.author.mention} refresh token added.",
            ephemeral=True,
        )

    @token.command(name="help")
    @commands.cooldown(3, 1800, commands.BucketType.user)  # 30 Minuten
    async def token_help(self, ctx: discord.ApplicationContext):
        """
        How to Use Token System
        """
        button1 = Button(
            label="Token Generator",
            url="https://hell-rider.de/refresh_token",
            style=discord.ButtonStyle.green,
            emoji="📜",
        )

        view = View()
        view.add_item(button1)
        await ctx.respond(
            "** TEST MODE **\n With the Link you can add the SSO Scope to the Discord Bot.\n ATM there is no use for it.",
            view=view,
        )

    @token_help.error
    async def command_cooldown(self, ctx, error):
        await application_cooldown(ctx, error)
