from datetime import datetime
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from gulcher.models import EventRecord
from gulcher.utils import (
    extract_json_ld,
    fetch_html,
    iter_event_nodes,
    parse_event_date_and_time,
    parse_event_datetime,
)


STATE_FARM_ARENA_LISTING_URL = "https://www.statefarmarena.com/events/index/4"
STATE_FARM_ARENA_SEED_URLS = [
    STATE_FARM_ARENA_LISTING_URL,
    "https://www.statefarmarena.com/",
    "https://www.statefarmarena.com/index.php",
    "https://www.statefarmarena.com/?lang=en",
]
LISTING_DATE_PATTERN = re.compile(
    r"(?:(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+)?"
    r"(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"\s+\d{1,2}(?:\s*-\s*(?:"
    r"(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"\s+)?\d{1,2})?\s+\d{4}"
)
START_TIME_PATTERN = re.compile(r"Event Starts\s+(\d{1,2}:\d{2}\s*[AP]M)")
MONTH_NAME_MAP = {
    "Jan": "January",
    "Feb": "February",
    "Mar": "March",
    "Apr": "April",
    "May": "May",
    "Jun": "June",
    "Jul": "July",
    "Aug": "August",
    "Sep": "September",
    "Oct": "October",
    "Nov": "November",
    "Dec": "December",
}


def extract_state_farm_arena_detail_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if "/events/detail/" not in href:
            continue

        event_url = urljoin(STATE_FARM_ARENA_LISTING_URL, href)
        if event_url in seen:
            continue

        seen.add(event_url)
        urls.append(event_url)

    return urls


def extract_state_farm_arena_listing_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if "/events/index/" not in href:
            continue

        listing_url = urljoin(STATE_FARM_ARENA_LISTING_URL, href)
        if listing_url in seen:
            continue

        seen.add(listing_url)
        urls.append(listing_url)

    return urls


def normalize_state_farm_arena_events(payloads: list[object]) -> list[EventRecord]:
    normalized_events: list[EventRecord] = []

    for payload in payloads:
        for raw_event in iter_event_nodes(payload):
            start_date = raw_event.get("startDate")
            if not start_date:
                continue

            start_at = parse_event_datetime(start_date)
            end_date = raw_event.get("endDate")
            end_at = parse_event_datetime(end_date) if end_date else None
            event_url = raw_event.get("url") or STATE_FARM_ARENA_LISTING_URL

            location_name = None
            location = raw_event.get("location")
            if isinstance(location, dict):
                location_name = location.get("name")
            elif isinstance(location, str):
                location_name = location

            normalized_events.append(
                {
                    "source": "state-farm-arena",
                    "summary": raw_event.get("name", "State Farm Arena Event"),
                    "description": raw_event.get("description"),
                    "url": event_url,
                    "location": location_name,
                    "start_at": start_at,
                    "end_at": end_at,
                }
            )

    return normalized_events


def normalize_listing_date(raw_date: str) -> str:
    cleaned = raw_date.strip()
    parts = cleaned.split()
    if parts and parts[0] in {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}:
        parts = parts[1:]

    if not parts:
        raise ValueError(f"unsupported date format: {raw_date}")

    month = MONTH_NAME_MAP.get(parts[0], parts[0])
    day = parts[1]
    year = parts[-1]
    return f"{month} {day.rstrip(',')}, {year}"


def extract_state_farm_arena_listing_events(listing_html: str, listing_url: str) -> list[EventRecord]:
    soup = BeautifulSoup(listing_html, "html.parser")
    events: list[EventRecord] = []
    seen_keys: set[tuple[str, str]] = set()

    for heading in soup.find_all(["h2", "h3"]):
        summary = heading.get_text(" ", strip=True)
        if not summary or summary in {"Events & Tickets", "Upcoming Events presented by"}:
            continue

        block = heading.parent
        if block is None:
            continue

        block_text = block.get_text("\n", strip=True)
        date_match = LISTING_DATE_PATTERN.search(block_text)
        if date_match is None:
            continue

        time_match = START_TIME_PATTERN.search(block_text)
        raw_date = date_match.group(0)
        time_value = time_match.group(1) if time_match else None

        subtitle = None
        subtitle_node = heading.find_next_sibling(["h4", "h5"])
        if subtitle_node is not None:
            subtitle = subtitle_node.get_text(" ", strip=True) or None

        detail_url = listing_url
        for link in block.find_all("a", href=True):
            href = link["href"].strip()
            link_text = link.get_text(" ", strip=True)
            if "/events/detail/" in href or "More Info" in link_text:
                detail_url = urljoin(STATE_FARM_ARENA_LISTING_URL, href)
                break

        normalized_date = normalize_listing_date(raw_date)
        start_at = parse_event_date_and_time(normalized_date, time_value)

        key = (summary, start_at.isoformat())
        if key in seen_keys:
            continue

        seen_keys.add(key)
        events.append(
            {
                "source": "state-farm-arena",
                "summary": summary,
                "description": subtitle,
                "url": detail_url,
                "location": "State Farm Arena",
                "start_at": start_at,
                "end_at": None,
            }
        )

    return events


def fetch_events() -> list[EventRecord]:
    pending_listing_urls = list(STATE_FARM_ARENA_SEED_URLS)
    seen_listing_urls: set[str] = set()
    detail_urls: list[str] = []
    seen_detail_urls: set[str] = set()
    fetched_listing = False

    while pending_listing_urls:
        listing_url = pending_listing_urls.pop(0)
        if listing_url in seen_listing_urls:
            continue

        seen_listing_urls.add(listing_url)
        try:
            listing_html = fetch_html(listing_url)
        except Exception:
            continue

        fetched_listing = True

        for next_listing_url in extract_state_farm_arena_listing_urls(listing_html):
            if next_listing_url not in seen_listing_urls and next_listing_url not in pending_listing_urls:
                pending_listing_urls.append(next_listing_url)

        for detail_url in extract_state_farm_arena_detail_urls(listing_html):
            if detail_url in seen_detail_urls:
                continue

            seen_detail_urls.add(detail_url)
            detail_urls.append(detail_url)

    print(
        f"[info] state_farm_arena discovered {len(seen_listing_urls)} listing pages and {len(detail_urls)} detail urls",
        file=sys.stderr,
    )

    if not fetched_listing:
        raise RuntimeError("unable to fetch any State Farm Arena listing pages")

    if not detail_urls:
        listing_events: list[EventRecord] = []
        for listing_url in seen_listing_urls:
            try:
                listing_html = fetch_html(listing_url)
            except Exception:
                continue
            listing_events.extend(extract_state_farm_arena_listing_events(listing_html, listing_url))
        print(
            f"[info] state_farm_arena listing fallback produced {len(listing_events)} events",
            file=sys.stderr,
        )
        return listing_events

    events: list[EventRecord] = []
    seen_event_keys: set[tuple[str, datetime]] = set()

    for detail_url in detail_urls:
        try:
            detail_html = fetch_html(detail_url)
        except Exception:
            continue

        payloads = extract_json_ld(detail_html)
        detail_events = normalize_state_farm_arena_events(payloads)

        for item in detail_events:
            if item["url"] == STATE_FARM_ARENA_LISTING_URL:
                item["url"] = detail_url

            event_key = (item["url"], item["start_at"])
            if event_key in seen_event_keys:
                continue

            seen_event_keys.add(event_key)
            events.append(item)

    if events:
        return events

    listing_events: list[EventRecord] = []
    for listing_url in seen_listing_urls:
        try:
            listing_html = fetch_html(listing_url)
        except Exception:
            continue
        listing_events.extend(extract_state_farm_arena_listing_events(listing_html, listing_url))

    print(
        f"[info] state_farm_arena detail pages produced 0 events, listing fallback produced {len(listing_events)} events",
        file=sys.stderr,
    )

    return listing_events
