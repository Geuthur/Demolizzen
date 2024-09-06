import discord
from discord.ext import commands


async def cog_loader_sync(self):
    guilds_to_check = [337275567487320064]
    connected_guilds = [guild.id for guild in self.bot.guilds]
    guilds = []
    for guild_id in guilds_to_check:
        if guild_id in connected_guilds:
            x = await self.bot.fetch_guild(guild_id)
            guilds.append(x)
            if not guilds:
                return False
        return guilds


# Convert Time
def convert_time(seconds: int) -> str:
    """
    Convert a duration in seconds into a human-readable string representation.

    This function takes a duration in seconds as input and converts it into a
    human-readable string format. It provides the duration in seconds, minutes,
    or hours, depending on the input value.

    Parameters
    ----------
    seconds : int
        The duration in seconds to be converted.

    Returns
    -------
    str
        A string representing the duration in seconds, minutes, or hours.
    """
    if seconds < 60:
        return f"{round(seconds)} Sekunden"
    minutes = seconds / 60
    if minutes < 60:
        return f"{round(minutes)} Minuten"
    hours = minutes / 60
    return f"{round(hours)} Stunden"


# Converter for Numbers - Example: 1000 to 1.000
def format_number(count, currency=None):
    """
    Diese Funktion nimmt eine Zahl als Eingabe und formatiert sie für die Ausgabe in einem benutzerfreundlichen Format.

    Parameters
    ----------
    count : int or float
        Die zu formatierende Zahl.
    currency : str, optional
        Die Währungseinheit, die der formatierten Zahl hinzugefügt werden soll. Standardmäßig ist dies None.

    Returns
    -------
    str
        Eine Zeichenkette, die die formatierte Zahl darstellt. Im Format "x.xxx,xx" für Dezimalzahlen, wobei
        das Tausender-Trennzeichen durch einen Punkt ersetzt wird. Wenn eine Währung angegeben ist, wird diese
        am Ende der formatierten Zahl angehängt.

    Examples
    --------
    Beispiel 1:
    >>> format_number(1000)
    '1.000'

    Beispiel 2 (mit Währung):
    >>> format_number(5000, 'EUR')
    '5.000 EUR'
    """
    # Anzahl formatieren und Komma durch Punkt ersetzen
    formatted_number = f"{count:,}".replace(",", ".")

    # Wenn eine Währung angegeben ist, füge sie hinzu
    if currency is not None:
        formatted_number = f"{formatted_number} {currency}"
    return formatted_number


def convert_to_bool(argument):
    lowered = argument.lower()
    if lowered in ("yes", "y", "true", "t", "1", "enable", "on"):
        return True
    if lowered in ("no", "n", "false", "f", "0", "disable", "off"):
        return False
    return None


# Application Cooldown Trigger
async def application_cooldown(ctx: discord.ApplicationContext, error):
    seconds = ctx.command.get_cooldown_retry_after(ctx)
    final_time = convert_time(seconds)
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.respond(
            f"The Rate limit has been reached, Please wait {final_time}",
            delete_after=10,
        )
        return


def colour(*args):
    """Returns a discord Colour object.
    Pass one as an argument to define colour:
        `str` match common colour names.
        `discord.Guild` bot's guild colour.
        `None` light grey.
    """
    arg = args[0] if args else None
    if isinstance(arg, str):
        color = arg
        try:
            return getattr(discord.Colour, color)()
        except AttributeError:
            return discord.Colour.lighter_grey()
    if isinstance(arg, discord.Guild):
        return arg.me.colour
    return discord.Colour.lighter_grey()


def make_embed(
    msg_type="",
    title=None,
    icon=discord.Embed,
    content=None,
    msg_colour=None,
    guild=None,
    title_url=discord.Embed,
    thumbnail="",
    image="",
    fields=None,
    footer=None,
    footer_icon=None,
    inline=False,
    subtitle=None,
    subtitle_url=None,
):
    """
    Helper for generating a formatted embed.

    Types available:
    error, warning, info, success, help.
    """

    embed_types = {
        "error": {"icon": "https://i.imgur.com/juhq2uJ.png", "colour": "red"},
        "warning": {"icon": "https://i.imgur.com/4JuaNt9.png", "colour": "gold"},
        "info": {"icon": "https://i.imgur.com/wzryVaS.png", "colour": "blue"},
        "success": {"icon": "https://i.imgur.com/ZTKc3mr.png", "colour": "green"},
        "help": {"icon": "https://i.imgur.com/kTTIZzR.png", "colour": "blue"},
    }

    if msg_type in embed_types:
        msg_colour = embed_types[msg_type]["colour"]
        icon = embed_types[msg_type]["icon"]

    if guild and not msg_colour:
        msg_colour = colour(guild)
    else:
        if not isinstance(msg_colour, discord.Colour):
            msg_colour = colour(msg_colour)

    embed = discord.Embed(
        description=content, colour=msg_colour, title=subtitle, url=subtitle_url
    )

    if title:
        embed.set_author(name=title, icon_url=icon, url=title_url)

    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    if image:
        embed.set_image(url=image)

    fields = fields or {}
    for key, value in fields.items():
        ilf = inline
        if not isinstance(value, str):
            ilf = value[0]
            value = value[1]
        embed.add_field(name=key, value=value, inline=ilf)

    if footer:
        footer = {"text": footer}

        if footer_icon:
            footer["icon_url"] = footer_icon

        embed.set_footer(**footer)
    return embed


def translate(num):
    num = float(f"{num:.3g}")
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return f"{num:f}".rstrip("0").rstrip(".") + ["", "K", "M", "B", "T"][magnitude]
