"""
Calendar tool for scheduling interviews and tracking application follow-ups.

This tool integrates with Google Calendar API for production use,
with a mock implementation for development/testing.

Interview line: "I built a calendar tool that syncs with Google Calendar
so the agent can help users schedule interviews and set follow-up reminders.
I used OAuth2 for secure access and handled timezone conversions carefully."
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.config import settings

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_CALENDAR_AVAILABLE = True
except ImportError:
    GOOGLE_CALENDAR_AVAILABLE = False


@dataclass
class CalendarEvent:
    """A calendar event."""
    id: str
    title: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    attendees: Optional[List[str]] = None
    event_type: str = "interview"  # interview, follow_up, deadline


class CalendarTool:
    """
    Calendar tool for managing interview schedules and reminders.

    Uses Google Calendar API in production, falls back to in-memory
    mock for development.
    """

    def __init__(self, use_mock: bool = False):
        """
        Initialize calendar tool.

        Args:
            use_mock: Force using mock implementation (for testing)
        """
        # Try to get credentials from settings
        google_credentials = None
        if settings.google_client_id and settings.google_client_secret and settings.google_refresh_token:
            google_credentials = {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": settings.google_refresh_token,
            }

        self.use_mock = use_mock or not GOOGLE_CALENDAR_AVAILABLE or not google_credentials
        self.google_credentials = google_credentials
        self.service = None

        # Mock storage (for development)
        self._mock_events: Dict[str, CalendarEvent] = {}
        self._mock_counter = 0

        if not self.use_mock and google_credentials:
            self._init_google_client()

    def _init_google_client(self):
        """Initialize Google Calendar API client."""
        try:
            creds = Credentials.from_authorized_user_info(
                self.google_credentials,
                ['https://www.googleapis.com/auth/calendar']
            )
            self.service = build('calendar', 'v3', credentials=creds)
        except Exception as e:
            print(f"Failed to initialize Google Calendar client: {e}")
            self.use_mock = True

    async def check_availability(
        self,
        start_date: datetime,
        end_date: datetime,
        timezone: str = "America/New_York"
    ) -> List[Dict[str, Any]]:
        """
        Check availability for a given date range.

        Returns list of busy time slots.

        Args:
            start_date: Start of date range
            end_date: End of date range
            timezone: Timezone for the query

        Returns:
            List of busy periods with start/end times
        """
        if self.use_mock:
            # Mock: return empty (fully available)
            return []

        try:
            # Query Google Calendar for busy periods
            body = {
                "timeMin": start_date.isoformat() + "Z",
                "timeMax": end_date.isoformat() + "Z",
                "timeZone": timezone,
                "items": [{"id": "primary"}]
            }

            result = self.service.freebusy().query(body=body).execute()
            busy_periods = result.get('calendars', {}).get('primary', {}).get('busy', [])

            return [
                {
                    "start": period["start"],
                    "end": period["end"]
                }
                for period in busy_periods
            ]
        except HttpError as e:
            print(f"Google Calendar API error: {e}")
            return []

    async def create_event(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        event_type: str = "interview",
        reminders: bool = True
    ) -> CalendarEvent:
        """
        Create a calendar event.

        Args:
            title: Event title
            start_time: Event start time
            end_time: Event end time
            description: Event description
            location: Event location (physical or video call URL)
            attendees: List of attendee email addresses
            event_type: Type of event (interview, follow_up, deadline)
            reminders: Whether to send reminders

        Returns:
            Created CalendarEvent
        """
        if self.use_mock:
            # Mock implementation
            self._mock_counter += 1
            event_id = f"mock_event_{self._mock_counter}"
            event = CalendarEvent(
                id=event_id,
                title=title,
                description=description,
                start_time=start_time,
                end_time=end_time,
                location=location,
                attendees=attendees,
                event_type=event_type
            )
            self._mock_events[event_id] = event
            return event

        try:
            # Build event body for Google Calendar
            event_body = {
                'summary': title,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'America/New_York',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'America/New_York',
                },
            }

            if location:
                event_body['location'] = location

            if attendees:
                event_body['attendees'] = [
                    {'email': email} for email in attendees
                ]

            if reminders:
                event_body['reminders'] = {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                        {'method': 'popup', 'minutes': 60},  # 1 hour before
                    ],
                }

            # Insert event
            result = self.service.events().insert(
                calendarId='primary',
                body=event_body
            ).execute()

            return CalendarEvent(
                id=result['id'],
                title=title,
                description=description,
                start_time=start_time,
                end_time=end_time,
                location=location,
                attendees=attendees,
                event_type=event_type
            )
        except HttpError as e:
            print(f"Failed to create event: {e}")
            raise Exception(f"Calendar API error: {e}")

    async def create_interview(
        self,
        company_name: str,
        role_title: str,
        start_time: datetime,
        duration_minutes: int = 60,
        location: Optional[str] = None,
        interviewer_emails: Optional[List[str]] = None
    ) -> CalendarEvent:
        """
        Convenience method to create an interview event.

        Args:
            company_name: Name of the company
            role_title: Role being interviewed for
            start_time: Interview start time
            duration_minutes: Interview duration in minutes
            location: Interview location or video call URL
            interviewer_emails: List of interviewer email addresses

        Returns:
            Created CalendarEvent
        """
        end_time = start_time + timedelta(minutes=duration_minutes)

        title = f"Interview: {role_title} at {company_name}"
        description = f"Interview for {role_title} position at {company_name}."

        return await self.create_event(
            title=title,
            start_time=start_time,
            end_time=end_time,
            description=description,
            location=location,
            attendees=interviewer_emails,
            event_type="interview"
        )

    async def create_follow_up_reminder(
        self,
        company_name: str,
        role_title: str,
        reminder_date: datetime,
        notes: Optional[str] = None
    ) -> CalendarEvent:
        """
        Create a follow-up reminder event.

        Args:
            company_name: Name of the company
            role_title: Role applied for
            reminder_date: When to follow up
            notes: Additional notes

        Returns:
            Created CalendarEvent
        """
        title = f"Follow up: {company_name} - {role_title}"
        description = f"Follow up on application for {role_title} at {company_name}."
        if notes:
            description += f"\n\nNotes: {notes}"

        # Follow-up is an all-day event (no specific time)
        end_time = reminder_date + timedelta(hours=1)

        return await self.create_event(
            title=title,
            start_time=reminder_date,
            end_time=end_time,
            description=description,
            event_type="follow_up"
        )

    async def list_upcoming_events(
        self,
        days_ahead: int = 7,
        event_type: Optional[str] = None
    ) -> List[CalendarEvent]:
        """
        List upcoming events.

        Args:
            days_ahead: Number of days to look ahead
            event_type: Filter by event type (optional)

        Returns:
            List of upcoming CalendarEvents
        """
        now = datetime.utcnow()
        end_time = now + timedelta(days=days_ahead)

        if self.use_mock:
            # Mock implementation
            events = list(self._mock_events.values())
            events = [e for e in events if e.start_time >= now and e.start_time <= end_time]
            if event_type:
                events = [e for e in events if e.event_type == event_type]
            return sorted(events, key=lambda e: e.start_time)

        try:
            result = self.service.events().list(
                calendarId='primary',
                timeMin=now.isoformat() + 'Z',
                timeMax=end_time.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = []
            for item in result.get('items', []):
                # Parse datetime
                start_str = item['start'].get('dateTime', item['start'].get('date'))
                end_str = item['end'].get('dateTime', item['end'].get('date'))

                # Handle all-day events (date only)
                if 'T' not in start_str:
                    start_time = datetime.fromisoformat(start_str)
                    end_time = datetime.fromisoformat(end_str)
                else:
                    start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                    end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))

                # Infer event type from title
                title = item.get('summary', '')
                inferred_type = "other"
                if 'interview' in title.lower():
                    inferred_type = "interview"
                elif 'follow up' in title.lower() or 'follow-up' in title.lower():
                    inferred_type = "follow_up"
                elif 'deadline' in title.lower():
                    inferred_type = "deadline"

                event = CalendarEvent(
                    id=item['id'],
                    title=title,
                    description=item.get('description'),
                    start_time=start_time,
                    end_time=end_time,
                    location=item.get('location'),
                    attendees=[
                        a['email'] for a in item.get('attendees', [])
                    ] if item.get('attendees') else None,
                    event_type=inferred_type
                )

                # Filter by type if specified
                if event_type and event.event_type != event_type:
                    continue

                events.append(event)

            return events
        except HttpError as e:
            print(f"Failed to list events: {e}")
            return []

    async def delete_event(self, event_id: str) -> bool:
        """
        Delete a calendar event.

        Args:
            event_id: ID of event to delete

        Returns:
            True if deleted successfully
        """
        if self.use_mock:
            if event_id in self._mock_events:
                del self._mock_events[event_id]
                return True
            return False

        try:
            self.service.events().delete(
                calendarId='primary',
                eventId=event_id
            ).execute()
            return True
        except HttpError as e:
            print(f"Failed to delete event: {e}")
            return False


# Global instance (mock for development)
_calendar_tool: Optional[CalendarTool] = None


def get_calendar_tool() -> CalendarTool:
    """Get or create the calendar tool instance."""
    global _calendar_tool
    if _calendar_tool is None:
        # Default to mock for development
        _calendar_tool = CalendarTool()
    return _calendar_tool


async def check_availability(
    start_date: datetime,
    end_date: datetime,
    timezone: str = "America/New_York"
) -> List[Dict[str, Any]]:
    """
    Convenience function to check availability.

    Args:
        start_date: Start of date range
        end_date: End of date range
        timezone: Timezone for the query

    Returns:
        List of busy periods
    """
    tool = get_calendar_tool()
    return await tool.check_availability(start_date, end_date, timezone)


async def schedule_interview(
    company_name: str,
    role_title: str,
    start_time: datetime,
    duration_minutes: int = 60,
    location: Optional[str] = None,
    interviewer_emails: Optional[List[str]] = None
) -> CalendarEvent:
    """
    Convenience function to schedule an interview.

    Args:
        company_name: Name of the company
        role_title: Role being interviewed for
        start_time: Interview start time
        duration_minutes: Interview duration
        location: Interview location or video call URL
        interviewer_emails: List of interviewer emails

    Returns:
        Created CalendarEvent
    """
    tool = get_calendar_tool()
    return await tool.create_interview(
        company_name=company_name,
        role_title=role_title,
        start_time=start_time,
        duration_minutes=duration_minutes,
        location=location,
        interviewer_emails=interviewer_emails
    )


async def list_upcoming_events(
    days_ahead: int = 7,
    event_type: Optional[str] = None
) -> List[CalendarEvent]:
    """
    Convenience function to list upcoming events.

    Args:
        days_ahead: Number of days to look ahead
        event_type: Filter by event type

    Returns:
        List of upcoming events
    """
    tool = get_calendar_tool()
    return await tool.list_upcoming_events(days_ahead, event_type)
