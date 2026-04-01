from datetime import datetime
from typing import TypedDict


class EventRecord(TypedDict):
    source: str
    summary: str
    description: str | None
    url: str
    location: str | None
    start_at: datetime
    end_at: datetime | None
