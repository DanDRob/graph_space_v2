from typing import Dict, List, Any, Optional
import datetime
import os
from urllib.parse import urlparse
import requests
import tempfile
import hashlib
import json

# iCal libraries
try:
    import icalendar
    import recurring_ical_events
    ICAL_AVAILABLE = True
except ImportError:
    ICAL_AVAILABLE = False

from graph_space_v2.integrations.calendar.calendar_service import CalendarEvent, Calendar
from graph_space_v2.utils.errors.exceptions import IntegrationError
from graph_space_v2.utils.helpers.path_utils import ensure_dir_exists, get_data_dir


class ICalProvider:
    """Provider for reading iCalendar format calendars."""

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the iCalendar provider.

        Args:
            cache_dir: Directory to cache calendar data
        """
        self.cache_dir = cache_dir or os.path.join(
            get_data_dir(), "calendar/ical_cache")
        ensure_dir_exists(self.cache_dir)

        self.calendars = {}
        self._load_cache()

        if not ICAL_AVAILABLE:
            raise ImportError(
                "icalendar and recurring_ical_events are required but not installed. "
                "Install them with: pip install icalendar recurring_ical_events"
            )

        self.urls = []
        self.files = []

        # Initialize calendars
        self._init_calendars()

    def _init_calendars(self) -> None:
        """Initialize calendar info from URLs and files"""
        # Add URL calendars
        for i, calendar_info in enumerate(self.urls):
            url = calendar_info['url']
            name = calendar_info.get('name') or f"Calendar {i+1}"

            # Generate unique ID from URL
            calendar_id = f"url_{self._safe_id(url)}"

            self.calendars[calendar_id] = {
                'id': calendar_id,
                'name': name,
                'type': 'url',
                'source': url,
                'color': calendar_info.get('color', '#3498db')
            }

        # Add file calendars
        for i, calendar_info in enumerate(self.files):
            file_path = calendar_info['file']
            name = calendar_info.get(
                'name') or f"Calendar {len(self.urls) + i + 1}"

            # Generate unique ID from file path
            calendar_id = f"file_{self._safe_id(file_path)}"

            self.calendars[calendar_id] = {
                'id': calendar_id,
                'name': name,
                'type': 'file',
                'source': file_path,
                'color': calendar_info.get('color', '#3498db')
            }

    def _safe_id(self, text: str) -> str:
        """Convert text to a safe ID format"""
        return hashlib.md5(text.encode()).hexdigest()

    def add_calendar(self, url_or_file: str, name: str, is_url: bool = True) -> str:
        """Add a new calendar"""
        calendar_id = f"{'url' if is_url else 'file'}_{self._safe_id(url_or_file)}"

        self.calendars[calendar_id] = {
            'id': calendar_id,
            'name': name,
            'type': 'url' if is_url else 'file',
            'source': url_or_file,
            'color': '#3498db'
        }

        if is_url:
            self.urls.append({'url': url_or_file, 'name': name})
        else:
            self.files.append({'file': url_or_file, 'name': name})

        return calendar_id

    def get_calendars(self) -> List[Calendar]:
        """Get list of calendars"""
        return [
            Calendar(
                id=cal_info['id'],
                name=cal_info['name'],
                description=f"iCal calendar from {cal_info['type']}: {cal_info['source']}",
                provider='ical',
                provider_data=cal_info,
                color=cal_info.get('color', '#3498db')
            )
            for cal_info in self.calendars.values()
        ]

    def get_events(
        self,
        calendar_id: str,
        start_date: datetime.datetime,
        end_date: datetime.datetime
    ) -> List[CalendarEvent]:
        """Get events from a calendar"""
        if calendar_id not in self.calendars:
            raise IntegrationError(f"Calendar not found: {calendar_id}")

        calendar_info = self.calendars[calendar_id]

        # Get calendar data
        calendar_data = self._get_calendar_data(calendar_info)
        if not calendar_data:
            return []

        # Parse events
        events = []

        try:
            # Parse iCal data
            cal = icalendar.Calendar.from_ical(calendar_data)

            # Get events including recurring ones
            ical_events = recurring_ical_events.of(
                cal).between(start_date, end_date)

            # Convert to CalendarEvent objects
            for event in ical_events:
                cal_event = self._ical_to_calendar_event(event, calendar_id)
                if cal_event:
                    events.append(cal_event)

        except Exception as e:
            print(f"Error parsing iCal data: {e}")

        return events

    def create_event(self, calendar_id: str, event: CalendarEvent) -> CalendarEvent:
        """Create a new event in a calendar"""
        # iCal provider is read-only, cannot create events
        raise NotImplementedError(
            "iCal provider is read-only, cannot create events")

    def update_event(self, calendar_id: str, event: CalendarEvent) -> CalendarEvent:
        """Update an existing event"""
        # iCal provider is read-only, cannot update events
        raise NotImplementedError(
            "iCal provider is read-only, cannot update events")

    def delete_event(self, calendar_id: str, event_id: str) -> bool:
        """Delete an event"""
        # iCal provider is read-only, cannot delete events
        raise NotImplementedError(
            "iCal provider is read-only, cannot delete events")

    def _get_calendar_data(self, calendar_info: Dict[str, Any]) -> Optional[bytes]:
        """Get calendar data from URL or file"""
        try:
            if calendar_info['type'] == 'url':
                # Download from URL
                url = calendar_info['source']

                # Check if we have a cached version first
                cache_file = os.path.join(
                    self.cache_dir, f"{self._safe_id(url)}.ics")

                # Download the file
                response = requests.get(url)
                if response.status_code != 200:
                    print(
                        f"Error downloading iCal file: {response.status_code}")
                    return None

                # Save to cache
                with open(cache_file, 'wb') as f:
                    f.write(response.content)

                return response.content

            elif calendar_info['type'] == 'file':
                # Read from file
                file_path = calendar_info['source']
                if not os.path.exists(file_path):
                    print(f"iCal file not found: {file_path}")
                    return None

                with open(file_path, 'rb') as f:
                    return f.read()

            return None

        except Exception as e:
            print(f"Error getting calendar data: {e}")
            return None

    def _ical_to_calendar_event(
        self,
        event: icalendar.cal.Event,
        calendar_id: str
    ) -> Optional[CalendarEvent]:
        """Convert iCal event to CalendarEvent"""
        try:
            # Get event ID
            event_id = None
            if 'UID' in event:
                event_id = str(event['UID'])

            if not event_id:
                event_id = str(event.get('SUMMARY', '')) + \
                    '_' + str(event.get('DTSTART', ''))

            # Get event title
            title = str(event.get('SUMMARY', 'Untitled Event'))

            # Get event description
            description = str(event.get('DESCRIPTION', ''))

            # Get start and end times
            start = event.get('DTSTART').dt
            end = event.get('DTEND').dt if 'DTEND' in event else start

            # Check if it's an all-day event
            is_all_day = isinstance(start, datetime.date) and not isinstance(
                start, datetime.datetime)

            # Convert to datetime if it's a date
            if is_all_day:
                start = datetime.datetime.combine(start, datetime.time.min)
                end = datetime.datetime.combine(end, datetime.time.min)

            # Get location
            location = str(event.get('LOCATION', ''))

            # Check for recurrence
            is_recurring = 'RRULE' in event
            recurrence_rule = None
            if is_recurring:
                recurrence_rule = str(event['RRULE'])

            # Create CalendarEvent
            return CalendarEvent(
                id=event_id,
                title=title,
                description=description,
                start_time=start,
                end_time=end,
                location=location,
                provider_data=dict(event),
                calendar_id=calendar_id,
                provider='ical',
                is_all_day=is_all_day,
                is_recurring=is_recurring,
                recurrence_rule=recurrence_rule
            )

        except Exception as e:
            print(f"Error converting iCal event: {e}")
            return None

    def _load_cache(self) -> None:
        """Load cached calendar data"""
        # Implementation of _load_cache method
        pass
