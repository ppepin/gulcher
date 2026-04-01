from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from gulcher.models import EventRecord
from gulcher.utils import extract_json_ld, fetch_html, iter_event_nodes, parse_event_datetime


STATE_FARM_ARENA_LISTING_URL = "https://www.statefarmarena.com/events/index/4"
STATE_FARM_ARENA_SEED_URLS = [
    STATE_FARM_ARENA_LISTING_URL,
    "https://www.statefarmarena.com/",
    "https://www.statefarmarena.com/index.php",
    "https://www.statefarmarena.com/?lang=en",
]


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

    if not fetched_listing:
        raise RuntimeError("unable to fetch any State Farm Arena listing pages")

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

    return events
