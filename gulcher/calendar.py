from datetime import UTC, datetime

from icalendar import Calendar, Event

from gulcher.models import EventRecord
from gulcher.utils import DEFAULT_TIMEZONE, build_uid


def dedupe_events(events: list[EventRecord]) -> list[EventRecord]:
    deduped_events: list[EventRecord] = []
    seen_keys: set[tuple[str, str, str | None]] = set()

    for event in events:
        key = (
            event["summary"].strip().lower(),
            event["start_at"].astimezone(DEFAULT_TIMEZONE).isoformat(),
            event["location"].strip().lower() if event["location"] else None,
        )
        if key in seen_keys:
            continue

        seen_keys.add(key)
        deduped_events.append(event)

    return deduped_events


def build_calendar(events: list[EventRecord]) -> Calendar:
    calendar = Calendar()
    calendar.add("prodid", "-//gulcher//events//EN")
    calendar.add("version", "2.0")
    generated_at = datetime.now(UTC)
    local_today = generated_at.astimezone(DEFAULT_TIMEZONE).date()
    upcoming_events = [
        event for event in events if event["start_at"].astimezone(DEFAULT_TIMEZONE).date() >= local_today
    ]

    for item in sorted(upcoming_events, key=lambda event: event["start_at"]):
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
