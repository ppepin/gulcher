import re
from datetime import UTC, datetime, timedelta

from icalendar import Calendar, Event

from gulcher.models import EventRecord
from gulcher.utils import DEFAULT_TIMEZONE, build_uid

DEFAULT_EVENT_DURATION = timedelta(hours=3)


def normalize_summary(summary: str) -> str:
    normalized = summary.lower().strip()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def score_event(event: EventRecord) -> tuple[int, int, int]:
    return (
        1 if event["description"] else 0,
        1 if event["end_at"] else 0,
        1 if event["url"] else 0,
    )


def dedupe_events(events: list[EventRecord]) -> list[EventRecord]:
    deduped_events: dict[tuple[str, str, str | None], EventRecord] = {}

    for event in events:
        key = (
            normalize_summary(event["summary"]),
            event["start_at"].astimezone(DEFAULT_TIMEZONE).date().isoformat(),
            event["location"].strip().lower() if event["location"] else None,
        )
        existing = deduped_events.get(key)
        if existing is None or score_event(event) > score_event(existing):
            deduped_events[key] = event

    return list(deduped_events.values())


def build_calendar(events: list[EventRecord]) -> Calendar:
    calendar = Calendar()
    calendar.add("prodid", "-//gulcher//events//EN")
    calendar.add("version", "2.0")
    generated_at = datetime.now(UTC)
    local_today = generated_at.astimezone(DEFAULT_TIMEZONE).date()
    local_cutoff = local_today.fromordinal(local_today.toordinal() + 30)
    upcoming_events = [
        event
        for event in events
        if local_today <= event["start_at"].astimezone(DEFAULT_TIMEZONE).date() <= local_cutoff
    ]

    for item in sorted(upcoming_events, key=lambda event: event["start_at"]):
        event = Event()
        event.add("summary", item["summary"])
        start_at_local = item["start_at"].astimezone(DEFAULT_TIMEZONE)
        end_at = item["end_at"] or (item["start_at"] + DEFAULT_EVENT_DURATION)
        event.add("dtstart", start_at_local)
        event.add("dtend", end_at.astimezone(DEFAULT_TIMEZONE))
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
