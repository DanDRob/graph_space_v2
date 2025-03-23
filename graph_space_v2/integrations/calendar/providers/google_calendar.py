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

        self.service = None
        self._authenticate()

    def _authenticate(self) -> None:
        """Authenticate with Google Calendar API"""
        creds = self.auth.get_credentials()
        self.service = build('calendar', 'v3', credentials=creds)

    def get_calendars(self) -> List[Calendar]:
        """Get list of calendars"""
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
                start_time = datetime.datetime.fromisoformat(start_date_str)
                # End date is exclusive in Google API, so subtract one day
                end_date = datetime.datetime.fromisoformat(end_date_str)
                end_time = end_date - datetime.timedelta(days=1)
            else:
                # Parse regular events with a specific time
                start_time_str = start.get('dateTime')
                end_time_str = end.get('dateTime')

                if start_time_str:
                    # Remove 'Z' and handle timezone
                    start_time = datetime.datetime.fromisoformat(
                        start_time_str.replace('Z', '+00:00'))

                if end_time_str:
                    # Remove 'Z' and handle timezone
                    end_time = datetime.datetime.fromisoformat(
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
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            return True
        except Exception:
            return False

    def _event_to_google_format(self, event: CalendarEvent) -> Dict[str, Any]:
        """Convert a CalendarEvent to Google Calendar API format"""
        google_event = {
            'summary': event.title,
            'description': event.description,
            'location': event.location,
        }

        # Handle all-day events differently
        if event.is_all_day:
            # For all-day events, we use 'date' instead of 'dateTime'
            start_date = event.start_time.date().isoformat()
            # Google API needs end date to be exclusive, so add one day
            end_date = (event.end_time.date() +
                        datetime.timedelta(days=1)).isoformat()

            google_event['start'] = {'date': start_date}
            google_event['end'] = {'date': end_date}
        else:
            # Regular events with specific times
            start_time = event.start_time.isoformat()
            end_time = event.end_time.isoformat()

            google_event['start'] = {'dateTime': start_time, 'timeZone': 'UTC'}
            google_event['end'] = {'dateTime': end_time, 'timeZone': 'UTC'}

        # Add attendees if specified
        if event.attendees:
            google_event['attendees'] = [
                {'email': attendee} for attendee in event.attendees
            ]

        # Add recurrence rule if specified
        if event.is_recurring and event.recurrence_rule:
            google_event['recurrence'] = [event.recurrence_rule]

        return google_event

    def _google_event_to_calendar_event(
        self,
        event_data: Dict[str, Any],
        calendar_id: str
    ) -> CalendarEvent:
        """Convert Google Calendar API format to CalendarEvent"""
        # Parse start and end times
        start = event_data.get('start', {})
        end = event_data.get('end', {})

        start_time = None
        end_time = None
        is_all_day = False

        # Handle all-day events
        if 'date' in start:
            is_all_day = True
            start_date_str = start.get('date')
            end_date_str = end.get('date')

            # Parse the date strings
            start_time = datetime.datetime.fromisoformat(start_date_str)
            # End date is exclusive in Google API, so subtract one day
            end_date = datetime.datetime.fromisoformat(end_date_str)
            end_time = end_date - datetime.timedelta(days=1)
        else:
            # Parse regular events with a specific time
            start_time_str = start.get('dateTime')
            end_time_str = end.get('dateTime')

            if start_time_str:
                # Remove 'Z' and handle timezone
                start_time = datetime.datetime.fromisoformat(
                    start_time_str.replace('Z', '+00:00'))

            if end_time_str:
                # Remove 'Z' and handle timezone
                end_time = datetime.datetime.fromisoformat(
                    end_time_str.replace('Z', '+00:00'))

        # Get attendees
        attendees = []
        for attendee in event_data.get('attendees', []):
            email = attendee.get('email')
            if email:
                attendees.append(email)

        # Create event object
        return CalendarEvent(
            id=event_data['id'],
            title=event_data.get('summary', 'Untitled Event'),
            description=event_data.get('description', ''),
            start_time=start_time,
            end_time=end_time,
            location=event_data.get('location', ''),
            attendees=attendees,
            provider_data=event_data,
            calendar_id=calendar_id,
            provider='google',
            is_all_day=is_all_day,
            is_recurring=bool(event_data.get('recurrence')),
            recurrence_rule=event_data.get('recurrence', [None])[
                0] if event_data.get('recurrence') else None
        )
