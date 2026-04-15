from datetime import date, datetime, timedelta
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from gulcher.models import EventRecord
from gulcher.calendar import normalize_summary
from gulcher.utils import (
    DATE_PATTERN,
    DEFAULT_TIMEZONE,
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
    r"\s+\d{1,2},?\s*(?:-\s*(?:"
    r"(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"\s+)?\d{1,2},?\s*)?\d{4}"
)
START_TIME_PATTERN = re.compile(r"Event Starts\s+(\d{1,2}:\d{2}\s*[AP]M)")
GENERIC_SUMMARIES = {
    "events and tickets",
    "upcoming events presented by",
    "featured events",
    "event details",
}
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
DAY_NAME_PREFIXES = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
STATE_FARM_ARENA_DESCRIPTION_REPLACEMENTS = (
    ("General Public Make it a Night", "General Public. Make it a Night."),
    ("Make it a Night Upgrade", "Make it a Night. Upgrade"),
    ("Tickets Tap Buy Tickets", "Tickets. Tap Buy Tickets"),
    ("Premium & Groups Make it", "Premium & Groups. Make it"),
    ("Plan Your Visit Reserve", "Plan Your Visit. Reserve"),
)
STATE_FARM_ARENA_DESCRIPTION_SECTION_HEADINGS = {
    "Make it a Night",
    "Tickets",
    "Premium & Groups",
    "Plan Your Visit",
}
STATE_FARM_ARENA_DETAIL_STOP_HEADINGS = {
    "Suite Rentals",
    "Stay & Play presented by Hotels.com",
    "Parking: Buy Now & Save!",
    "Plan Your Visit",
    "Bag Policy",
    "Cashless Enviroment",
    "Cashless Environment",
    "Omni Hotel Guests",
    "Back To Top",
}


def normalize_state_farm_arena_description(description: str | None) -> str | None:
    if not description:
        return description

    cleaned = re.sub(r"\s+", " ", description).strip()
    cleaned = re.sub(r"([.!?])([A-Z])", r"\1 \2", cleaned)
    cleaned = re.sub(r"([a-z])([A-Z])", r"\1 \2", cleaned)
    cleaned = re.sub(r"([A-Za-z])(\d)", r"\1 \2", cleaned)
    cleaned = re.sub(r"(\d)([A-Za-z])", r"\1 \2", cleaned)
    cleaned = re.sub(r"([.)])([A-Z])", r"\1 \2", cleaned)
    for source, replacement in STATE_FARM_ARENA_DESCRIPTION_REPLACEMENTS:
        cleaned = cleaned.replace(source, replacement)
    cleaned = re.sub(r"\.\s+\.", ".", cleaned)
    return cleaned


def extract_state_farm_arena_detail_description(detail_html: str) -> str | None:
    soup = BeautifulSoup(detail_html, "html.parser")
    description_wrapper = soup.select_one("div.description_wrapper")
    if description_wrapper is not None:
        fragments: list[str] = []
        seen_fragments: set[str] = set()

        for tag in description_wrapper.find_all(["h4", "p"]):
            text = tag.get_text(" ", strip=True)
            if not text or text in seen_fragments:
                continue
            if text in STATE_FARM_ARENA_DESCRIPTION_SECTION_HEADINGS:
                break
            seen_fragments.add(text)
            fragments.append(text)

        if fragments:
            return normalize_state_farm_arena_description(" ".join(fragments))

    event_details_heading = soup.find(
        lambda tag: getattr(tag, "name", None) in {"h2", "h3"} and tag.get_text(" ", strip=True) == "Event Details"
    )
    if event_details_heading is None:
        return None

    fragments: list[str] = []
    seen_fragments: set[str] = set()

    for tag in event_details_heading.find_all_next():
        if tag == event_details_heading:
            continue

        tag_name = getattr(tag, "name", None)
        if tag_name in {"h2", "h3"}:
            tag_text = tag.get_text(" ", strip=True)
            if tag_text in STATE_FARM_ARENA_DETAIL_STOP_HEADINGS:
                break

        if tag_name not in {"h4", "p"}:
            continue

        text = tag.get_text(" ", strip=True)
        if not text or text in seen_fragments:
            continue

        seen_fragments.add(text)
        fragments.append(text)

    if not fragments:
        return None

    return normalize_state_farm_arena_description(" ".join(fragments))


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
                    "description": normalize_state_farm_arena_description(raw_event.get("description")),
                    "url": event_url,
                    "location": location_name,
                    "start_at": start_at,
                    "end_at": end_at,
                }
            )

    return normalized_events


def enrich_detail_event_descriptions(detail_events: list[EventRecord], detail_description: str | None) -> list[EventRecord]:
    if not detail_description:
        return detail_events

    enriched_events: list[EventRecord] = []
    for item in detail_events:
        enriched = dict(item)
        existing_description = enriched.get("description") or ""
        if len(detail_description) > len(existing_description):
            enriched["description"] = detail_description
        enriched_events.append(enriched)
    return enriched_events


def normalize_month_name(value: str) -> str:
    return MONTH_NAME_MAP.get(value, value)


def parse_listing_date_token(raw_value: str, default_month: str | None, year: int) -> date:
    parts = raw_value.strip().replace(",", "").split()
    if parts and parts[0] in DAY_NAME_PREFIXES:
        parts = parts[1:]
    if not parts:
        raise ValueError(f"unsupported date token: {raw_value}")

    if len(parts) == 1:
        if default_month is None:
            raise ValueError(f"missing month in date token: {raw_value}")
        month_name = default_month
        day_value = parts[0]
    else:
        month_name = normalize_month_name(parts[0])
        day_value = parts[1]

    parsed = datetime.strptime(f"{month_name} {day_value} {year}", "%B %d %Y")
    return parsed.date()


def expand_listing_dates(raw_date: str) -> list[date]:
    cleaned = raw_date.strip().replace(" ,", ",")
    year_match = re.search(r"(20\d{2})$", cleaned)
    if year_match is None:
        raise ValueError(f"unsupported date format: {raw_date}")

    year = int(year_match.group(1))
    without_year = cleaned[: year_match.start()].strip().rstrip(",")
    if "-" not in without_year:
        return [parse_listing_date_token(without_year, None, year)]

    start_raw, end_raw = [part.strip() for part in without_year.split("-", 1)]
    start_parts = start_raw.replace(",", "").split()
    if start_parts and start_parts[0] in DAY_NAME_PREFIXES:
        start_parts = start_parts[1:]
    if not start_parts:
        raise ValueError(f"unsupported date range: {raw_date}")

    start_month = normalize_month_name(start_parts[0])
    start_date = parse_listing_date_token(start_raw, None, year)
    end_date = parse_listing_date_token(end_raw, start_month, year)
    if end_date < start_date:
        raise ValueError(f"descending date range: {raw_date}")

    expanded_dates: list[date] = []
    current = start_date
    while current <= end_date:
        expanded_dates.append(current)
        current += timedelta(days=1)

    return expanded_dates


def build_listing_start_at(event_date: date, time_value: str | None) -> datetime:
    raw_date = f"{event_date.strftime('%B')} {event_date.day}, {event_date.year}"
    return parse_event_date_and_time(raw_date, time_value)


def has_placeholder_midnight(event: EventRecord) -> bool:
    local_start = event["start_at"].astimezone(DEFAULT_TIMEZONE)
    return (local_start.hour, local_start.minute, local_start.second) == (0, 0, 0)


def apply_detail_time(base_event: EventRecord, detail_event: EventRecord) -> EventRecord:
    if not has_placeholder_midnight(base_event):
        return base_event

    detail_local_start = detail_event["start_at"].astimezone(DEFAULT_TIMEZONE)
    if (detail_local_start.hour, detail_local_start.minute, detail_local_start.second) == (0, 0, 0):
        return base_event

    base_local_start = base_event["start_at"].astimezone(DEFAULT_TIMEZONE)
    enriched = dict(base_event)
    enriched["start_at"] = base_local_start.replace(
        hour=detail_local_start.hour,
        minute=detail_local_start.minute,
        second=detail_local_start.second,
        microsecond=detail_local_start.microsecond,
    )
    return enriched


def extract_listing_time(block_text: str, summary: str, subtitle: str | None) -> str | None:
    time_match = START_TIME_PATTERN.search(block_text)
    if time_match is not None:
        return time_match.group(1)

    filtered_lines = []
    for line in block_text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned == summary or cleaned == (subtitle or ""):
            continue
        filtered_lines.append(cleaned)

    for line in filtered_lines:
        if line in {"More Info", "Buy Tickets", "Featured Events"}:
            continue
        if DATE_PATTERN.search(line):
            continue
        time_match = re.search(r"\b(\d{1,2}:\d{2}\s*[AP]M)\b", line)
        if time_match is not None:
            return time_match.group(1)

    return None


def extract_listing_time_from_heading(heading: object, summary: str, subtitle: str | None) -> str | None:
    if not getattr(heading, "next_elements", None):
        return None

    scanned = 0
    for element in heading.next_elements:
        if getattr(element, "name", None) in {"h2", "h3"}:
            next_summary = element.get_text(" ", strip=True)
            if next_summary and next_summary != summary:
                break

        text = None
        if isinstance(element, str):
            text = element.strip()
        elif getattr(element, "get_text", None):
            text = element.get_text(" ", strip=True)

        if not text:
            continue
        if text == summary or text == (subtitle or ""):
            continue

        scanned += 1
        if scanned > 30:
            break

        time_match = START_TIME_PATTERN.search(text)
        if time_match is not None:
            return time_match.group(1)

        if text in {"Buy Tickets", "Parking", "More Info"}:
            continue
        if DATE_PATTERN.search(text):
            continue

        generic_time_match = re.search(r"\b(\d{1,2}:\d{2}\s*[AP]M)\b", text)
        if generic_time_match is not None:
            return generic_time_match.group(1)

    return None


def enrich_listing_event(base_event: EventRecord, detail_event: EventRecord) -> EventRecord:
    enriched = apply_detail_time(base_event, detail_event)
    if detail_event.get("description"):
        enriched["description"] = detail_event["description"]
    same_local_day = (
        detail_event["end_at"] is not None
        and detail_event["end_at"].astimezone(DEFAULT_TIMEZONE).date()
        == base_event["start_at"].astimezone(DEFAULT_TIMEZONE).date()
    )
    if same_local_day:
        enriched["end_at"] = detail_event["end_at"]
    if detail_event.get("url") and "/events/detail/" in detail_event["url"]:
        enriched["url"] = detail_event["url"]
    return enriched


def merge_state_farm_records(detail_events: list[EventRecord], listing_events: list[EventRecord]) -> list[EventRecord]:
    merged_events: list[EventRecord] = []
    listing_index: dict[tuple[str, str, str | None], int] = {}
    detail_series_index: dict[tuple[str, str | None], EventRecord] = {}

    for item in listing_events:
        key = (
            normalize_summary(item["summary"]),
            item["start_at"].astimezone(DEFAULT_TIMEZONE).date().isoformat(),
            item["location"].strip().lower() if item["location"] else None,
        )
        listing_index[key] = len(merged_events)
        merged_events.append(item)

    for item in detail_events:
        summary_location_key = (
            normalize_summary(item["summary"]),
            item["location"].strip().lower() if item["location"] else None,
        )
        existing_series = detail_series_index.get(summary_location_key)
        if existing_series is None or existing_series["start_at"] > item["start_at"]:
            detail_series_index[summary_location_key] = item

        key = (
            normalize_summary(item["summary"]),
            item["start_at"].astimezone(DEFAULT_TIMEZONE).date().isoformat(),
            item["location"].strip().lower() if item["location"] else None,
        )
        existing_index = listing_index.get(key)
        if existing_index is not None:
            merged_events[existing_index] = enrich_listing_event(merged_events[existing_index], item)
            continue

        local_event_date = item["start_at"].astimezone(DEFAULT_TIMEZONE).date()
        today = datetime.now(DEFAULT_TIMEZONE).date()
        if today <= local_event_date <= today + timedelta(days=30):
            listing_index[key] = len(merged_events)
            merged_events.append(item)

    for index, item in enumerate(merged_events):
        summary_location_key = (
            normalize_summary(item["summary"]),
            item["location"].strip().lower() if item["location"] else None,
        )
        detail_event = detail_series_index.get(summary_location_key)
        if detail_event is None:
            continue
        merged_events[index] = apply_detail_time(item, detail_event)

    return merged_events


def extract_state_farm_arena_listing_events(listing_html: str, listing_url: str) -> list[EventRecord]:
    soup = BeautifulSoup(listing_html, "html.parser")
    events: list[EventRecord] = []
    seen_keys: set[tuple[str, str, str]] = set()

    for heading in soup.find_all(["h2", "h3"]):
        summary = heading.get_text(" ", strip=True)
        if not summary or normalize_summary(summary) in GENERIC_SUMMARIES:
            continue

        block = heading.parent
        if block is None:
            continue

        block_text = block.get_text("\n", strip=True)
        date_match = LISTING_DATE_PATTERN.search(block_text)
        if date_match is None:
            continue

        raw_date = date_match.group(0)

        subtitle = None
        subtitle_node = heading.find_next_sibling(["h4", "h5"])
        if subtitle_node is not None:
            subtitle = subtitle_node.get_text(" ", strip=True) or None
        time_value = extract_listing_time(block_text, summary, subtitle)
        if time_value is None:
            time_value = extract_listing_time_from_heading(heading, summary, subtitle)

        detail_url = listing_url
        for link in block.find_all("a", href=True):
            href = link["href"].strip()
            link_text = link.get_text(" ", strip=True)
            if "/events/detail/" in href or "More Info" in link_text:
                detail_url = urljoin(STATE_FARM_ARENA_LISTING_URL, href)
                break

        try:
            event_dates = expand_listing_dates(raw_date)
        except ValueError:
            continue

        for event_date in event_dates:
            start_at = build_listing_start_at(event_date, time_value)
            key = (normalize_summary(summary), event_date.isoformat(), "state farm arena")
            if key in seen_keys:
                continue

            seen_keys.add(key)
            events.append(
                {
                    "source": "state-farm-arena",
                    "summary": summary,
                    "description": normalize_state_farm_arena_description(subtitle),
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

    if not fetched_listing:
        raise RuntimeError("unable to fetch any State Farm Arena listing pages")

    listing_events: list[EventRecord] = []
    for listing_url in seen_listing_urls:
        try:
            listing_html = fetch_html(listing_url)
        except Exception:
            continue
        listing_events.extend(extract_state_farm_arena_listing_events(listing_html, listing_url))

    events: list[EventRecord] = []
    seen_event_keys: set[tuple[str, datetime]] = set()

    for detail_url in detail_urls:
        try:
            detail_html = fetch_html(detail_url)
        except Exception:
            continue

        payloads = extract_json_ld(detail_html)
        detail_events = normalize_state_farm_arena_events(payloads)
        detail_description = extract_state_farm_arena_detail_description(detail_html)
        detail_events = enrich_detail_event_descriptions(detail_events, detail_description)

        for item in detail_events:
            if item["url"] == STATE_FARM_ARENA_LISTING_URL:
                item["url"] = detail_url

            event_key = (item["url"], item["start_at"])
            if event_key in seen_event_keys:
                continue

            seen_event_keys.add(event_key)
            events.append(item)

    merged_events = merge_state_farm_records(events, listing_events)

    return merged_events
