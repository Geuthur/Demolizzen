"""What an EVE id stands for: its kind (alliance, corporation, system, …) and name.

Asked from ESI, EVE's public API, without any token. The panel only uses this
to describe ids on its pages; when ESI cannot say, the pages show the bare id.
"""

# Standard Library
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass

# Third Party
import aiohttp

logger = logging.getLogger(__name__)

# The same API version the bot uses (demolizzen/core/openapi.py).
NAMES_URL = "https://esi.evetech.net/latest/universe/names/"
HEADERS = {"User-Agent": "Demolizzen panel (https://github.com/Geuthur/Demolizzen)"}
# A page waits for this at most; afterwards it shows the ids without names.
TIMEOUT = aiohttp.ClientTimeout(total=4)

# Names and kinds hardly ever change.
KNOWN_SECONDS = 24 * 3600
# An id ESI did not explain, or could not be asked about, is tried again later.
UNKNOWN_SECONDS = 300
# ESI takes positive 32-bit numbers only.
_MAX_ID = 2**31 - 1

_clock = time.monotonic
_cache: dict[int, tuple[float, "EveName | None"]] = {}


class EsiError(Exception):
    """ESI could not be asked or answered with something unusable."""


class EsiUnknownId(EsiError):
    """ESI knows at least one of the ids not; it then explains none of them."""


@dataclass(frozen=True)
class EveName:
    id: int
    # ESI's category: alliance, corporation, character, solar_system, region, …
    kind: str
    name: str


def clear() -> None:
    """Forget everything that was looked up."""
    _cache.clear()


async def fetch(ids: list[int], session_factory=aiohttp.ClientSession) -> list[dict]:
    """Ask ESI for the kind and name of the ids."""
    try:
        async with session_factory(timeout=TIMEOUT) as session:
            async with session.post(NAMES_URL, json=ids, headers=HEADERS) as response:
                if response.status == 404:
                    raise EsiUnknownId("ESI does not know one of the ids")
                if response.status != 200:
                    logger.warning("ESI answered %s", response.status)
                    raise EsiError(f"ESI answered {response.status}")
                answer = await response.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, ValueError) as error:
        logger.warning("ESI request failed: %r", error)
        raise EsiError("ESI could not be reached") from error
    if not isinstance(answer, list):
        logger.warning("ESI answered with %s instead of a list", type(answer).__name__)
        raise EsiError("ESI answered with something unexpected")
    return answer


async def lookup(ids: Iterable[int]) -> dict[int, EveName]:
    """The kind and name of every id ESI can explain. Never raises.

    An id that is missing from the answer is unknown to ESI, or ESI could not
    be asked right now.
    """
    wanted = [number for number in dict.fromkeys(ids) if 0 < number <= _MAX_ID]
    now = _clock()
    open_ids = [
        number for number in wanted if number not in _cache or _cache[number][0] <= now
    ]
    if open_ids:
        await _ask(open_ids)
    found = {number: _cache[number][1] for number in wanted if number in _cache}
    return {number: name for number, name in found.items() if name is not None}


async def _ask(ids: list[int]) -> None:
    """Fill the cache for the ids, one way or the other."""
    try:
        _remember(ids, await fetch(ids))
    except EsiUnknownId:
        if len(ids) == 1:
            _remember(ids, [])
            return
        # One unknown id spoils the whole list: ask for each on its own.
        for position, number in enumerate(ids):
            try:
                _remember([number], await fetch([number]))
            except EsiUnknownId:
                _remember([number], [])
            except EsiError:
                _remember(ids[position:], [])
                return
    except EsiError:
        # Not asked again on every page view while ESI is away.
        _remember(ids, [])


def _remember(ids: list[int], answer: list[dict]) -> None:
    now = _clock()
    names: dict[int, EveName] = {}
    for entry in answer:
        try:
            name = EveName(int(entry["id"]), str(entry["category"]), str(entry["name"]))
        except (KeyError, TypeError, ValueError):
            continue
        names[name.id] = name
    for number in ids:
        name = names.get(number)
        lifetime = KNOWN_SECONDS if name is not None else UNKNOWN_SECONDS
        _cache[number] = (now + lifetime, name)
