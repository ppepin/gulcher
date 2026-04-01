import re

from icalendar import Calendar

from gulcher.models import EventRecord
from gulcher.utils import fetch_html, parse_event_datetime


ATLANTA_UNITED_DOWNLOADS_URL = "https://www.atlutd.com/schedule/downloadable-calendars"
ATLANTA_UNITED_LOCATION = "Mercedes-Benz Stadium"


def extract_home_calendar_url(html: str) -> str | None:
    patterns = [
        r"Atlanta United \d{4} Home Matches.*?(https://images\.mlssoccer\.com/raw/upload/[^\"'\s]+\.ics)",
        r"Home Matches.*?(https://images\.mlssoccer\.com/raw/upload/[^\"'\s]+\.ics)",
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            return match.group(1).replace("%20", " ")

    return None


def fetch_events() -> list[EventRecord]:
    downloads_html = fetch_html(ATLANTA_UNITED_DOWNLOADS_URL)
    calendar_url = extract_home_calendar_url(downloads_html)
    if not calendar_url:
        return []

    calendar_text = fetch_html(calendar_url)
    calendar = Calendar.from_ical(calendar_text)
    events: list[EventRecord] = []

    for component in calendar.walk("VEVENT"):
        summary = str(component.get("summary", "")).strip()
        dtstart = component.decoded("dtstart")
        dtend = component.decoded("dtend") if component.get("dtend") else None
        url = str(component.get("url", calendar_url)).strip()

        if not summary:
            continue

        start_at = parse_event_datetime(dtstart.isoformat())
        end_at = parse_event_datetime(dtend.isoformat()) if dtend is not None else None

        events.append(
            {
                "source": "atlanta-united",
                "summary": summary,
                "description": str(component.get("description", "")).strip() or None,
                "url": url,
                "location": str(component.get("location", ATLANTA_UNITED_LOCATION)).strip() or ATLANTA_UNITED_LOCATION,
                "start_at": start_at,
                "end_at": end_at,
            }
        )

    return events
