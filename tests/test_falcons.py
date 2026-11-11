import unittest
from unittest.mock import patch

from gulcher.calendar import build_calendar
from gulcher.sources import falcons


def game_card(opponent, timestamp, venue="Mercedes-Benz Stadium"):
    return f"""<div class="nfl-o-matchup-cards" data-gametime="{timestamp}">
      <p class="nfl-o-matchup-cards__team-full-name">{opponent}</p>
      <span class="nfl-o-matchup-cards__venue--location"> {venue} </span>
    </div>"""


class FalconsEventsTests(unittest.TestCase):
    def test_home_game_reaches_calendar_with_correct_opponent_and_kickoff(self):
        html = game_card("Kansas City Chiefs", "11/15/2026 13:00:00 -05:00")
        with patch.object(falcons, "fetch_html", return_value=html):
            events = falcons.fetch_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["summary"], "Atlanta Falcons vs. Kansas City Chiefs")
        self.assertEqual(events[0]["start_at"].isoformat(), "2026-11-15T13:00:00-05:00")
        with patch("gulcher.calendar.get_upcoming_events", side_effect=lambda events: events):
            calendar_events = build_calendar(events).walk("VEVENT")
        self.assertEqual(len(calendar_events), 1)
        self.assertEqual(calendar_events[0].decoded("dtstart"), events[0]["start_at"])

    def test_away_neutral_and_unscheduled_games_are_excluded(self):
        html = (
            game_card("Minnesota Vikings", "11/29/2026 13:00:00 -05:00", "U.S. Bank Stadium")
            + game_card("Cincinnati Bengals", "11/08/2026 09:30:00 -05:00", "Bernabeu")
            + game_card("Tampa Bay Buccaneers", "01/01/0001 00:00:00 +00:00")
            + game_card("Unknown", "TBD")
        )
        with patch.object(falcons, "fetch_html", return_value=html):
            self.assertEqual(falcons.fetch_events(), [])

    def test_january_game_keeps_following_calendar_year(self):
        html = game_card("New Orleans Saints", "01/03/2027 13:00:00 -05:00")
        with patch.object(falcons, "fetch_html", return_value=html):
            events = falcons.fetch_events()
        self.assertEqual(events[0]["start_at"].isoformat(), "2027-01-03T13:00:00-05:00")
