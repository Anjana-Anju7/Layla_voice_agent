from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from auth import get_credentials


def _service():
    return build("calendar", "v3", credentials=get_credentials())


def _parse_datetime(dt_str: str) -> datetime:
    """Parse ISO format or natural-ish datetime string."""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {dt_str}")


def read_calendar(days_ahead: int = 1) -> str:
    """
    Read upcoming calendar events.
    days_ahead: how many days ahead to look (default 1 = today only)
    """
    svc = _service()
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days_ahead)

    result = svc.events().list(
        calendarId="primary",
        timeMin=now.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=20,
    ).execute()

    events = result.get("items", [])
    if not events:
        period = "today" if days_ahead == 1 else f"the next {days_ahead} days"
        return f"No events found for {period}."

    lines = []
    for e in events:
        start = e["start"].get("dateTime", e["start"].get("date", ""))
        end_t = e["end"].get("dateTime", e["end"].get("date", ""))
        title = e.get("summary", "(no title)")
        event_id = e["id"]

        if "T" in start:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            start_str = dt.strftime("%A %d %b, %I:%M %p")
        else:
            start_str = start

        lines.append(f"- ID:{event_id} | {start_str} | {title}")

    return "\n".join(lines)


def list_calendars() -> str:
    """List all available calendars for the user."""
    svc = _service()
    result = svc.calendarList().list().execute()
    calendars = result.get("items", [])
    if not calendars:
        return "No calendars found."
    lines = [f"- ID:{c['id']} | {c.get('summary', 'Unnamed')}" for c in calendars]
    return "\n".join(lines)


def create_event(
    title: str,
    start: str,
    end: str,
    description: str = "",
    calendar_id: str = "primary",
) -> str:
    """
    Create a new calendar event.
    title: event name
    start: ISO datetime string, e.g. '2026-06-10T14:00:00'
    end: ISO datetime string, e.g. '2026-06-10T15:00:00'
    description: optional event description
    calendar_id: calendar to add the event to (default: primary)
    """
    svc = _service()
    event_body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start, "timeZone": "UTC"},
        "end": {"dateTime": end, "timeZone": "UTC"},
    }
    event = svc.events().insert(calendarId=calendar_id, body=event_body).execute()
    return f"Event created: '{title}' on {start}. ID:{event['id']}"


def modify_event(
    event_id: str,
    title: str = None,
    new_start: str = None,
    new_end: str = None,
    description: str = None,
    calendar_id: str = "primary",
) -> str:
    """
    Modify an existing calendar event. Only provided fields are changed.
    Preserves original duration if only new_start is given.
    event_id: the ID of the event to modify
    title: new title (optional)
    new_start: new start datetime ISO string (optional)
    new_end: new end datetime ISO string (optional)
    description: new description (optional)
    calendar_id: calendar containing the event (default: primary)
    """
    svc = _service()
    event = svc.events().get(calendarId=calendar_id, eventId=event_id).execute()

    if title:
        event["summary"] = title
    if description is not None:
        event["description"] = description

    if new_start:
        old_start = datetime.fromisoformat(event["start"]["dateTime"].replace("Z", "+00:00"))
        old_end = datetime.fromisoformat(event["end"]["dateTime"].replace("Z", "+00:00"))
        duration = old_end - old_start

        new_start_dt = _parse_datetime(new_start).replace(tzinfo=timezone.utc)
        event["start"]["dateTime"] = new_start_dt.isoformat()

        if new_end:
            new_end_dt = _parse_datetime(new_end).replace(tzinfo=timezone.utc)
        else:
            new_end_dt = new_start_dt + duration  # preserve duration

        event["end"]["dateTime"] = new_end_dt.isoformat()

    updated = svc.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
    return f"Event updated: '{updated.get('summary')}'. ID:{event_id}"


def delete_event(event_id: str, calendar_id: str = "primary") -> str:
    """
    Delete a calendar event by its ID.
    event_id: the ID of the event to delete
    calendar_id: calendar containing the event (default: primary)
    """
    svc = _service()
    svc.events().delete(calendarId=calendar_id, eventId=event_id).execute()
    return f"Event {event_id} deleted."
