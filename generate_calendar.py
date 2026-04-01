from icalendar import Calendar, Event
from datetime import datetime

cal = Calendar()
event = Event()
event.add('summary', 'Test Event')
event.add('dtstart', datetime(2026, 4, 1, 20, 0))
event.add('dtend', datetime(2026, 4, 1, 21, 0))
cal.add_component(event)

# Write to repo root
with open('gulcher-events.ics', 'wb') as f:
    f.write(cal.to_ical())