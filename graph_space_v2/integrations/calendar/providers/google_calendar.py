import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import re

# Google API client libraries
try:
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

from graph_space_v2.utils.errors.exceptions import IntegrationError
from graph_space_v2.integrations.calendar.models import CalendarEvent, Calendar
from graph_space_v2.integrations.google.auth import GoogleAuth
from graph_space_v2.utils.helpers.path_utils import ensure_dir_exists, get_data_dir


class GoogleCalendarProvider:
    """Provider for Google Calendar integration."""

    def __init__(
        self,
        credentials_file: Optional[str] = None,
        token_file: Optional[str] = None,
        calendar_ids: Optional[List[str]] = None
    ):
        """
        Initialize Google Calendar provider.

        Args:
            credentials_file: Path to credentials JSON file
            token_file: Path to token file
            calendar_ids: List of calendar IDs to access
        """
        if not GOOGLE_API_AVAILABLE:
            raise ImportError(
                "Google API client libraries are required but not installed. "
                "Install them with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            )

        # Use default token file location if not provided
        self.token_file = token_file or os.path.join(
            get_data_dir(), "credentials", "calendar_token.json")
        ensure_dir_exists(os.path.dirname(self.token_file))

        self.credentials_file = credentials_file
        self.calendar_ids = calendar_ids or ['primary']

        # Initialize Google Auth
        self.auth = GoogleAuth(
            credentials_file=credentials_file,
            token_file=self.token_file,
            scopes=['https://www.googleapis.com/auth/calendar.readonly']
        )

        # Auth status flags
        self.auth_required = False
        self.authenticated = False

        self.service = None

        # Only authenticate immediately if auth is not deferred
        if not self.auth_required:
            self._authenticate()

    def _authenticate(self) -> None:
        """Authenticate with Google Calendar API"""
        try:
            creds = self.auth.get_credentials()

            if not creds:
                if self.auth_required:
                    # Just mark as not authenticated, don't raise exception
                    self.authenticated = False
                    return
                else:
                    raise ValueError("No valid credentials found")

            self.service = build('calendar', 'v3', credentials=creds)
            self.authenticated = True
        except Exception as e:
            self.authenticated = False
            if not self.auth_required:
                raise IntegrationError(
                    f"Failed to authenticate with Google Calendar: {e}")
            print(f"Warning: Failed to authenticate with Google Calendar: {e}")

    def _ensure_authenticated(self) -> bool:
        """Ensure service is authenticated before making API calls"""
        if not self.authenticated or not self.service:
            self._authenticate()
        return self.authenticated

    def get_calendars(self) -> List[Calendar]:
        """Get list of calendars"""
        if not self._ensure_authenticated():
            raise IntegrationError("Not authenticated with Google Calendar")

        response = self.service.calendarList().list().execute()
        calendars = []

        for item in response.get('items', []):
            calendar = Calendar(
                id=item['id'],
                name=item.get('summary', 'Untitled'),
                description=item.get('description', ''),
                provider='google',
                provider_data=item,
                color=item.get('backgroundColor', '#3498db')
            )
            calendars.append(calendar)

        return calendars

    def get_events(
        self,
        calendar_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[CalendarEvent]:
        """Get events from a calendar within the date range"""
        if not self._ensure_authenticated():
            raise IntegrationError("Not authenticated with Google Calendar")

        # Format dates for Google API
        time_min = start_date.isoformat() + 'Z'
        time_max = end_date.isoformat() + 'Z'

        # Query events
        response = self.service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=2500,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = []
        for item in response.get('items', []):
            # Skip cancelled events
            if item.get('status') == 'cancelled':
                continue

            # Parse start and end times
            start = item.get('start', {})
            end = item.get('end', {})

            start_time = None
            end_time = None
            is_all_day = False

            # Handle all-day events
            if 'date' in start:
                is_all_day = True
                start_date_str = start.get('date')
                end_date_str = end.get('date')

                # Parse the date strings
                start_time = datetime.fromisoformat(start_date_str)
                # End date is exclusive in Google API, so subtract one day
                end_date = datetime.fromisoformat(end_date_str)
                end_time = end_date - timedelta(days=1)
            else:
                # Parse regular events with a specific time
                start_time_str = start.get('dateTime')
                end_time_str = end.get('dateTime')

                if start_time_str:
                    # Remove 'Z' and handle timezone
                    start_time = datetime.fromisoformat(
                        start_time_str.replace('Z', '+00:00'))

                if end_time_str:
                    # Remove 'Z' and handle timezone
                    end_time = datetime.fromisoformat(
                        end_time_str.replace('Z', '+00:00'))

            # Get attendees
            attendees = []
            for attendee in item.get('attendees', []):
                email = attendee.get('email')
                if email:
                    attendees.append(email)

            # Create event object
            event = CalendarEvent(
                id=item['id'],
                title=item.get('summary', 'Untitled Event'),
                description=item.get('description', ''),
                start_time=start_time,
                end_time=end_time,
                location=item.get('location', ''),
                attendees=attendees,
                provider_data=item,
                calendar_id=calendar_id,
                provider='google',
                is_all_day=is_all_day,
                is_recurring=bool(item.get('recurrence')),
                recurrence_rule=item.get('recurrence', [None])[
                    0] if item.get('recurrence') else None
            )

            events.append(event)

        return events

    def create_event(self, calendar_id: str, event: CalendarEvent) -> CalendarEvent:
        """Create a new event in Google Calendar"""
        if not self._ensure_authenticated():
            raise IntegrationError("Not authenticated with Google Calendar")

        event_data = self._event_to_google_format(event)

        # Call the API to create the event
        response = self.service.events().insert(
            calendarId=calendar_id,
            body=event_data
        ).execute()

        # Convert the response to a CalendarEvent
        return self._google_event_to_calendar_event(response, calendar_id)

    def update_event(self, calendar_id: str, event: CalendarEvent) -> CalendarEvent:
        """Update an existing event in Google Calendar"""
        if not self._ensure_authenticated():
            raise IntegrationError("Not authenticated with Google Calendar")

        event_data = self._event_to_google_format(event)

        # Call the API to update the event
        response = self.service.events().update(
            calendarId=calendar_id,
            eventId=event.id,
            body=event_data
        ).execute()

        # Convert the response to a CalendarEvent
        return self._google_event_to_calendar_event(response, calendar_id)

    def delete_event(self, calendar_id: str, event_id: str) -> bool:
        """Delete an event from Google Calendar"""
        if not self._ensure_authenticated():
            raise IntegrationError("Not authenticated with Google Calendar")

        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            return True
        except Exception as e:
            raise IntegrationError(f"Failed to delete event: {e}")

    def _event_to_google_format(self, event: CalendarEvent) -> Dict[str, Any]:
        """Convert a CalendarEvent to Google Calendar API format"""
        # Create basic event data
        event_data = {
            'summary': event.title,
            'location': event.location,
            'description': event.description,
            'status': 'confirmed'
        }

        # Set start and end times based on all-day status
        if event.is_all_day:
            # All-day events use date instead of dateTime
            start_date = event.start_time.date().isoformat(
            ) if event.start_time else datetime.now().date().isoformat()
            end_date = event.end_time.date().isoformat() if event.end_time else (
                datetime.now() + timedelta(days=1)).date().isoformat()

            event_data['start'] = {'date': start_date}
            event_data['end'] = {'date': end_date}
        else:
            # Regular events use dateTime
            start_time = event.start_time.isoformat(
            ) if event.start_time else datetime.now().isoformat()
            end_time = event.end_time.isoformat() if event.end_time else (
                datetime.now() + timedelta(hours=1)).isoformat()

            event_data['start'] = {'dateTime': start_time, 'timeZone': 'UTC'}
            event_data['end'] = {'dateTime': end_time, 'timeZone': 'UTC'}

        # Add attendees if provided
        if event.attendees:
            event_data['attendees'] = [{'email': email}
                                       for email in event.attendees]

        # Add recurrence if provided
        if event.recurrence_rule:
            event_data['recurrence'] = [event.recurrence_rule]

        return event_data

    def _google_event_to_calendar_event(self, google_event: Dict[str, Any], calendar_id: str) -> CalendarEvent:
        """Convert a Google Calendar API event to a CalendarEvent"""
        # Parse start and end times
        start = google_event.get('start', {})
        end = google_event.get('end', {})

        start_time = None
        end_time = None
        is_all_day = False

        # Handle all-day events
        if 'date' in start:
            is_all_day = True
            start_date_str = start.get('date')
            end_date_str = end.get('date')

            # Parse the date strings
            start_time = datetime.fromisoformat(start_date_str)
            # End date is exclusive in Google API, so subtract one day
            end_date = datetime.fromisoformat(end_date_str)
            end_time = end_date - timedelta(days=1)
        else:
            # Parse regular events with a specific time
            start_time_str = start.get('dateTime')
            end_time_str = end.get('dateTime')

            if start_time_str:
                # Remove 'Z' and handle timezone
                start_time = datetime.fromisoformat(
                    start_time_str.replace('Z', '+00:00'))

            if end_time_str:
                # Remove 'Z' and handle timezone
                end_time = datetime.fromisoformat(
                    end_time_str.replace('Z', '+00:00'))

        # Get attendees
        attendees = []
        for attendee in google_event.get('attendees', []):
            email = attendee.get('email')
            if email:
                attendees.append(email)

        # Create event object
        return CalendarEvent(
            id=google_event['id'],
            title=google_event.get('summary', 'Untitled Event'),
            description=google_event.get('description', ''),
            start_time=start_time,
            end_time=end_time,
            location=google_event.get('location', ''),
            attendees=attendees,
            provider_data=google_event,
            calendar_id=calendar_id,
            provider='google',
            is_all_day=is_all_day,
            is_recurring=bool(google_event.get('recurrence')),
            recurrence_rule=google_event.get('recurrence', [None])[
                0] if google_event.get('recurrence') else None
        )

    def set_credentials(self, credentials):
        """
        Set credentials for use with web-based authentication flow.

        Args:
            credentials: OAuth2 credentials from web auth flow
        """
        from googleapiclient.discovery import build
        self.service = build('calendar', 'v3', credentials=credentials)
        self.authenticated = True
