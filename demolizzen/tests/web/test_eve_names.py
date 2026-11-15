# Standard Library
from unittest.mock import patch

# Third Party
import aiohttp

# Django
from django.test import SimpleTestCase

# Demolizzen
from demolizzen.tests.web.test_discord_api import Answer, FakeSession
from demolizzen.web import eve_names
from demolizzen.web.eve_names import EsiError, EsiUnknownId, EveName

VOW = {"category": "alliance", "id": 99003581, "name": "Voices of War"}
JITA = {"category": "solar_system", "id": 30000142, "name": "Jita"}


class FetchTest(SimpleTestCase):
    """The one request the panel sends to EVE's public API."""

    async def test_ids_are_posted_and_the_answer_returned(self):
        http = FakeSession(Answer(data=[VOW, JITA]))

        answer = await eve_names.fetch([99003581, 30000142], session_factory=http)

        self.assertEqual(answer, [VOW, JITA])
        ((method, url, options),) = http.requests
        self.assertEqual(
            (method, url), ("POST", "https://esi.evetech.net/latest/universe/names/")
        )
        self.assertEqual(options["json"], [99003581, 30000142])
        self.assertIn("Demolizzen", options["headers"]["User-Agent"])
        # The page must not hang on a slow API.
        self.assertLessEqual(http.session_options["timeout"].total, 5)

    async def test_an_id_esi_does_not_know_is_told_apart_from_an_outage(self):
        with self.assertRaises(EsiUnknownId):
            await eve_names.fetch([5], session_factory=FakeSession(Answer(status=404)))

    async def test_errors_timeouts_and_bad_answers_are_esi_errors(self):
        answers = (
            Answer(status=502),
            Answer(error=aiohttp.ClientConnectionError("down")),
            Answer(error=TimeoutError()),
            Answer(broken=True),
            Answer(data={"error": "not a list"}),
        )
        for answer in answers:
            with self.subTest(answer=vars(answer)), self.assertLogs(level="WARNING"):
                with self.assertRaises(EsiError):
                    await eve_names.fetch([5], session_factory=FakeSession(answer))


class LookupTest(SimpleTestCase):
    def setUp(self):
        eve_names.clear()
        self.now = 1000.0
        self.enterContext(patch.object(eve_names, "_clock", lambda: self.now))
        self.asked: list[list[int]] = []
        self.known = {99003581: VOW, 30000142: JITA}
        self.down = False
        self.enterContext(patch.object(eve_names, "fetch", self.fetch))

    async def fetch(self, ids):
        self.asked.append(list(ids))
        if self.down:
            raise EsiError("ESI could not be reached")
        if any(number not in self.known for number in ids):
            raise EsiUnknownId("ESI does not know one of the ids")
        return [self.known[number] for number in ids]

    async def test_kind_and_name_come_back_per_id(self):
        names = await eve_names.lookup([99003581, 30000142])

        self.assertEqual(
            names,
            {
                99003581: EveName(99003581, "alliance", "Voices of War"),
                30000142: EveName(30000142, "solar_system", "Jita"),
            },
        )
        self.assertEqual(self.asked, [[99003581, 30000142]])

    async def test_known_ids_are_not_asked_again_for_a_day(self):
        await eve_names.lookup([99003581])
        self.now += eve_names.KNOWN_SECONDS - 1
        await eve_names.lookup([99003581, 99003581])
        self.assertEqual(len(self.asked), 1)

        self.now += 2
        await eve_names.lookup([99003581])
        self.assertEqual(len(self.asked), 2)

    async def test_one_unknown_id_does_not_cost_the_others_their_names(self):
        # ESI refuses the whole list when one id is unknown.
        names = await eve_names.lookup([99003581, 424242, 30000142])

        self.assertEqual(set(names), {99003581, 30000142})
        self.assertEqual(
            self.asked, [[99003581, 424242, 30000142], [99003581], [424242], [30000142]]
        )

    async def test_unknown_id_is_left_alone_for_a_while(self):
        await eve_names.lookup([424242])
        await eve_names.lookup([424242])
        self.assertEqual(len(self.asked), 1)

        self.now += eve_names.UNKNOWN_SECONDS + 1
        await eve_names.lookup([424242])
        self.assertEqual(len(self.asked), 2)

    async def test_outage_gives_no_names_and_is_not_asked_about_on_every_page(self):
        self.down = True

        self.assertEqual(await eve_names.lookup([99003581, 30000142]), {})
        self.assertEqual(await eve_names.lookup([99003581]), {})
        # One request, not one per id and not one per page view.
        self.assertEqual(self.asked, [[99003581, 30000142]])

        self.down = False
        self.now += eve_names.UNKNOWN_SECONDS + 1
        self.assertEqual(set(await eve_names.lookup([99003581])), {99003581})

    async def test_ids_esi_cannot_hold_are_never_sent(self):
        # ESI answers 400 to anything outside a positive 32-bit number.
        self.assertEqual(await eve_names.lookup([0, -5, 2**31, 10**11]), {})
        self.assertEqual(self.asked, [])

    async def test_nothing_to_look_up_asks_nothing(self):
        self.assertEqual(await eve_names.lookup([]), {})
        self.assertEqual(self.asked, [])

    async def test_surprising_answer_never_breaks_the_page(self):
        self.known[7] = {"id": 7}  # no category, no name

        self.assertEqual(await eve_names.lookup([7]), {})
