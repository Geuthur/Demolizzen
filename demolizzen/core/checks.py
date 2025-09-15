# Discord
import discord
from discord.ext import commands

# Demolizzen
from demolizzen.models import GuildProfile


async def check_is_guildowner(ctx: discord.ApplicationContext, precheck=None):
    if ctx.author.id == ctx.guild.owner.id:
        return True
    if not precheck:
        await ctx.respond("You are not the Guild Owner.", ephemeral=True)
    return False


async def check_is_admin(ctx: discord.ApplicationContext, precheck=None):
    if ctx.author.guild_permissions.manage_guild:
        return True
    if await check_is_guildowner(ctx, precheck=True):
        return True
    if not precheck:
        permissions = []
        if await check_is_guildowner(ctx, precheck=True):
            permissions.append("Guild Owner")
        permissions.append("Admin")
        await ctx.respond(
            "You are not an Admin. Permitted are: " + ", ".join(permissions),
            ephemeral=True,
        )
    return False


async def check_is_guildmanager(ctx: discord.ApplicationContext, precheck=None):
    if ctx.author.guild_permissions.manage_guild:
        return True
    if await check_is_guildowner(ctx, precheck=True):
        return True
    if await check_is_admin(ctx, precheck=True):
        return True
    if not precheck:
        permissions = []
        if await check_is_guildowner(ctx, precheck=True):
            permissions.append("Guild Owner")
        if await check_is_admin(ctx, precheck=True):
            permissions.append("Admin")
        permissions.append("Guild Manager")
        await ctx.respond(
            "You are not a Guild Manager. Permitted are: " + ", ".join(permissions),
            ephemeral=True,
        )
    return False


async def check_is_mod(ctx: discord.ApplicationContext, precheck=None):
    if ctx.channel.permissions_for(ctx.author).manage_messages:
        return True
    if await check_is_guildowner(ctx, precheck=True):
        return True
    if await check_is_admin(ctx, precheck=True):
        return True
    if await check_is_guildmanager(ctx, precheck=True):
        return True
    if not precheck:
        permissions = []
        if await check_is_guildowner(ctx, precheck=True):
            permissions.append("Guild Owner")
        if await check_is_admin(ctx, precheck=True):
            permissions.append("Admin")
        if await check_is_guildmanager(ctx, precheck=True):
            permissions.append("Guild Manager")
        permissions.append("Moderation")
        await ctx.respond(
            "You are not a Mod. Permitted are: " + ", ".join(permissions),
            ephemeral=True,
        )
    return False


# Benutzerdefinierte Überprüfungsfunktion, die sicherstellt, dass der Befehl im gewünschten Channel ausgeführt wird
async def check_channel(ctx: discord.ApplicationContext):
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
    guild_profile = await GuildProfile.objects.aget(guild_id=ctx.guild.id)

    if guild_profile is not None:
        channel = discord.utils.get(
            ctx.guild.channels,
            name=guild_profile.main_channel,
        )
        if ctx.channel.name != f"{channel}" and channel is not None:
            await ctx.respond(
                f"Commands are only allowed in <#{channel.id}>.", ephemeral=True
            )
            return False
    return True


# Decorators for the checks hierarchy example: is_mod > is_guild_manager > is_admin > is_guild_owner
def is_guild_owner():
    """Check if the user is the guild owner or higher."""
    return commands.check(check_is_guildowner)


def is_admin():
    """Check if the user is an admin or higher."""
    return commands.check(check_is_admin)


def is_guild_manager():
    """Check if the user is the guild manager or higher."""
    return commands.check(check_is_guildmanager)


def is_mod():
    """Check if the user is a mod or higher."""
    return commands.check(check_is_mod)


def is_in_channel():
    """Check if the command is used in the correct channel."""
    return commands.check(check_channel)
