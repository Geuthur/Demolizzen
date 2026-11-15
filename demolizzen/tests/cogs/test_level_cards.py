# Standard Library
import asyncio
import tempfile
from io import BytesIO
from pathlib import Path

# Third Party
import aiohttp
from PIL import Image

# Django
from django.test import SimpleTestCase

# Demolizzen
from demolizzen.cogs.levelsystem._cards import (
    AssetError,
    AssetLoader,
    render_level_up_card,
    render_rank_card,
)
from demolizzen.tests.cogs.level_fakes import FakeResponse, FakeSession, png

URL = "https://cdn.example/avatar.png"


class AssetLoaderTest(SimpleTestCase):
    def loader(self, session):
        return AssetLoader(lambda: session)

    async def test_loads_bytes(self):
        session = FakeSession({URL: b"image-bytes"})

        self.assertEqual(await self.loader(session).load(URL), b"image-bytes")

    async def test_second_load_comes_from_the_cache(self):
        session = FakeSession({URL: b"image-bytes"})
        loader = self.loader(session)

        await loader.load(URL)
        await loader.load(URL)

        self.assertEqual(len(session.calls), 1)

    async def test_uncached_load_asks_again_and_stores_nothing(self):
        session = FakeSession({URL: b"image-bytes"})
        loader = self.loader(session)

        await loader.load(URL, cache=False)
        await loader.load(URL, cache=False)

        self.assertEqual(len(session.calls), 2)

    async def test_request_carries_the_time_limit(self):
        session = FakeSession({URL: b"x"})

        await self.loader(session).load(URL)

        timeout = session.calls[0][1]["timeout"]
        self.assertIsInstance(timeout, aiohttp.ClientTimeout)
        self.assertEqual(timeout.total, AssetLoader.TIMEOUT)
        self.assertEqual(AssetLoader.TIMEOUT, 10)

    async def test_failures_raise_asset_error(self):
        too_big = b"x" * (AssetLoader.MAX_BYTES + 1)
        cases = {
            "not found": FakeResponse(status=404),
            "server error": FakeResponse(status=500),
            "timeout": FakeResponse(error=asyncio.TimeoutError()),
            "connection": FakeResponse(error=aiohttp.ClientConnectionError("down")),
            "too large": FakeResponse(too_big),
        }
        for name, response in cases.items():
            with self.subTest(case=name):
                loader = self.loader(FakeSession({URL: response}))
                with self.assertRaises(AssetError):
                    await loader.load(URL)

    async def test_failed_download_is_not_cached(self):
        session = FakeSession({URL: FakeResponse(status=500)})
        loader = self.loader(session)
        with self.assertRaises(AssetError):
            await loader.load(URL)
        session.responses[URL] = b"now-fine"

        self.assertEqual(await loader.load(URL), b"now-fine")

    async def test_largest_allowed_image_is_accepted(self):
        data = b"x" * AssetLoader.MAX_BYTES
        self.assertEqual(AssetLoader.MAX_BYTES, 8 * 1024 * 1024)

        loaded = await self.loader(FakeSession({URL: data})).load(URL)

        self.assertEqual(len(loaded), AssetLoader.MAX_BYTES)

    async def test_missing_session(self):
        with self.assertRaises(AssetError):
            await AssetLoader(lambda: None).load(URL)

    async def test_local_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "border.png"
            path.write_bytes(b"local-bytes")

            self.assertEqual(
                await self.loader(FakeSession()).load(str(path)), b"local-bytes"
            )
            with self.assertRaises(AssetError):
                await self.loader(FakeSession()).load(str(path) + ".missing")

    async def test_cache_drops_the_oldest_entry(self):
        session = FakeSession(default=b"x")
        loader = self.loader(session)
        urls = [
            f"https://cdn.example/{n}.png" for n in range(AssetLoader.CACHE_SIZE + 1)
        ]
        for url in urls:
            await loader.load(url)
        asked = len(session.calls)

        await loader.load(urls[-1])
        self.assertEqual(len(session.calls), asked)
        await loader.load(urls[0])
        self.assertEqual(len(session.calls), asked + 1)


class CardRenderTest(SimpleTestCase):
    def test_level_up_card(self):
        card = render_level_up_card(
            png((900, 270)),
            png((900, 270), (0, 0, 0, 120)),
            png((128, 128)),
            png((210, 210)),
            name="Alice",
            level=3,
            xp_into_level=40,
        )

        image = Image.open(card)
        self.assertEqual(image.format, "PNG")
        self.assertEqual(image.size, (900, 270))

    def test_rank_card(self):
        card = render_rank_card(
            png((400, 100)),
            png((128, 128)),
            png((210, 220)),
            name="Alice",
            experience=150,
            level=2,
            into_level=50,
            needed=200,
            percent=25,
            colour="#ffffff",
            blur=5,
            rank=2,
        )

        image = Image.open(card)
        self.assertEqual(image.format, "PNG")
        self.assertEqual(image.size, (1050, 300))

    def test_rank_card_without_name_colour(self):
        # Demolizzen
        from demolizzen import config

        original = config.NAME_COLOUR
        config.NAME_COLOUR = False
        try:
            card = render_rank_card(
                png(),
                png(),
                png(),
                name="Alice",
                experience=0,
                level=1,
                into_level=0,
                needed=100,
                percent=0,
                colour="#ffffff",
                blur=0,
                rank=1,
            )
        finally:
            config.NAME_COLOUR = original

        self.assertEqual(Image.open(card).size, (1050, 300))

    def test_broken_image_bytes_raise(self):
        with self.assertRaises(Exception):
            render_level_up_card(
                b"not an image",
                png(),
                png(),
                png(),
                name="Alice",
                level=3,
                xp_into_level=40,
            )

    def test_cards_are_fresh_buffers_at_position_zero(self):
        card = render_level_up_card(
            png(), png(), png(), png(), name="A", level=1, xp_into_level=0
        )

        self.assertIsInstance(card, BytesIO)
        self.assertEqual(card.tell(), 0)
