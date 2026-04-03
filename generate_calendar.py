import sys

from gulcher.calendar import build_calendar, dedupe_events
from gulcher.sources.atlanta_united import fetch_events as fetch_atlanta_united_events
from gulcher.sources.falcons import fetch_events as fetch_falcons_events
from gulcher.sources.mercedes_benz_stadium import fetch_events as fetch_mercedes_benz_stadium_events
from gulcher.sources.state_farm_arena import fetch_events as fetch_state_farm_arena_events


OUTPUT_PATH = "gulcher-events.ics"


def extend_events(events: list, source_name: str, fetcher) -> None:
    try:
        fetched_events = fetcher()
        events.extend(fetched_events)
    except Exception as exc:
        print(f"[warn] failed to fetch {source_name}: {exc}", file=sys.stderr)


def main() -> None:
    events = []
    extend_events(events, "state_farm_arena", fetch_state_farm_arena_events)
    extend_events(events, "mercedes_benz_stadium", fetch_mercedes_benz_stadium_events)
    extend_events(events, "atlanta_united", fetch_atlanta_united_events)
    extend_events(events, "atlanta_falcons", fetch_falcons_events)
    deduped_events = dedupe_events(events)
    calendar = build_calendar(deduped_events)

    with open(OUTPUT_PATH, "wb") as f:
        f.write(calendar.to_ical())


if __name__ == "__main__":
    main()
