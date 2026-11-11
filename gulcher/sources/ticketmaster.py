import os
import re
from datetime import datetime, time, timedelta

import requests

from gulcher.calendar import normalize_summary
from gulcher.models import EventRecord
from gulcher.utils import DEFAULT_TIMEZONE, parse_event_datetime


API_URL = "https://app.ticketmaster.com/discovery/v2/events.json"
VENUES = {
    "KovZpZAEdJaA": "Mercedes-Benz Stadium",
    "KovZpa2Xke": "State Farm Arena",
}


def normalize_event(item: dict, venue_id: str) -> EventRecord | None:
    dates = item.get("dates", {})
    start = dates.get("start", {})
    if dates.get("status", {}).get("code") in {"cancelled", "postponed"}:
        return None
    if start.get("dateTBA") or start.get("dateTBD"):
        return None
    if any(c.get("type", {}).get("name", "").lower() == "upsell"
           or c.get("segment", {}).get("name", "").lower() == "miscellaneous"
           for c in item.get("classifications", [])):
        return None
    if venue_id not in {v.get("id") for v in item.get("_embedded", {}).get("venues", [])}:
        return None
    summary = item.get("name", "").strip()
    url = item.get("url", "").strip()
    if not summary or not url:
        return None
    try:
        if start.get("dateTime") and not (start.get("timeTBA") or start.get("noSpecificTime")):
            start_at = parse_event_datetime(start["dateTime"]).astimezone(DEFAULT_TIMEZONE)
        else:
            local_time = start.get("localTime", "00:00:00")
            if start.get("timeTBA") or start.get("noSpecificTime"):
                local_time = "00:00:00"
            start_at = datetime.fromisoformat(f"{start['localDate']}T{local_time}").replace(tzinfo=DEFAULT_TIMEZONE)
    except (KeyError, ValueError):
        return None
    return {
        "source": "ticketmaster", "summary": summary, "description": None,
        "url": url, "location": VENUES[venue_id], "start_at": start_at, "end_at": None,
    }


def fetch_events() -> list[EventRecord]:
    api_key = os.environ.get("TICKETMASTER_API_KEY", "").strip()
    if not api_key:
        return []
    today = datetime.now(DEFAULT_TIMEZONE).date()
    start_at = datetime.combine(today, time.min, DEFAULT_TIMEZONE)
    end_at = start_at + timedelta(days=31)
    events = []
    for venue_id in VENUES:
        page = 0
        while True:
            try:
                response = requests.get(API_URL, params={
                    "apikey": api_key, "venueId": venue_id, "source": "ticketmaster",
                    "localStartDateTime": f"{start_at:%Y-%m-%dT%H:%M:%S},{end_at:%Y-%m-%dT%H:%M:%S}",
                    "size": 200, "page": page, "sort": "date,asc",
                }, timeout=30)
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError):
                # Requests exceptions contain the URL, including the API key.
                raise RuntimeError("Ticketmaster event request failed") from None
            for item in payload.get("_embedded", {}).get("events", []):
                event = normalize_event(item, venue_id)
                if event is not None:
                    events.append(event)
            page += 1
            if page >= payload.get("page", {}).get("totalPages", 1):
                break
            if page * 200 >= 1000:
                raise RuntimeError("Ticketmaster results exceed the API paging limit")
    return events


def title_words(summary: str) -> set[str]:
    normalized = normalize_summary(summary)
    normalized = re.sub(r"\b(?:20\d{2}|v|vs|game)\b", " ", normalized)
    return set(normalized.split())


def merge_events(events: list[EventRecord], supplements: list[EventRecord]) -> list[EventRecord]:
    merged = list(events)
    for supplement in supplements:
        match = None
        for index, existing in enumerate(merged):
            if existing["location"] != supplement["location"]:
                continue
            old_start = existing["start_at"].astimezone(DEFAULT_TIMEZONE)
            new_start = supplement["start_at"].astimezone(DEFAULT_TIMEZONE)
            if old_start.date() != new_start.date():
                continue
            old_words, new_words = title_words(existing["summary"]), title_words(supplement["summary"])
            if not old_words or not new_words or not (old_words <= new_words or new_words <= old_words):
                continue
            if old_start.time() != new_start.time() and old_start.time() != time.min and new_start.time() != time.min:
                continue
            match = index
            break
        if match is None:
            merged.append(supplement)
        elif merged[match]["start_at"].astimezone(DEFAULT_TIMEZONE).time() == time.min:
            # Keep the venue's title, description and URL, but fill missing time.
            merged[match] = {**merged[match], "start_at": supplement["start_at"]}
    return merged
