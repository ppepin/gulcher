from bs4 import BeautifulSoup
from icalendar import Calendar

from gulcher.models import EventRecord
from gulcher.utils import fetch_bytes, fetch_html, parse_event_datetime


ATLANTA_UNITED_DOWNLOADS_URL = "https://www.atlutd.com/schedule/downloadable-calendars"
ATLANTA_UNITED_LOCATION = "Mercedes-Benz Stadium"


def normalize_description(description: str | None) -> str | None:
    if not description:
        return None

    cleaned = description.strip()
    ticket_marker = cleaned.find("View tickets:")
    if ticket_marker != -1:
        cleaned = cleaned[:ticket_marker].rstrip()

    return cleaned or None


def normalize_location(location: str | None) -> str:
    if not location:
        return ATLANTA_UNITED_LOCATION

    cleaned = location.strip()
    if cleaned.startswith(ATLANTA_UNITED_LOCATION):
        return ATLANTA_UNITED_LOCATION
    return cleaned


def extract_home_calendar_url(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    home_heading = soup.find(string=lambda text: isinstance(text, str) and "Home Matches" in text)
    if home_heading is None:
        return None

    for link in home_heading.parent.find_all_next("a", href=True):
        link_text = link.get_text(" ", strip=True)
        href = link["href"].strip()
        if "Away Matches" in link_text:
            break
        if "Sync to Apple" not in link_text and "Sync to Outlook" not in link_text:
            continue
        if href.endswith(".ics"):
            return href.replace("%20", " ")

    return None


def fetch_events() -> list[EventRecord]:
    downloads_html = fetch_html(ATLANTA_UNITED_DOWNLOADS_URL)
    calendar_url = extract_home_calendar_url(downloads_html)
    if not calendar_url:
        return []

    calendar_bytes = fetch_bytes(calendar_url)
    calendar = Calendar.from_ical(calendar_bytes)
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
                "description": normalize_description(str(component.get("description", "")).strip() or None),
                "url": url,
                "location": normalize_location(str(component.get("location", ATLANTA_UNITED_LOCATION)).strip() or None),
                "start_at": start_at,
                "end_at": end_at,
            }
        )

    return events
