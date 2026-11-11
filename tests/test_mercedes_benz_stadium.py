import unittest
from unittest.mock import patch

from gulcher.sources import mercedes_benz_stadium as stadium


class StadiumEventsTests(unittest.TestCase):
    def test_featured_slide_cannot_borrow_page_heading_or_suppress_real_card(self):
        html = """
        <div class="page--wrapper">
          <h1>Upcoming Events at Mercedes-Benz Stadium</h1>
          <div class="home_slide--item w-dyn-item">
            <h2>Featured Concert</h2><div>November 11, 2026</div>
            <a href="/events/concert">Event Details</a>
          </div>
          <div class="events--item w-dyn-item">
            <div class="events_feature_content">
              <h3>Featured Concert</h3>
              <div>Date</div><div>November 11, 2026</div>
              <div>Time</div><div>7:30 PM</div>
              <a href="/events/concert">Event Details</a>
              <a href="https://mbssuites.com/events/concert">Event Details</a>
            </div>
          </div>
        </div>
        """
        with patch.object(stadium, "fetch_html", return_value=html) as fetch:
            events = stadium.fetch_events()

        fetch.assert_called_once_with(stadium.MERCEDES_BENZ_STADIUM_EVENTS_URL)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["summary"], "Featured Concert")
        self.assertEqual(events[0]["url"], "https://www.mercedesbenzstadium.com/events/concert")
        self.assertEqual(events[0]["start_at"].isoformat(), "2026-11-11T19:30:00-05:00")

    def test_featured_slide_without_an_event_card_is_skipped(self):
        html = """
        <div><h1>Upcoming Events at Mercedes-Benz Stadium</h1>
          <div class="w-dyn-item"><h2>Featured Concert</h2>
            <a href="/events/concert">Event Details</a>
          </div>
          <div>Date November 11, 2026 Time 7:30 PM</div>
        </div>
        """
        with patch.object(stadium, "fetch_html", return_value=html):
            self.assertEqual(stadium.fetch_events(), [])


if __name__ == "__main__":
    unittest.main()
