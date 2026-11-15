"""Level-up and rank cards.

Loading images never blocks the bot: downloads go through the bot's aiohttp
session with a time limit and a size limit, and the drawing functions are plain
synchronous functions that the cog runs in a worker thread.
"""

# Standard Library
import asyncio
from collections import OrderedDict
from io import BytesIO
from pathlib import Path

# Third Party
import aiohttp
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Demolizzen
from demolizzen import config
from demolizzen.utils.functions import translate


class AssetError(Exception):
    """An image could not be loaded."""


class AssetLoader:
    """Loads image bytes from a URL or a local path.

    Images that rarely change (backgrounds, borders) are kept in a small cache
    so a level-up does not download them again every time.
    """

    TIMEOUT = 10
    MAX_BYTES = 8 * 1024 * 1024
    CACHE_SIZE = 64

    def __init__(self, get_session):
        # The session is looked up on use: the bot creates it when it starts.
        self._get_session = get_session
        self._cache: OrderedDict[str, bytes] = OrderedDict()

    async def load(self, source: str, cache: bool = True) -> bytes:
        """Return the bytes behind ``source``. Raises :class:`AssetError`."""
        source = str(source)
        if cache and source in self._cache:
            self._cache.move_to_end(source)
            return self._cache[source]

        if source.startswith(("http://", "https://")):
            data = await self._download(source)
        else:
            data = await self._read_file(source)

        if cache:
            self._cache[source] = data
            while len(self._cache) > self.CACHE_SIZE:
                self._cache.popitem(last=False)
        return data

    async def _download(self, url: str) -> bytes:
        session = self._get_session()
        if session is None:
            raise AssetError("No HTTP session available.")
        chunks, size = [], 0
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)
            ) as response:
                if response.status >= 400:
                    raise AssetError(f"{url} answered with status {response.status}.")
                async for chunk in response.content.iter_chunked(64 * 1024):
                    size += len(chunk)
                    if size > self.MAX_BYTES:
                        raise AssetError(
                            f"{url} is larger than {self.MAX_BYTES} bytes."
                        )
                    chunks.append(chunk)
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise AssetError(f"{url} could not be loaded: {exc!r}") from exc
        return b"".join(chunks)

    @staticmethod
    async def _read_file(path: str) -> bytes:
        try:
            return await asyncio.to_thread(Path(path).read_bytes)
        except OSError as exc:
            raise AssetError(f"{path} could not be read: {exc!r}") from exc


def _open(data: bytes) -> Image.Image:
    return Image.open(BytesIO(data)).convert("RGBA")


def _round(image: Image.Image) -> Image.Image:
    """Cut the image to a circle."""
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, *image.size), fill=255)
    image.putalpha(mask)
    return image


def _png(image: Image.Image) -> BytesIO:
    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output


def render_level_up_card(
    background: bytes,
    shade: bytes,
    avatar: bytes,
    border: bytes,
    *,
    name: str,
    level: int,
    xp_into_level: int,
) -> BytesIO:
    """Draw the card that announces a new level. Returns a PNG, 900×270."""
    blur = ImageFilter.GaussianBlur(radius=config.LEVEL_UP_BLUR)
    card = _open(background).resize((900, 270)).filter(blur)
    overlay = _open(shade).resize((900, 270)).filter(blur)
    card.paste(overlay, (0, 0), overlay)

    profile = _round(_open(avatar).resize((200, 200)))
    frame = _round(_open(border).resize((210, 210)))
    card.paste(frame, (40, 30), frame)
    card.paste(profile, (45, 35), profile)

    big = ImageFont.load_default(size=70)
    medium = ImageFont.load_default(size=50)
    regular = ImageFont.load_default(size=30)
    draw = ImageDraw.Draw(card)
    needed = int(config.XP_PER_LEVEL * level)
    lines = [
        ((600, 50), "LEVEL UP!", big),
        ((600, 100), str(name), regular),
        ((600, 150), f"LEVEL {level:,}", medium),
        ((600, 190), f"{translate(xp_into_level)}/{translate(needed)} XP", regular),
    ]
    for position, text, font in lines:
        draw.text(
            position,
            text,
            font=font,
            fill="white",
            anchor="mm",
            stroke_width=2,
            stroke_fill="black",
        )
    return _png(card)


def render_rank_card(
    background: bytes,
    avatar: bytes,
    border: bytes,
    *,
    name: str,
    experience: int,
    level: int,
    into_level: int,
    needed: int,
    percent: int,
    colour: str,
    blur: int,
    rank: int,
) -> BytesIO:
    """Draw a member's rank card. Returns a PNG, 1050×300."""
    card = _open(background).resize((1050, 300))
    if int(blur) > 0:
        card = card.filter(ImageFilter.GaussianBlur(radius=int(blur)))

    profile = _open(avatar).resize((200, 210))
    frame = _open(border).resize((210, 220))
    card.paste(frame, (30, 40), frame)
    card.paste(profile, (35, 45), profile)

    font_25 = ImageFont.load_default(size=25)
    font_40 = ImageFont.load_default(size=40)
    font_60 = ImageFont.load_default(size=60)
    draw = ImageDraw.Draw(card)

    if config.NAME_COLOUR is True:
        draw.text(
            (260, 40),
            str(name),
            font=font_60,
            fill=colour,
            stroke_fill="black",
            stroke_width=1,
        )
        draw.text(
            (700, 40),
            f"EXP: {translate(experience)}",
            font=font_60,
            fill=colour,
            stroke_fill="black",
            stroke_width=1,
        )
        draw.text((270, 150), f"Level: {level:,}", font=font_25, fill=colour)
    else:
        draw.text((250, 40), str(name), font=font_60, fill="white")
        draw.text(
            (870, 190),
            f"#{rank:,}",
            font=font_40,
            fill="white",
            stroke_fill="black",
            stroke_width=1,
        )
        draw.text((270, 150), f"Level: {level:,}", font=font_25, fill="white")

    # Experience bar: dark track, coloured fill
    bar_x, bar_y, bar_w, bar_h, bar_r = 260, 190, 600, 40, 20
    draw.rounded_rectangle(
        (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h),
        radius=bar_r,
        fill=(40, 40, 40, 180),
    )
    if percent > 5:
        fill_w = int(bar_w * (percent / 100))
        draw.rounded_rectangle(
            (bar_x, bar_y, bar_x + fill_w, bar_y + bar_h), radius=bar_r, fill=colour
        )

    draw.text(
        (845, 145),
        f"Remaining: {translate(into_level)} / {translate(needed)}",
        font=font_25,
        fill="white",
        anchor="ra",
        stroke_fill="black",
        stroke_width=1,
    )
    return _png(card)
