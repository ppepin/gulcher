from collections import defaultdict
from datetime import UTC, datetime
from html import escape
import re

from gulcher.calendar import CALENDAR_DESCRIPTION, CALENDAR_NAME, get_upcoming_events
from gulcher.models import EventRecord
from gulcher.utils import DEFAULT_TIMEZONE

SOURCE_LABELS = {
    "atlanta-falcons": "Atlanta Falcons",
    "atlanta-united": "Atlanta United",
    "gwcc": "GWCC",
    "mercedes-benz-stadium": "Mercedes-Benz Stadium",
    "state-farm-arena": "State Farm Arena",
}
STATE_FARM_ARENA_DESCRIPTION_HEADERS = (
    "Make it a Night.",
    "Tickets.",
    "Premium & Groups.",
    "Plan Your Visit.",
)

THEMES = {
    "color": {
        "body": "background: linear-gradient(180deg, #fff8ef 0%, #f3f7ff 100%); color: #172033;",
        "panel": "background: rgba(255, 255, 255, 0.88); border: 1px solid rgba(23, 32, 51, 0.08); box-shadow: 0 18px 50px rgba(23, 32, 51, 0.08);",
        "muted": "#5a6478",
        "accent": "#0c7c59",
        "accent_soft": "#dff4ec",
        "rule": "rgba(23, 32, 51, 0.12)",
        "link": "#155eef",
        "badge_text": "#172033",
        "source_styles": """
            .event[data-source="state-farm-arena"] .source { background: #fde68a; }
            .event[data-source="mercedes-benz-stadium"] .source { background: #bfdbfe; }
            .event[data-source="atlanta-united"] .source { background: #fecaca; }
            .event[data-source="atlanta-falcons"] .source { background: #d8b4fe; }
            .event[data-source="gwcc"] .source { background: #bbf7d0; }
        """,
    },
    "eink": {
        "body": "background: #f6f6f6; color: #111111;",
        "panel": "background: #ffffff; border: 2px solid #111111; box-shadow: none;",
        "muted": "#333333",
        "accent": "#111111",
        "accent_soft": "#e9e9e9",
        "rule": "#222222",
        "link": "#111111",
        "badge_text": "#111111",
        "source_styles": """
            .event .source { background: #e9e9e9; border: 1px solid #111111; }
        """,
    },
}


def format_source_label(source_name: str) -> str:
    return SOURCE_LABELS.get(source_name, source_name.replace("-", " ").title())


def format_badge_label(event: EventRecord) -> str:
    location = (event["location"] or "").strip()
    if location:
        return location
    return format_source_label(event["source"])


def format_event_time(event: EventRecord) -> str:
    start_at = event["start_at"].astimezone(DEFAULT_TIMEZONE)
    end_at = event["end_at"].astimezone(DEFAULT_TIMEZONE) if event["end_at"] else None
    start_label = start_at.strftime("%-I:%M %p").lower()
    if end_at is None:
        return start_label
    return f"{start_label} - {end_at.strftime('%-I:%M %p').lower()}"


def format_event_description(event: EventRecord) -> str:
    description = event["description"]
    if not description:
        return ""

    if event["source"] != "state-farm-arena":
        return escape(description)

    pattern = re.compile(
        r"(^|(?<=\.\s))("
        + "|".join(re.escape(header) for header in STATE_FARM_ARENA_DESCRIPTION_HEADERS)
        + r")"
    )
    parts: list[str] = []
    last_index = 0

    for match in pattern.finditer(description):
        parts.append(escape(description[last_index:match.start()]))
        prefix, header = match.groups()
        parts.append(escape(prefix))
        parts.append(f"<em>{escape(header)}</em>")
        last_index = match.end()

    parts.append(escape(description[last_index:]))
    return "".join(parts)


def render_event(event: EventRecord) -> str:
    summary = escape(event["summary"])
    source = escape(format_badge_label(event))
    source_key = escape(event["source"])
    time_label = escape(format_event_time(event))
    description = format_event_description(event)
    url = event["url"].strip()
    url_markup = (
        f'<a class="event-link" href="{escape(url, quote=True)}">Event page</a>'
        if url
        else ""
    )
    description_markup = f'<p class="description">{description}</p>' if description else ""

    return f"""
        <article class="event" data-source="{source_key}">
          <div class="event-header">
            <p class="time">{time_label}</p>
            <span class="source">{source}</span>
          </div>
          <h3>{summary}</h3>
          {description_markup}
          {url_markup}
        </article>
    """.strip()


def render_schedule_page(events: list[EventRecord], *, theme: str) -> str:
    if theme not in THEMES:
        raise ValueError(f"unknown theme: {theme}")

    generated_at = datetime.now(UTC).astimezone(DEFAULT_TIMEZONE)
    upcoming_events = sorted(get_upcoming_events(events), key=lambda event: event["start_at"])
    events_by_date: dict[str, list[EventRecord]] = defaultdict(list)
    for event in upcoming_events:
        date_key = event["start_at"].astimezone(DEFAULT_TIMEZONE).strftime("%A, %B %-d")
        events_by_date[date_key].append(event)

    theme_values = THEMES[theme]
    sections = []
    for date_label, grouped_events in events_by_date.items():
        cards = "\n".join(render_event(event) for event in grouped_events)
        sections.append(
            f"""
            <section class="day-group">
              <h2>{escape(date_label)}</h2>
              <div class="events">
                {cards}
              </div>
            </section>
            """.strip()
        )

    if not sections:
        sections.append(
            """
            <section class="day-group">
              <h2>No upcoming events</h2>
              <div class="events">
                <article class="event">
                  <p class="description">No events were found in the next 30 days.</p>
                </article>
              </div>
            </section>
            """.strip()
        )

    alternate_path = "schedule-eink.html" if theme == "color" else "schedule-color.html"
    alternate_label = "greyscale e-ink" if theme == "color" else "color"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(CALENDAR_NAME)} Schedule</title>
  <meta name="description" content="{escape(CALENDAR_DESCRIPTION)}">
  <style>
    :root {{
      color-scheme: light;
      --muted: {theme_values["muted"]};
      --accent: {theme_values["accent"]};
      --accent-soft: {theme_values["accent_soft"]};
      --rule: {theme_values["rule"]};
      --link: {theme_values["link"]};
      --badge-text: {theme_values["badge_text"]};
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
      {theme_values["body"]}
    }}
    a {{ color: var(--link); }}
    .shell {{
      max-width: 1040px;
      margin: 0 auto;
      padding: 32px 20px 64px;
    }}
    .hero {{
      padding: 28px;
      border-radius: 28px;
      {theme_values["panel"]}
    }}
    h1 {{
      margin: 0;
      font-size: clamp(2.2rem, 6vw, 4.75rem);
      line-height: 0.96;
    }}
    .intro {{
      max-width: 55rem;
      margin: 14px 0 0;
      color: var(--muted);
      font-size: 1.05rem;
    }}
    .hero-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px 20px;
      margin-top: 18px;
      color: var(--muted);
      font: 500 0.92rem/1.4 "Avenir Next", "Segoe UI", sans-serif;
    }}
    .hero-meta a {{
      text-decoration-thickness: 0.08em;
      text-underline-offset: 0.14em;
    }}
    .day-group {{
      margin-top: 28px;
    }}
    .day-group h2 {{
      margin: 0 0 14px;
      padding-bottom: 10px;
      border-bottom: 2px solid var(--rule);
      font: 600 1.4rem/1.2 "Avenir Next", "Segoe UI", sans-serif;
    }}
    .events {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
    }}
    .event {{
      display: flex;
      flex-direction: column;
      min-height: 100%;
      padding: 18px;
      border-radius: 20px;
      {theme_values["panel"]}
    }}
    .event-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 10px;
    }}
    .time {{
      margin: 0;
      font: 700 0.95rem/1.2 "Avenir Next", "Segoe UI", sans-serif;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .source {{
      flex-shrink: 0;
      padding: 6px 10px;
      border-radius: 999px;
      color: var(--badge-text);
      background: var(--accent-soft);
      font: 600 0.74rem/1 "Avenir Next", "Segoe UI", sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .event h3 {{
      margin: 14px 0 8px;
      font-size: 1.4rem;
      line-height: 1.05;
    }}
    .meta, .description {{
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 0.98rem;
      line-height: 1.45;
    }}
    .description em {{
      font-style: italic;
      color: var(--accent);
    }}
    .event-link {{
      margin-top: auto;
      font: 600 0.92rem/1.2 "Avenir Next", "Segoe UI", sans-serif;
      text-underline-offset: 0.14em;
    }}
    {theme_values["source_styles"]}
    @media (max-width: 640px) {{
      .shell {{ padding: 20px 14px 48px; }}
      .hero {{ padding: 20px; border-radius: 22px; }}
      .event {{ border-radius: 16px; }}
      .event-header {{ flex-direction: column; align-items: flex-start; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <h1>{escape(CALENDAR_NAME)}</h1>
      <p class="intro">{escape(CALENDAR_DESCRIPTION)}</p>
      <div class="hero-meta">
        <span>Updated {escape(generated_at.strftime('%B %-d, %Y at %-I:%M %p %Z'))}</span>
        <a href="webcal://example.com/calendar.ics">Subscribe to Calendar</a>
        <a href="{alternate_path}">Switch to {alternate_label} view</a>
      </div>
    </section>
    {"".join(sections)}
  </main>
</body>
</html>
"""
