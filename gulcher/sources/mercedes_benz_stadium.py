from urllib.parse import urljoin

from bs4 import BeautifulSoup

from gulcher.models import EventRecord
from gulcher.utils import DATE_PATTERN, TIME_PATTERN, fetch_html, parse_event_date_and_time


MERCEDES_BENZ_STADIUM_EVENTS_URL = "https://www.mercedesbenzstadium.com/events"


def fetch_events() -> list[EventRecord]:
    html = fetch_html(MERCEDES_BENZ_STADIUM_EVENTS_URL)
    soup = BeautifulSoup(html, "html.parser")
    normalized_events: list[EventRecord] = []
    seen_urls: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if "/events/" not in href:
            continue
        if href == "/events" or href.endswith("/events"):
            continue

        detail_link = urljoin(MERCEDES_BENZ_STADIUM_EVENTS_URL, href)
        if detail_link in seen_urls:
            continue

        event_block = None
        for ancestor in link.parents:
            if not getattr(ancestor, "name", None):
                continue
            if ancestor.name not in {"article", "section", "div", "li"}:
                continue

            block_text = ancestor.get_text("\n", strip=True)
            if "Date" in block_text and "Time" in block_text:
                event_block = ancestor
                break

        if event_block is None:
            continue

        summary_node = event_block.find(["h2", "h3", "h4"])
        summary = (summary_node.get_text(" ", strip=True) if summary_node else link.get_text(" ", strip=True)).strip()
        if not summary:
            continue

        block_text = event_block.get_text("\n", strip=True)
        date_match = DATE_PATTERN.search(block_text)
        time_match = TIME_PATTERN.search(block_text)
        if date_match is None:
            continue

        time_value = time_match.group(0) if time_match is not None else None

        seen_urls.add(detail_link)
        normalized_events.append(
            {
                "source": "mercedes-benz-stadium",
                "summary": summary,
                "description": None,
                "url": detail_link,
                "location": "Mercedes-Benz Stadium",
                "start_at": parse_event_date_and_time(date_match.group(0), time_value),
                "end_at": None,
            }
        )

    return normalized_events
