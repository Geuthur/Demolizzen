"""Asks the appraisal service for market prices."""

# Standard Library
import logging

# Third Party
import aiohttp

# Demolizzen
from demolizzen.services.errors import PriceUnavailable
from demolizzen.services.prices import Quote

URL = "https://appraise.gnf.lt/appraisal/structured.json"
TIMEOUT = aiohttp.ClientTimeout(total=10)

logger = logging.getLogger(__name__)


def _price(prices: dict, side: str, bound: str) -> int:
    return int(round(float((prices.get(side) or {}).get(bound) or 0)))


def _quotes(data) -> list[Quote]:
    """Read the quotes from the answer; raises if it is not built as expected."""
    quotes = []
    for item in data["appraisal"]["items"]:
        prices = item.get("prices") or {}
        quotes.append(
            Quote(
                item_name=str(item["name"]),
                sell=_price(prices, "sell", "min"),
                buy=_price(prices, "buy", "max"),
            )
        )
    return quotes


class AppraisalClient:
    """Fetches lowest sell and highest buy prices of items in a market.

    Every failure – no answer in time, an error status, an answer that cannot
    be read – is raised as :class:`PriceUnavailable`, so a failure can never be
    mistaken for a price.
    """

    def __init__(self, get_session, headers: dict | None = None):
        self._get_session = get_session
        self._headers = headers or {}

    async def quotes(self, market: str, names: list[str]) -> list[Quote]:
        session = self._get_session()
        if session is None:
            raise PriceUnavailable(market)
        try:
            async with session.post(
                URL,
                json={
                    "market_name": market,
                    "items": [{"name": name} for name in names],
                },
                headers=self._headers,
                timeout=TIMEOUT,
            ) as response:
                if response.status != 200:
                    logger.warning(
                        "Appraisal service answered with status %s for market %s.",
                        response.status,
                        market,
                    )
                    raise PriceUnavailable(market)
                return _quotes(await response.json(content_type=None))
        except (aiohttp.ClientError, TimeoutError) as error:
            logger.warning("Appraisal service is unreachable: %r", error)
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            logger.warning("Appraisal service sent an unreadable answer: %r", error)
        raise PriceUnavailable(market)
