import asyncio
import datetime
import logging

import discord
from discord.ext import commands
from pycolorise.colors import Red
from settings import db

log = logging.getLogger("events")
log_test = logging.getLogger("testing")


# pylint: disable=too-many-statements
def init_events(bot: discord.Bot):
    @bot.event
    async def on_connect():
        if hasattr(bot, "launch_time"):
            return print("Reconnected.")

        if not hasattr(bot, "launch_time"):
            bot.launch_time = datetime.datetime.now()

        print(Red("==========================================="))
        print(Red("Demolizzen - The Discord Bot for EVE Online"))
        print(Red("==========================================="))

        if bot.invite_url:
            print(f"\nInvite URL: {bot.invite_url}\n")

    @bot.event
    async def on_ready():
        guilds = len(bot.guilds)
        users = len(list(bot.get_all_members()))

        try:
            await bot.sync_commands()
        # pylint: disable=broad-except
        except Exception as e:
            log.exception(f"Error while syncing commands: {e}")

        if guilds:
            print(f"Servers: {guilds}")
            print(f"Members: {users}")
        else:
            print("Invite me to a server!")

    @bot.event
    async def on_application_command_error(ctx: discord.ApplicationContext, error):
        if isinstance(error, commands.MissingRole):
            await ctx.respond(
                "Du hast nicht die erforderliche Rolle, um diesen Befehl auszuführen!"
            )
            return

        if isinstance(error, commands.CommandOnCooldown):
            return

        if isinstance(error, commands.NoPrivateMessage):
            await ctx.respond(
                "This Command works only on Server.", ephemeral=True, delete_after=10
            )
            return

        if isinstance(error, commands.CommandError):
            await ctx.respond(
                "Der Befehl konnte nicht verarbeitet werden, Bitte versuche es später erneut.",
                ephemeral=True,
                delete_after=10,
            )
            log.exception(f"Ein Fehler ist aufgetreten: {error}", exc_info=True)
            return

        if isinstance(error, commands.CheckFailure):
            return

        if "check functions" in str(error):
            return

        log.exception(f"Ein Fehler ist aufgetreten: {error}", exc_info=True)
        em = discord.Embed(
            color=discord.Color.red(),
            description="Es ist ein Fehler aufgetreten bitte versuch es später erneut.",
        )
        if isinstance(ctx, discord.Interaction):
            await ctx.respond(embed=em, delete_after=10)
        return

    @bot.event
    # pylint: disable=unused-argument
    async def on_command_error(ctx, error):
        if isinstance(error, commands.MissingRole):
            log.info(f"Ein Fehler ist aufgetreten: {error}", exc_info=True)
            return
        if isinstance(error, commands.CommandOnCooldown):
            return
        if isinstance(error, commands.NoPrivateMessage):
            log.info(
                f"No Privat Message Fehler ist aufgetreten: {error}", exc_info=True
            )
            return
        if isinstance(error, commands.CommandError):
            log.info(f"Command Fehler ist aufgetreten: {error}", exc_info=True)
            return

        log.info(f"Ein Fehler ist aufgetreten: {error}", exc_info=True)
        return

    @bot.event
    async def on_guild_join(guild):
        owner = guild.owner
        em = discord.Embed(
            title="Demolizzen - EVE Online Discord Bot",
            color=discord.Color.teal(),
            description="",
        )
        em.add_field(
            name="",
            value=f"Hello **{owner.name}**, thank you choosing me as EVE Online Assistant.",
            inline=False,
        )
        em.add_field(
            name="",
            value="If you have any Question to me please use `/help` on your Server.",
            inline=False,
        )
        em.add_field(
            name="",
            value="I recommend to set the main channel for my interactions with `/mc set`",
            inline=False,
        )
        em.add_field(
            name="",
            value="If there is any errors or something that not work let me know!",
            inline=False,
        )
        em.add_field(
            name="",
            value="Be sure that the bot has enough permission you can check it with `/bot perms_guild`",
            inline=False,
        )
        em.add_field(
            name="",
            value="Support Discord: https://discord.gg/WrHzA4rnxA",
            inline=False,
        )
        await owner.send(embed=em)

    @bot.event
    async def on_member_join(member):
        retries = 3  # Anzahl der Versuche
        delay_seconds = 5  # Verzögerung zwischen den Versuchen in Sekunden

        for attempt in range(retries):
            try:
                # Core Data
                await db.create_user_new(user=member, guild=member.guild.id)
                # Wenn der Code bis hierher ausgeführt wird, breche die Schleife ab.
                log.info(f"Create User Data: {member.display_name}")
                break
            # pylint: disable=broad-except
            except Exception as e:
                log.error(f"Fehler bei on member join: {e}")
                if attempt < retries - 1:
                    # Warte vor dem nächsten Versuch
                    await asyncio.sleep(delay_seconds)

    @bot.event
    async def on_member_remove(member):
        retries = 3  # Anzahl der Versuche
        delay_seconds = 5  # Verzögerung zwischen den Versuchen in Sekunden
        for attempt in range(retries):
            try:
                # Core Data
                await db.remove_user_new(user=member, guild=member.guild.id)
                log.info(f"Remove User Data: {member.display_name}")

                # Leveling Data
                sql = "DELETE FROM `levelling` WHERE `guild_id` = :guild_id AND `user_id` = :user_id"
                val = {"guild_id": member.guild.id, "user_id": member.id}
                await db.execute_sql(sql, val)
                log.info(f"Delete Levelsystem User: {member.display_name}")
                # Wenn der Code bis hierher ausgeführt wird, breche die Schleife ab.
                break
            # pylint: disable=broad-except
            except Exception:
                log.error("Fehler bei on member remove")
                if attempt < retries - 1:
                    # Warte vor dem nächsten Versuch
                    await asyncio.sleep(delay_seconds)
