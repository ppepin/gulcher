# gulcher
Compile and present events in Centennial Yards.

Running `python3 generate_calendar.py` now writes three artifacts:

- [Calendar feed (`gulcher-events.ics`)](https://ppepin.github.io/gulcher/gulcher-events.ics)
- [Color schedule (`schedule-color.html`)](https://ppepin.github.io/gulcher/schedule-color.html)
- [E-ink schedule (`schedule-eink.html`)](https://ppepin.github.io/gulcher/schedule-eink.html)

Events come from the venue websites, the Atlanta Falcons schedule, and the Atlanta United calendar. Ticketmaster supplements Mercedes-Benz Stadium and State Farm Arena listings when `TICKETMASTER_API_KEY` is set in the environment. For deployed builds, configure it as a GitHub Actions repository secret with the same name. Parking and ticket add-ons are excluded, and overlapping listings are merged.

---
Updated November 11, 2026
