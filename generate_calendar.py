import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event


OUTPUT_PATH = "gulcher-events.ics"
DEFAULT_TIMEZONE = ZoneInfo("America/New_York")
STATE_FARM_ARENA_EVENTS_URL = "https://www.statefarmarena.com/events/index/36"


def fetch_html(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def extract_json_ld(html: str) -> list[Any]:
    soup = BeautifulSoup(html, "html.parser")
    payloads: list[Any] = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw_json = script.string or script.get_text()
        if not raw_json or not raw_json.strip():
            continue

        try:
            payloads.append(json.loads(raw_json))
        except json.JSONDecodeError:
            continue

    return payloads


def iter_event_nodes(node: Any) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    if isinstance(node, list):
        for item in node:
            events.extend(iter_event_nodes(item))
        return events

    if not isinstance(node, dict):
        return events

    node_type = node.get("@type")
    if node_type == "Event" or (isinstance(node_type, list) and "Event" in node_type):
        events.append(node)

    for key in ("@graph", "itemListElement", "mainEntity", "subjectOf"):
        value = node.get(key)
        if value is not None:
            events.extend(iter_event_nodes(value))

    return events


def parse_event_datetime(raw_value: str) -> datetime:
    normalized = raw_value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=DEFAULT_TIMEZONE)
    return parsed


def build_uid(source_name: str, event_url: str, start_at: datetime) -> str:
    digest = hashlib.sha256(f"{source_name}|{event_url}|{start_at.isoformat()}".encode()).hexdigest()
    return f"{digest[:24]}@gulcher.local"


def normalize_state_farm_arena_events(payloads: list[Any]) -> list[dict[str, Any]]:
    normalized_events: list[dict[str, Any]] = []

    for payload in payloads:
        for raw_event in iter_event_nodes(payload):
            start_date = raw_event.get("startDate")
            if not start_date:
                continue

            start_at = parse_event_datetime(start_date)
            end_date = raw_event.get("endDate")
            end_at = parse_event_datetime(end_date) if end_date else None
            event_url = raw_event.get("url") or STATE_FARM_ARENA_EVENTS_URL

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


def build_calendar(events: list[dict[str, Any]]) -> Calendar:
    calendar = Calendar()
    calendar.add("prodid", "-//gulcher//events//EN")
    calendar.add("version", "2.0")
    generated_at = datetime.now(UTC)

    for item in sorted(events, key=lambda event: event["start_at"]):
        event = Event()
        event.add("summary", item["summary"])
        event.add("dtstart", item["start_at"].astimezone(UTC))
        if item["end_at"] is not None:
            event.add("dtend", item["end_at"].astimezone(UTC))
        event.add("dtstamp", generated_at)
        event.add("uid", build_uid(item["source"], item["url"], item["start_at"]))

        if item["description"]:
            event.add("description", item["description"])
        if item["location"]:
            event.add("location", item["location"])
        if item["url"]:
            event.add("url", item["url"])

        calendar.add_component(event)

    return calendar


def main() -> None:
    html = fetch_html(STATE_FARM_ARENA_EVENTS_URL)
    payloads = extract_json_ld(html)
    events = normalize_state_farm_arena_events(payloads)
    calendar = build_calendar(events)

    with open(OUTPUT_PATH, "wb") as f:
        f.write(calendar.to_ical())


if __name__ == "__main__":
    main()
