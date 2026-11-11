from datetime import datetime

from bs4 import BeautifulSoup

from gulcher.models import EventRecord
from gulcher.utils import DEFAULT_TIMEZONE, fetch_html


FALCONS_SCHEDULE_URL = "https://www.atlantafalcons.com/schedule/"
FALCONS_HOME_VENUE = "Mercedes-Benz Stadium"


def fetch_events() -> list[EventRecord]:
    html = fetch_html(FALCONS_SCHEDULE_URL)
    soup = BeautifulSoup(html, "html.parser")
    events: list[EventRecord] = []

    for card in soup.select(".nfl-o-matchup-cards[data-gametime]"):
        venue = card.select_one(".nfl-o-matchup-cards__venue--location")
        opponent = card.select_one(".nfl-o-matchup-cards__team-full-name")
        if venue is None or venue.get_text(strip=True) != FALCONS_HOME_VENUE:
            continue
        if opponent is None:
            continue
        opponent_name = opponent.get_text(" ", strip=True)
        if not opponent_name:
            continue

        try:
            start_at = datetime.strptime(card["data-gametime"], "%m/%d/%Y %H:%M:%S %z")
        except ValueError:
            continue
        # The site uses year 0001 as a placeholder for unscheduled games.
        if start_at.year == 1:
            continue
        start_at = start_at.astimezone(DEFAULT_TIMEZONE)

        events.append(
            {
                "source": "atlanta-falcons",
                "summary": f"Atlanta Falcons vs. {opponent_name}",
                "description": None,
                "url": FALCONS_SCHEDULE_URL,
                "location": FALCONS_HOME_VENUE,
                "start_at": start_at,
                "end_at": None,
            }
        )

    return events
