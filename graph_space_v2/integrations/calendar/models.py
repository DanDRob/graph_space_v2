from typing import Dict, List, Any, Optional, Tuple
import datetime
import json


class CalendarEvent:
    def __init__(
        self,
        id: str,
        title: str,
        description: str = "",
        start_time: datetime.datetime = None,
        end_time: datetime.datetime = None,
        location: str = "",
        attendees: List[str] = None,
        provider_data: Dict[str, Any] = None,
        calendar_id: str = None,
        provider: str = None,
        is_all_day: bool = False,
        is_recurring: bool = False,
        recurrence_rule: str = None
    ):
        self.id = id
        self.title = title
        self.description = description
        self.start_time = start_time or datetime.datetime.now()
        self.end_time = end_time or (
            self.start_time + datetime.timedelta(hours=1))
        self.location = location
        self.attendees = attendees or []
        self.provider_data = provider_data or {}
        self.calendar_id = calendar_id
        self.provider = provider
        self.is_all_day = is_all_day
        self.is_recurring = is_recurring
        self.recurrence_rule = recurrence_rule

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "location": self.location,
            "attendees": self.attendees,
            "provider_data": self.provider_data,
            "calendar_id": self.calendar_id,
            "provider": self.provider,
            "is_all_day": self.is_all_day,
            "is_recurring": self.is_recurring,
            "recurrence_rule": self.recurrence_rule
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CalendarEvent':
        # Convert ISO format strings back to datetime objects
        start_time = None
        end_time = None

        if data.get("start_time"):
            try:
                start_time = datetime.datetime.fromisoformat(
                    data["start_time"])
            except (ValueError, TypeError):
                start_time = None

        if data.get("end_time"):
            try:
                end_time = datetime.datetime.fromisoformat(data["end_time"])
            except (ValueError, TypeError):
                end_time = None

        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            start_time=start_time,
            end_time=end_time,
            location=data.get("location", ""),
            attendees=data.get("attendees", []),
            provider_data=data.get("provider_data", {}),
            calendar_id=data.get("calendar_id"),
            provider=data.get("provider"),
            is_all_day=data.get("is_all_day", False),
            is_recurring=data.get("is_recurring", False),
            recurrence_rule=data.get("recurrence_rule")
        )


class Calendar:
    def __init__(
        self,
        id: str,
        name: str,
        description: str = "",
        provider: str = "",
        provider_data: Dict[str, Any] = None,
        color: str = "#3498db"
    ):
        self.id = id
        self.name = name
        self.description = description
        self.provider = provider
        self.provider_data = provider_data or {}
        self.color = color

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "provider": self.provider,
            "provider_data": self.provider_data,
            "color": self.color
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Calendar':
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            provider=data.get("provider", ""),
            provider_data=data.get("provider_data", {}),
            color=data.get("color", "#3498db")
        )
