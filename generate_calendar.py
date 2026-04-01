from datetime import datetime
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event


OUTPUT_PATH = "gulcher-events.ics"
EVENT_TIMEZONE = ZoneInfo("America/New_York")


def main() -> None:
    cal = Calendar()
    event = Event()
    event.add("summary", "Test Event")
    event.add("dtstart", datetime(2026, 4, 1, 20, 0, tzinfo=EVENT_TIMEZONE))
    event.add("dtend", datetime(2026, 4, 1, 21, 0, tzinfo=EVENT_TIMEZONE))
    cal.add_component(event)

    with open(OUTPUT_PATH, "wb") as f:
        f.write(cal.to_ical())


if __name__ == "__main__":
    main()
