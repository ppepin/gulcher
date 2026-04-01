from datetime import datetime, timedelta

def create_event(summary, location, start_dt):
    start_buffer = start_dt - timedelta(hours=2)
    end_buffer = start_dt + timedelta(hours=3)

    return f"""BEGIN:VEVENT
SUMMARY:{summary}
LOCATION:{location}
DTSTART:{start_buffer.strftime('%Y%m%dT%H%M%SZ')}
DTEND:{end_buffer.strftime('%Y%m%dT%H%M%SZ')}
DESCRIPTION:🚗 Traffic alert window (2h before to 3h after)
END:VEVENT
"""

events = []

# Example hardcoded (we’ll replace with live scraping next)
events.append(create_event(
    "Atlanta United Match",
    "Mercedes-Benz Stadium, Atlanta, GA",
    datetime(2026, 4, 4, 19, 30)
))

ics = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//ATL Traffic//EN\n"
ics += "\n".join(events)
ics += "\nEND:VCALENDAR"

with open("gulcher-events.ics", "w") as f:
    f.write(ics)
