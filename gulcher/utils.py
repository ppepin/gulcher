import hashlib
import json
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


DEFAULT_TIMEZONE = ZoneInfo("America/New_York")
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
DATE_PATTERN = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}"
)
TIME_PATTERN = re.compile(r"\b\d{1,2}:\d{2}\s*[APap][Mm]\b|\bTBA\b")


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
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


def parse_event_date_and_time(raw_date: str, raw_time: str | None) -> datetime:
    cleaned_time = (raw_time or "").strip()
    if not cleaned_time or cleaned_time.upper() == "TBA":
        cleaned_time = "12:00 AM"

    parsed = datetime.strptime(f"{raw_date.strip()} {cleaned_time}", "%B %d, %Y %I:%M %p")
    return parsed.replace(tzinfo=DEFAULT_TIMEZONE)


def build_uid(source_name: str, event_url: str, start_at: datetime) -> str:
    digest = hashlib.sha256(f"{source_name}|{event_url}|{start_at.isoformat()}".encode()).hexdigest()
    return f"{digest[:24]}@gulcher.local"
