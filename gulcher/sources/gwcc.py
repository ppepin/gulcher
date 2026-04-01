import json
from datetime import timedelta
from typing import Any

from gulcher.models import EventRecord
from gulcher.utils import extract_json_ld, fetch_html, iter_event_nodes, parse_event_datetime


GWCC_CALENDAR_URL = "https://www.gwcca.org/event-calendar"
GWCC_LOCATION_KEYWORDS = ("georgia world congress center", "gwcc")
LARGE_EVENT_KEYWORDS = (
    "expo",
    "conference",
    "convention",
    "summit",
    "show",
    "market",
    "championship",
    "tournament",
    "festival",
    "fan fest",
    "trade show",
)


def extract_embedded_json_candidates(html: str) -> list[Any]:
    decoder = json.JSONDecoder()
    candidates: list[Any] = []

    for marker in ('{"title"', '[{"title"', '{"start"', '[{"start"'):
        start_index = 0
        while True:
            index = html.find(marker, start_index)
            if index == -1:
                break

            try:
                payload, offset = decoder.raw_decode(html[index:])
            except json.JSONDecodeError:
                start_index = index + 1
                continue

            candidates.append(payload)
            start_index = index + max(offset, 1)

    return candidates


def iter_gwcc_event_nodes(node: Any) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    if isinstance(node, list):
        for item in node:
            events.extend(iter_gwcc_event_nodes(item))
        return events

    if not isinstance(node, dict):
        return events

    has_gwcc_shape = (
        ("title" in node or "name" in node)
        and ("start" in node or "startDate" in node)
        and any(key in node for key in ("eventLocation", "location", "venue"))
    )
    if has_gwcc_shape:
        events.append(node)

    for value in node.values():
        if isinstance(value, (list, dict)):
            events.extend(iter_gwcc_event_nodes(value))

    return events


def extract_location_name(raw_event: dict[str, Any]) -> str | None:
    location = raw_event.get("eventLocation") or raw_event.get("location") or raw_event.get("venue")
    if isinstance(location, dict):
        return (
            location.get("name")
            or location.get("title")
            or location.get("location")
            or location.get("venue")
        )
    if isinstance(location, str):
        return location
    return None


def extract_event_url(raw_event: dict[str, Any]) -> str:
    return (
        raw_event.get("url")
        or raw_event.get("path")
        or raw_event.get("href")
        or raw_event.get("detailsUrl")
        or GWCC_CALENDAR_URL
    )


def is_large_gwcc_event(event: EventRecord) -> bool:
    title_blob = " ".join(filter(None, [event["summary"], event["description"]])).lower()
    end_at = event["end_at"] or event["start_at"]
    duration = end_at - event["start_at"]
    is_multiday = duration >= timedelta(days=1)
    has_large_keyword = any(keyword in title_blob for keyword in LARGE_EVENT_KEYWORDS)
    return is_multiday or has_large_keyword


def normalize_gwcc_events(payloads: list[Any]) -> list[EventRecord]:
    events: list[EventRecord] = []

    for payload in payloads:
        for raw_event in iter_gwcc_event_nodes(payload):
            start_value = raw_event.get("start") or raw_event.get("startDate")
            if not isinstance(start_value, str) or not start_value.strip():
                continue

            location_name = extract_location_name(raw_event)
            if not location_name or not any(keyword in location_name.lower() for keyword in GWCC_LOCATION_KEYWORDS):
                continue

            end_value = raw_event.get("end") or raw_event.get("endDate")
            end_at = parse_event_datetime(end_value) if isinstance(end_value, str) and end_value.strip() else None
            event: EventRecord = {
                "source": "gwcc",
                "summary": raw_event.get("title") or raw_event.get("name") or "GWCC Event",
                "description": raw_event.get("description") or raw_event.get("body"),
                "url": extract_event_url(raw_event),
                "location": location_name,
                "start_at": parse_event_datetime(start_value),
                "end_at": end_at,
            }

            if is_large_gwcc_event(event):
                events.append(event)

    return events


def fetch_events() -> list[EventRecord]:
    html = fetch_html(GWCC_CALENDAR_URL)
    payloads: list[Any] = []
    payloads.extend(extract_json_ld(html))
    payloads.extend(extract_embedded_json_candidates(html))

    events = normalize_gwcc_events(payloads)
    deduped_events: list[EventRecord] = []
    seen_keys: set[tuple[str, str]] = set()

    for event in events:
        event_key = (event["url"], event["start_at"].isoformat())
        if event_key in seen_keys:
            continue

        seen_keys.add(event_key)
        deduped_events.append(event)

    return deduped_events
