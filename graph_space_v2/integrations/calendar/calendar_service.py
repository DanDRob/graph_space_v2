from typing import Dict, List, Any, Optional, Tuple, Union
import datetime
import json
import os

from graph_space_v2.utils.errors.exceptions import IntegrationError
from graph_space_v2.integrations.calendar.models import CalendarEvent, Calendar
from graph_space_v2.utils.helpers.path_utils import ensure_dir_exists, get_data_dir

# Import providers at runtime only to avoid circular imports


def _get_google_calendar_provider():
    from graph_space_v2.integrations.calendar.providers.google_calendar import GoogleCalendarProvider
    return GoogleCalendarProvider


def _get_ical_provider():
    from graph_space_v2.integrations.calendar.providers.ical import ICalProvider
    return ICalProvider


class CalendarService:
    """Service for calendar operations and integration."""

    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize the calendar service.

        Args:
            storage_dir: Directory to store calendar data
        """
        self.storage_dir = storage_dir or os.path.join(
            get_data_dir(), "calendar")
        ensure_dir_exists(self.storage_dir)

        self.providers = {}
        self.sync_active = False
        self.last_sync = {}

        # Load existing configuration
        self._load_config()

        # Initialize cache
        self._cache = {
            "calendars": {},
            "events": {}
        }

        self._load_cache()

    def add_provider(self, provider_id: str, provider_instance: Any) -> None:
        self.providers[provider_id] = provider_instance

    def remove_provider(self, provider_id: str) -> None:
        if provider_id in self.providers:
            del self.providers[provider_id]

    def get_provider(self, provider_id: str) -> Any:
        if provider_id not in self.providers:
            raise IntegrationError(
                f"Calendar provider '{provider_id}' is not registered")

        return self.providers[provider_id]

    def get_calendars(self, provider_id: str) -> List[Calendar]:
        provider = self.get_provider(provider_id)

        try:
            calendars = provider.get_calendars()

            # Cache the calendars
            if provider_id not in self._cache["calendars"]:
                self._cache["calendars"][provider_id] = {}

            for calendar in calendars:
                self._cache["calendars"][provider_id][calendar.id] = calendar

            self._save_cache()
            return calendars

        except Exception as e:
            raise IntegrationError(
                f"Failed to get calendars from provider '{provider_id}': {str(e)}")

    def get_events(
        self,
        provider_id: str,
        calendar_id: str,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        use_cache: bool = True
    ) -> List[CalendarEvent]:
        provider = self.get_provider(provider_id)

        # Try to get from cache first if use_cache is True
        cache_key = f"{provider_id}:{calendar_id}:{start_date.isoformat()}:{end_date.isoformat()}"
        if use_cache and cache_key in self._cache["events"]:
            events_data = self._cache["events"][cache_key]

            # Convert cache data back to CalendarEvent objects
            events = []
            for event_data in events_data:
                events.append(CalendarEvent.from_dict(event_data))

            return events

        # If not in cache or cache not requested, get from provider
        try:
            events = provider.get_events(calendar_id, start_date, end_date)

            # Cache the results
            self._cache["events"][cache_key] = [event.to_dict()
                                                for event in events]
            self._save_cache()

            return events

        except Exception as e:
            raise IntegrationError(
                f"Failed to get events from calendar '{calendar_id}' "
                f"using provider '{provider_id}': {str(e)}"
            )

    def create_event(
        self,
        provider_id: str,
        calendar_id: str,
        title: str,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        description: str = "",
        location: str = "",
        attendees: List[str] = None,
        is_all_day: bool = False
    ) -> CalendarEvent:
        provider = self.get_provider(provider_id)

        # Create a new event object
        event = CalendarEvent(
            id="",  # This will be filled in by the provider
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            location=location,
            attendees=attendees or [],
            calendar_id=calendar_id,
            provider=provider_id,
            is_all_day=is_all_day
        )

        # Use the provider to create the event
        try:
            created_event = provider.create_event(calendar_id, event)

            # Invalidate cache for this calendar during this time period
            cache_keys_to_remove = []
            for key in self._cache["events"]:
                if f"{provider_id}:{calendar_id}:" in key:
                    cache_keys_to_remove.append(key)

            for key in cache_keys_to_remove:
                del self._cache["events"][key]

            self._save_cache()

            return created_event

        except Exception as e:
            raise IntegrationError(
                f"Failed to create event in calendar '{calendar_id}' "
                f"using provider '{provider_id}': {str(e)}"
            )

    def update_event(self, event: CalendarEvent) -> CalendarEvent:
        provider = self.get_provider(event.provider)

        try:
            updated_event = provider.update_event(event.calendar_id, event)

            # Invalidate cache for this calendar
            cache_keys_to_remove = []
            for key in self._cache["events"]:
                if f"{event.provider}:{event.calendar_id}:" in key:
                    cache_keys_to_remove.append(key)

            for key in cache_keys_to_remove:
                del self._cache["events"][key]

            self._save_cache()

            return updated_event

        except Exception as e:
            raise IntegrationError(f"Failed to update event: {str(e)}")

    def delete_event(self, provider_id: str, calendar_id: str, event_id: str) -> bool:
        provider = self.get_provider(provider_id)

        try:
            success = provider.delete_event(calendar_id, event_id)

            # Invalidate cache for this calendar
            cache_keys_to_remove = []
            for key in self._cache["events"]:
                if f"{provider_id}:{calendar_id}:" in key:
                    cache_keys_to_remove.append(key)

            for key in cache_keys_to_remove:
                del self._cache["events"][key]

            self._save_cache()

            return success

        except Exception as e:
            raise IntegrationError(f"Failed to delete event: {str(e)}")

    def _load_cache(self) -> None:
        cache_path = os.path.join(self.storage_dir, "cache.json")

        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r") as f:
                    cache_data = json.load(f)

                # Convert calendar dicts to Calendar objects
                calendars_cache = {}
                for provider_id, provider_calendars in cache_data.get("calendars", {}).items():
                    calendars_cache[provider_id] = {}
                    for calendar_id, calendar_data in provider_calendars.items():
                        calendars_cache[provider_id][calendar_id] = Calendar.from_dict(
                            calendar_data)

                # Keep events as dicts to avoid serialization issues
                events_cache = cache_data.get("events", {})

                self._cache = {
                    "calendars": calendars_cache,
                    "events": events_cache
                }

            except Exception as e:
                # If loading fails, start with an empty cache
                print(f"Failed to load calendar cache: {str(e)}")
                self._cache = {
                    "calendars": {},
                    "events": {}
                }
        else:
            # If no cache file exists, initialize empty cache
            self._cache = {
                "calendars": {},
                "events": {}
            }

    def _save_cache(self) -> None:
        cache_path = os.path.join(self.storage_dir, "cache.json")

        try:
            # Convert Calendar objects to dicts for serialization
            calendars_cache = {}
            for provider_id, provider_calendars in self._cache["calendars"].items():
                calendars_cache[provider_id] = {}
                for calendar_id, calendar in provider_calendars.items():
                    if isinstance(calendar, Calendar):
                        calendars_cache[provider_id][calendar_id] = calendar.to_dict(
                        )
                    else:
                        calendars_cache[provider_id][calendar_id] = calendar

            # Save the cache to disk
            cache_data = {
                "calendars": calendars_cache,
                "events": self._cache["events"]
            }

            with open(cache_path, "w") as f:
                json.dump(cache_data, f, indent=2)

        except Exception as e:
            print(f"Failed to save calendar cache: {str(e)}")

    def clear_cache(self) -> None:
        self._cache = {
            "calendars": {},
            "events": {}
        }
        self._save_cache()

    def _load_config(self) -> None:
        # Implementation of _load_config method
        pass
