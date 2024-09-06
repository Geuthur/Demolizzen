import discord
import Levelling.Database.get
import Levelling.Database.set
from discord.ext import commands


async def check_is_owner(ctx):
    return await ctx.bot.is_owner(ctx.author)


async def check_is_guildowner(ctx, precheck=None):
    if not ctx.guild:
        await ctx.respond("This command works only on Server", ephemeral=True)
        return False
    if ctx.author.id == ctx.guild.owner.id:
        return True
    if not precheck:
        await ctx.respond("You are not the Owner.", ephemeral=True)
    return False


async def check_is_admin(ctx, precheck=None):
    if not ctx.guild:
        await ctx.respond("This command works only on Server", ephemeral=True)
        return False
    if ctx.author.guild_permissions.manage_guild:
        return True
    if await check_is_guildowner(ctx, precheck=True):
        return True
    if not precheck:
        await ctx.respond("You have no Admin Permission.", ephemeral=True)
    return False


async def check_is_botmanager(ctx):
    if not ctx.guild:
        await ctx.respond("This command works only on Server", ephemeral=True)
        return False
    bot_manager_role = discord.utils.get(ctx.guild.roles, name="Bot-Manager")
    if bot_manager_role and bot_manager_role in ctx.author.roles:
        return True
    if await check_is_admin(ctx, precheck=True):
        return True
    await ctx.respond("You need the Role `Bot-Manager`", ephemeral=True)
    ctx.permission_sent = True
    return False


async def check_is_mod(ctx):
    if not ctx.guild:
        await ctx.respond("This command works only on Server", ephemeral=True)
        return False
    if ctx.channel.permissions_for(ctx.author).manage_messages:
        return True
    if await check_is_admin(ctx, precheck=True):
        return True
    await ctx.respond("You have no Moderation Permission.", ephemeral=True)
    ctx.permission_sent = True

    return False


# Benutzerdefinierte Überprüfungsfunktion, die sicherstellt, dass der Befehl im gewünschten Channel ausgeführt wird
async def check_channel(ctx):
    """
    Custom check function to ensure that a command is executed in the desired channel.

    This function checks if a command is being executed in a specific channel defined
    by the guild's main channel setting. If a main channel is defined, the command can
    only be used in that channel.

    Returns
    -------
    Callable
        A coroutine predicate that checks if the command is in the correct channel.
    """
    if await Levelling.Database.get.mainchannel(guild=ctx.guild) is not None:
        channel = discord.utils.get(
            ctx.guild.channels,
            name=await Levelling.Database.get.mainchannel(guild=ctx.guild),
        )
        if ctx.channel.name != f"{channel}" and channel is not None:
            await ctx.respond(
                f"Commands are only allowed in <#{channel.id}>.", ephemeral=True
            )
            return False
    return True


def is_owner():
    return commands.check(check_is_owner)


def is_guild_owner():
    return commands.check(check_is_guildowner)


def is_admin():
    return commands.check(check_is_admin)


def is_botmanager():
    return commands.check(check_is_botmanager)


def is_mod():
    return commands.check(check_is_mod)


def is_in_channel():
    return commands.check(check_channel)
