import unittest
from datetime import datetime
from unittest.mock import patch

from gulcher.calendar import get_upcoming_events
from gulcher.sources import atlanta_united as united
from gulcher.utils import DEFAULT_TIMEZONE


class AtlantaUnitedTests(unittest.TestCase):
    def test_selects_home_feed_with_old_and_new_headings(self):
        for heading in ["Home Matches", "Atlanta United Sprint Season 2027 Home Schedule"]:
            html = f"""<p>Full Schedule</p><a href="/full.ics">Sync to Apple</a>
                <p><strong>{heading}</strong></p>
                <a href="/home%20schedule.ics">Sync to Apple</a>
                <p>Away Schedule</p><a href="/away.ics">Sync to Apple</a>"""
            with self.subTest(heading=heading):
                self.assertEqual(united.extract_home_calendar_url(html),
                                 "https://www.atlutd.com/home%20schedule.ics")

    def test_does_not_fall_through_to_away_calendar(self):
        html = """<h2>Home Schedule</h2><p>Coming soon</p>
            <h2>Away Schedule</h2><a href="/away.ics">Sync to Apple</a>"""
        self.assertIsNone(united.extract_home_calendar_url(html))

    def test_missing_home_link_reports_source_failure(self):
        with patch.object(united, "fetch_html", return_value="<p>Schedule coming soon</p>"):
            with self.assertRaisesRegex(RuntimeError, "home calendar link"):
                united.fetch_events()

    def test_calendar_preserves_times_and_stays_outside_current_window(self):
        calendar = b"\r\n".join([
            b"BEGIN:VCALENDAR", b"VERSION:2.0", b"BEGIN:VEVENT",
            b"SUMMARY:Atlanta United vs Toronto FC",
            b"DTSTART;TZID=America/New_York:20270220T190000",
            b"DTEND;TZID=America/New_York:20270220T210000",
            b"LOCATION:Mercedes-Benz Stadium - Atlanta, GA",
            b"DESCRIPTION:Home match. View tickets: https://example.com",
            b"END:VEVENT", b"END:VCALENDAR", b"",
        ])
        with patch.object(united, "fetch_html", return_value=
                          '<h2>Home Schedule</h2><a href="/home.ics">Sync to Outlook</a>'), \
                patch.object(united, "fetch_bytes", return_value=calendar):
            events = united.fetch_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["start_at"].isoformat(), "2027-02-20T19:00:00-05:00")
        self.assertEqual(events[0]["end_at"].isoformat(), "2027-02-20T21:00:00-05:00")
        self.assertEqual(events[0]["location"], united.ATLANTA_UNITED_LOCATION)
        self.assertEqual(events[0]["description"], "Home match.")
        with patch("gulcher.calendar.datetime", wraps=datetime) as clock:
            clock.now.return_value = datetime(2026, 11, 11, 12, tzinfo=DEFAULT_TIMEZONE)
            self.assertEqual(get_upcoming_events(events), [])
