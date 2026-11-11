import os
import unittest
from datetime import datetime
from unittest.mock import Mock, patch

import requests

from gulcher.sources import ticketmaster as tm
from gulcher.utils import DEFAULT_TIMEZONE


VENUE = next(iter(tm.VENUES))


def api_event():
    return {
        "name": "Atlanta Falcons v Kansas City Chiefs", "url": "https://www.ticketmaster.com/event/test",
        "dates": {"start": {"localDate": "2026-11-15", "dateTime": "2026-11-15T18:00:00Z"},
                  "status": {"code": "onsale"}},
        "_embedded": {"venues": [{"id": VENUE}]},
        "classifications": [{"segment": {"name": "Sports"}, "type": {"name": "Group"}}],
    }


class TicketmasterTests(unittest.TestCase):
    def test_normalizes_kickoff_and_venue(self):
        event = tm.normalize_event(api_event(), VENUE)
        self.assertEqual(event["start_at"].isoformat(), "2026-11-15T13:00:00-05:00")
        self.assertEqual(event["location"], "Mercedes-Benz Stadium")

    def test_excludes_addons_cancelled_unscheduled_and_other_venues(self):
        cases = []
        for status in ["cancelled", "postponed"]:
            item = api_event()
            item["dates"]["status"]["code"] = status
            cases.append(item)
        for flag in ["dateTBA", "dateTBD"]:
            item = api_event()
            item["dates"]["start"][flag] = True
            cases.append(item)
        item = api_event()
        item["classifications"][0]["type"]["name"] = "Upsell"
        cases.append(item)
        item = api_event()
        item["_embedded"]["venues"][0]["id"] = "other"
        cases.append(item)
        for item in cases:
            with self.subTest(item=item):
                self.assertIsNone(tm.normalize_event(item, VENUE))

    def test_unknown_time_does_not_use_placeholder_timestamp(self):
        item = api_event()
        item["dates"]["start"]["timeTBA"] = True
        self.assertEqual(tm.normalize_event(item, VENUE)["start_at"].hour, 0)

    def test_missing_key_skips_network(self):
        with patch.dict(os.environ, {"TICKETMASTER_API_KEY": ""}), patch.object(tm.requests, "get") as get:
            self.assertEqual(tm.fetch_events(), [])
        get.assert_not_called()

    def test_paginates_each_venue(self):
        responses = [Mock(), Mock(), Mock()]
        for response, pages in zip(responses, [2, 2, 1]):
            response.json.return_value = {"page": {"totalPages": pages}}
        with patch.dict(os.environ, {"TICKETMASTER_API_KEY": "test-key"}), patch.object(
            tm.requests, "get", side_effect=responses
        ) as get:
            self.assertEqual(tm.fetch_events(), [])
        self.assertEqual([c.kwargs["params"]["page"] for c in get.call_args_list], [0, 1, 0])
        self.assertEqual([c.kwargs["params"]["venueId"] for c in get.call_args_list],
                         [VENUE, VENUE, "KovZpa2Xke"])

    def test_request_errors_do_not_disclose_key(self):
        with patch.dict(os.environ, {"TICKETMASTER_API_KEY": "test-key"}), patch.object(
            tm.requests, "get", side_effect=requests.RequestException("https://example.com?apikey=test-key")
        ):
            with self.assertRaises(RuntimeError) as error:
                tm.fetch_events()
        self.assertNotIn("test-key", str(error.exception))

    def test_merges_sports_title_variants_and_fills_unknown_time(self):
        supplement = tm.normalize_event(api_event(), VENUE)
        existing = {**supplement, "summary": "Atlanta Falcons vs. Kansas City Chiefs", "source": "atlanta-falcons"}
        self.assertEqual(tm.merge_events([existing], [supplement]), [existing])
        existing = {**existing, "summary": "SEC Championship", "start_at": datetime(2026, 12, 5, tzinfo=DEFAULT_TIMEZONE)}
        supplement = {**supplement, "summary": "2026 Sec Championship Game", "start_at": datetime(2026, 12, 5, 16, tzinfo=DEFAULT_TIMEZONE)}
        merged = tm.merge_events([existing], [supplement])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["start_at"].hour, 16)
        self.assertEqual(merged[0]["summary"], "SEC Championship")

    def test_preserves_distinct_dates_venues_and_showtimes(self):
        event = tm.normalize_event(api_event(), VENUE)
        for overrides in [
            {"start_at": event["start_at"].replace(hour=19)},
            {"start_at": event["start_at"].replace(day=16)},
            {"location": "State Farm Arena"},
            {"summary": "Atlanta Falcons vs. Detroit Lions"},
        ]:
            with self.subTest(overrides=overrides):
                self.assertEqual(len(tm.merge_events([event], [{**event, **overrides}])), 2)

    def test_olivia_title_and_time_conflicts_merge_on_each_date(self):
        base = tm.normalize_event(api_event(), VENUE)
        primary, supplements = [], []
        for day in [11, 12]:
            primary.append({**base, "source": "state-farm-arena", "location": "State Farm Arena",
                            "summary": "Olivia Rodrigo", "description": "Venue details",
                            "start_at": datetime(2026, 11, day, 19, 30, tzinfo=DEFAULT_TIMEZONE)})
            supplements.append({**primary[-1], "source": "ticketmaster",
                                "summary": "Olivia Rodrigo: The Unraveled Tour",
                                "start_at": datetime(2026, 11, day, 19, tzinfo=DEFAULT_TIMEZONE)})
        merged = tm.merge_events(primary, supplements)
        self.assertEqual(len(merged), 2)
        self.assertEqual([e["start_at"].day for e in merged], [11, 12])
        self.assertTrue(all(e["start_at"].hour == 19 and e["start_at"].minute == 0 for e in merged))
        self.assertTrue(all(e["description"] == "Venue details" for e in merged))

    def test_ambiguous_nearby_performances_are_not_collapsed(self):
        event = tm.normalize_event(api_event(), VENUE)
        primary = {**event, "source": "state-farm-arena"}
        supplements = [event, {**event, "start_at": event["start_at"].replace(minute=30)}]
        self.assertEqual(len(tm.merge_events([primary], supplements)), 3)
        primary_shows = [primary, {**primary, "start_at": primary["start_at"].replace(minute=30)}]
        self.assertEqual(len(tm.merge_events(primary_shows, [event])), 3)
