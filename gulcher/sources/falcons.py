import re
from datetime import datetime

from gulcher.models import EventRecord
from gulcher.utils import DEFAULT_TIMEZONE, fetch_html


FALCONS_SCHEDULE_URL = "https://www.atlantafalcons.com/schedule/"
FALCONS_HOME_VENUE = "Mercedes-Benz Stadium"
DATE_LINE_PATTERN = re.compile(
    r"WEEK\s+\d+\s+·\s+(Sun|Mon|Tue|Wed|Thu|Fri|Sat)\s+(\d{2})/(\d{2})\s+·\s+(\d{1,2}:\d{2}\s+[AP]M)\s+(EDT|EST)"
)
SEASON_YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")


def parse_falcons_start(year: int, month: str, day: str, time_value: str) -> datetime:
    parsed = datetime.strptime(f"{year}-{month}-{day} {time_value}", "%Y-%m-%d %I:%M %p")
    return parsed.replace(tzinfo=DEFAULT_TIMEZONE)


def extract_season_year(html: str) -> int:
    for line in html.splitlines():
        upper_line = line.upper()
        if "REGULAR SEASON" not in upper_line:
            continue

        match = SEASON_YEAR_PATTERN.search(line)
        if match:
            return int(match.group(1))

    return datetime.now(DEFAULT_TIMEZONE).year


def fetch_events() -> list[EventRecord]:
    html = fetch_html(FALCONS_SCHEDULE_URL)
    season_year = extract_season_year(html)
    lines = [line.strip() for line in html.splitlines() if line.strip()]
    events: list[EventRecord] = []
    in_regular_season = False

    for index, line in enumerate(lines):
        if line == "##  REGULAR SEASON":
            in_regular_season = True
            continue
        if line == "##  PRESEASON":
            break
        if not in_regular_season:
            continue

        match = DATE_LINE_PATTERN.search(line)
        if not match:
            continue

        month, day, time_value = match.group(2), match.group(3), match.group(4)
        opponent_name = None
        venue_name = None

        for next_line in lines[index + 1 : index + 15]:
            if next_line in {"Presented By", "BYE"}:
                break
            if next_line == FALCONS_HOME_VENUE:
                venue_name = next_line
                continue
            if next_line.startswith("AT "):
                break
            if next_line.startswith("【") or next_line.startswith("Image:"):
                continue
            if next_line in {"GAME CENTER", "BOOK HOTEL", "BOOK AIRBNB"}:
                continue
            if next_line and "Stadium" not in next_line and next_line not in {"Falcons Takeover", "TRAVEL PACKAGES"}:
                opponent_name = next_line

        if venue_name != FALCONS_HOME_VENUE or not opponent_name:
            continue

        events.append(
            {
                "source": "atlanta-falcons",
                "summary": f"Atlanta Falcons vs. {opponent_name}",
                "description": None,
                "url": FALCONS_SCHEDULE_URL,
                "location": FALCONS_HOME_VENUE,
                "start_at": parse_falcons_start(season_year, month, day, time_value),
                "end_at": None,
            }
        )

    return events
