import logging
import time

import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks
from discord.ui import Button, View
from settings import db
from settings.functions import application_cooldown

log = logging.getLogger("discord")


class Token(commands.Cog):
    """
    ESI Token System - Testing Phase - ** Use at your own risk! **
    How to use: You can use https://hell-rider.de/refresh_token or you need a Developer that know how to get Refresh_Token
    You need a valid Refresh Token from EVE-Online to use Token needed Commands!
    """

    def __init__(self, bot):
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
        try:
            await self.refresh()
        # pylint: disable=broad-except
        except Exception as e:
            log.error("ERROR: %s", str(e))

    @token_refresh.before_loop
    async def before_token_refresh(self):
        await self.bot.wait_until_ready()

    @token.command(name="add")
    @commands.cooldown(3, 1800, commands.BucketType.user)  # 30 Minuten
    @option("token", description="Put Refresh Token here")
    async def _token(self, ctx, token: str):
        """
        Add ESI Token to Discord Bot.
        """
        access_token = await self.bot.esi_data.refresh_access_token(
            token, self.client_id, self.secret_id
        )
        try:
            verify = await self.bot.esi_data.verify_token(access_token["access_token"])
            character_id = verify["CharacterID"]
        # pylint: disable=broad-except
        except Exception:
            return await ctx.respond("ERROR: That is not a valid refresh token.")
        expires = float(access_token["expires_in"]) + time.time()
        sql = "REPLACE INTO access_tokens (character_id, discord_id, refresh_token, access_token, expires) VALUES(:character_id, :discord_id, :refresh_token, :access_token, :expires)"
        values = {
            "character_id": character_id,
            "discord_id": ctx.author.id,
            "refresh_token": token,
            "access_token": access_token["access_token"],
            "expires": expires,
        }
        await db.execute_sql(sql, values)
        log.info(f"Token - {ctx.author.name} added a refresh token.")
        await ctx.respond(
            f"{ctx.author.mention} refresh token added.",
            ephemeral=True,
            delete_after=15,
        )

    @token.command(name="help")
    @commands.cooldown(3, 1800, commands.BucketType.user)  # 30 Minuten
    async def _token_help(self, ctx):
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

    @_token_help.error
    async def command_cooldown(self, ctx, error):
        await application_cooldown(ctx, error)

    async def refresh(self):
        sql = "SELECT * FROM access_tokens"
        tokens = await db.select(sql)

        if tokens is not None:  # Überprüfen, ob `tokens` nicht None ist
            for token in tokens:
                if token[5] is not None and token[5] < time.time():
                    access_token = await self.bot.esi_data.refresh_access_token(
                        token[3], self.client_id, self.secret_id
                    )
                    try:
                        await self.bot.esi_data.verify_token(
                            access_token["access_token"]
                        )
                        # character_id = verify["CharacterID"]
                    # pylint: disable=broad-except
                    except Exception as e:
                        log.error(f"Fehler in Token: {e}")
                        sql = "DELETE FROM access_tokens WHERE refresh_token = :refresh_token"
                        values = {"refresh_token": access_token["refresh_token"]}
                        await db.execute_sql(sql, values)
                        continue
                    expires = float(access_token["expires_in"]) + time.time()
                    sql = "UPDATE access_tokens SET `access_token` = :access_token, `expires` = :expires WHERE `refresh_token` = :refresh_token AND `discord_id` = :discord_id"

                    values = {
                        "access_token": access_token["access_token"],
                        "expires": expires,
                        "refresh_token": token[3],
                        "discord_id": token[2],
                    }
                    await db.execute_sql(sql, values)
        else:
            log.debug("Keine Tokens in der Datenbank gefunden.")
