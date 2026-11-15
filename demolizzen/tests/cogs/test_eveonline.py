# Standard Library
import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# Discord
import discord

# Django
from django.test import TestCase

# Demolizzen
from demolizzen.cogs.eveonline.eveonline import EveOnline
from demolizzen.models import EvePricecache, InvTypes
from demolizzen.services.errors import PriceUnavailable
from demolizzen.services.prices import Quote
from demolizzen.tests.helpers import make_ctx, make_guild
from demolizzen.utils.autocomplete import search_items


class EveOnlineTestCase(TestCase):
    def setUp(self):
        self.bot = MagicMock()
        self.cog = EveOnline(self.bot)
        self.quotes = AsyncMock(return_value=[Quote("Tritanium", 1234567, 4)])
        self.cog.appraisal = SimpleNamespace(quotes=self.quotes)
        self.ctx = make_ctx(make_guild())

    def embed(self) -> discord.Embed:
        return self.ctx.respond.await_args.kwargs["embed"]


class PriceCommandTest(EveOnlineTestCase):
    async def price(self, item_name="tritanium", tradehub=None):
        await self.cog.priceinfo.callback(self.cog, self.ctx, item_name, tradehub)

    async def test_price_shows_sell_and_buy(self):
        await self.price(tradehub="Amarr")

        embed = self.embed()
        self.assertEqual(
            embed.title, "Tradehub: **Amarr VIII (Oris) - Emperor Family Academy**"
        )
        self.assertEqual(embed.description, "**Tritanium**")
        self.assertEqual(
            [(field.name, field.value) for field in embed.fields],
            [("Sell", "`1,234,567 ISK`"), ("Buy", "`4 ISK`")],
        )
        self.quotes.assert_awaited_once_with("amarr", ["tritanium"])

    async def test_price_defers_before_asking(self):
        async def quotes(market, names):
            self.ctx.defer.assert_awaited_once()
            return [Quote("Tritanium", 5, 4)]

        self.quotes.side_effect = quotes

        await self.price()

        self.quotes.assert_awaited_once()
        self.ctx.respond.assert_awaited_once()

    async def test_price_without_tradehub_uses_jita(self):
        await self.price()

        self.quotes.assert_awaited_once_with("jita", ["tritanium"])
        self.assertIn("Jita IV - Moon 4", self.embed().title)

    async def test_second_request_is_answered_from_the_cache(self):
        await self.price()
        await self.price()

        self.quotes.assert_awaited_once()
        self.assertEqual(self.embed().fields[0].value, "`1,234,567 ISK`")

    async def test_other_tradehub_is_asked_separately(self):
        await self.price(tradehub="Jita")
        self.quotes.return_value = [Quote("Tritanium", 9, 8)]
        await self.price(tradehub="Amarr")

        self.assertEqual(self.embed().fields[0].value, "`9 ISK`")
        self.assertEqual(await EvePricecache.objects.acount(), 2)

    async def test_unknown_item_gets_a_clear_message(self):
        self.quotes.return_value = []

        await self.price("@everyone")

        self.ctx.respond.assert_awaited_once()
        call = self.ctx.respond.await_args
        self.assertEqual(
            call.args[0], "No market price found for **@everyone** in Jita."
        )
        self.assertNotIn("embed", call.kwargs)
        mentions = call.kwargs["allowed_mentions"]
        self.assertFalse(mentions.everyone or mentions.users or mentions.roles)

    async def test_unavailable_service_gets_a_clear_message(self):
        self.quotes.side_effect = PriceUnavailable("hek")

        await self.price(tradehub="Hek")

        self.assertEqual(
            self.ctx.respond.await_args.args[0],
            "The price service did not answer for Hek. Please try again later.",
        )

    def test_price_service_uses_the_bot_session(self):
        cog = EveOnline(self.bot)
        self.bot.session = "session"

        self.assertEqual(cog.appraisal._get_session(), "session")
        self.assertIn("User-Agent", cog.appraisal._headers)

    def test_price_list_modal_is_gone(self):
        self.assertFalse(hasattr(EveOnline, "PriceListModal"))
        with self.assertRaises(ImportError):
            importlib.import_module("demolizzen.utils.pricehandler")

    def test_cooldown_is_reported_once_by_the_bot(self):
        self.assertFalse(EveOnline.status.has_error_handler())
        self.assertFalse(EveOnline.priceinfo.has_error_handler())


class StatusCommandTest(EveOnlineTestCase):
    async def status(self):
        await self.cog.status.callback(self.cog, self.ctx)
        (field,) = self.embed().fields
        return field.name, field.value

    async def test_status_online(self):
        self.bot.esi_data.server_info = AsyncMock(
            return_value=SimpleNamespace(start_time="2026-11-15", players=12345)
        )

        self.assertEqual(
            await self.status(), ("Server Online 🟢", "12,345 players connected.")
        )
        self.ctx.defer.assert_awaited_once()

    async def test_status_offline(self):
        self.bot.esi_data.server_info = AsyncMock(return_value=None)

        self.assertEqual(
            await self.status(),
            ("Server Offline 🔴", "Tranquility is not responding."),
        )

    async def test_status_timeout_counts_as_offline(self):
        async def never(*args):
            await asyncio.sleep(30)

        self.bot.esi_data.server_info = never

        with patch.object(EveOnline, "STATUS_TIMEOUT", 0.01):
            name, _ = await self.status()

        self.assertEqual(name, "Server Offline 🔴")
        self.assertEqual(EveOnline.STATUS_TIMEOUT, 10)

    async def test_status_error_counts_as_offline(self):
        self.bot.esi_data.server_info = AsyncMock(side_effect=RuntimeError("boom"))

        with self.assertLogs("demolizzen.cogs.eveonline.eveonline", "WARNING"):
            name, _ = await self.status()

        self.assertEqual(name, "Server Offline 🔴")


class AutocompleteTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        InvTypes.objects.bulk_create(
            [
                InvTypes(typeID=1, typeName="Caldari Navy Raven", published=True),
                InvTypes(typeID=2, typeName="Raven", published=True),
            ]
        )

    async def test_autocomplete_returns_matching_names(self):
        ctx = SimpleNamespace(value="rav", bot=MagicMock())

        self.assertEqual(await search_items(ctx), ["Raven", "Caldari Navy Raven"])

    async def test_autocomplete_without_input(self):
        ctx = SimpleNamespace(value=None, bot=MagicMock())

        self.assertEqual(await search_items(ctx), [])

    async def test_autocomplete_survives_a_database_error(self):
        ctx = SimpleNamespace(value="rav", bot=MagicMock())

        with patch(
            "demolizzen.utils.autocomplete.prices.search_item_names",
            AsyncMock(side_effect=RuntimeError("database away")),
        ):
            self.assertEqual(await search_items(ctx), [])

        ctx.bot.logger.error.assert_called_once()
