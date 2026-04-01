from gulcher.calendar import build_calendar
from gulcher.sources.gwcc import fetch_events as fetch_gwcc_events
from gulcher.sources.mercedes_benz_stadium import fetch_events as fetch_mercedes_benz_stadium_events
from gulcher.sources.state_farm_arena import fetch_events as fetch_state_farm_arena_events


OUTPUT_PATH = "gulcher-events.ics"


def main() -> None:
    events = []
    events.extend(fetch_state_farm_arena_events())
    events.extend(fetch_mercedes_benz_stadium_events())
    events.extend(fetch_gwcc_events())
    calendar = build_calendar(events)

    with open(OUTPUT_PATH, "wb") as f:
        f.write(calendar.to_ical())


if __name__ == "__main__":
    main()
