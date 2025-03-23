from typing import Dict, Any, List, Optional, Set, ClassVar, Union
from datetime import datetime, timedelta
import datetime as dt
from graph_space_v2.core.models.base import BaseModel


class Task(BaseModel):
    """Model representing a task in the system."""

    # Task status constants
    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELED = "canceled"

    # Task priority constants
    PRIORITY_LOW = "low"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_HIGH = "high"

    # Task recurrence frequency constants
    FREQUENCY_DAILY = "daily"
    FREQUENCY_WEEKLY = "weekly"
    FREQUENCY_MONTHLY = "monthly"

    # Add task-specific fields to the serializable fields
    fields: ClassVar[Set[str]] = BaseModel.fields.union({
        'title', 'description', 'status', 'due_date', 'priority', 'tags',
        'project', 'is_recurring', 'recurrence_frequency', 'recurrence_start_date',
        'recurrence_next_run', 'recurrence_enabled', 'calendar_sync',
        'calendar_id', 'calendar_provider'
    })

    def __init__(
        self,
        id: Optional[str] = None,
        title: str = "",
        description: str = "",
        status: str = STATUS_PENDING,
        due_date: Optional[str] = None,
        priority: str = PRIORITY_MEDIUM,
        tags: Optional[List[str]] = None,
        project: str = "",
        is_recurring: bool = False,
        recurrence_frequency: str = "",
        recurrence_start_date: Optional[str] = None,
        recurrence_next_run: Optional[str] = None,
        recurrence_enabled: bool = True,
        calendar_sync: bool = False,
        calendar_id: str = "",
        calendar_provider: str = "",
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize a Task.

        Args:
            id: Unique identifier
            title: Task title
            description: Task description
            status: Task status (pending, in_progress, completed, canceled)
            due_date: Due date (ISO format string)
            priority: Task priority (low, medium, high)
            tags: List of tags
            project: Project name
            is_recurring: Whether the task is recurring
            recurrence_frequency: Recurrence frequency (daily, weekly, monthly)
            recurrence_start_date: Start date for recurrence (ISO format string)
            recurrence_next_run: Next scheduled run (ISO format string)
            recurrence_enabled: Whether recurrence is enabled
            calendar_sync: Whether to sync with calendar
            calendar_id: External calendar ID
            calendar_provider: Calendar provider (e.g., google, ical)
            created_at: Creation timestamp
            updated_at: Last update timestamp
            **kwargs: Additional attributes
        """
        super().__init__(
            id=id,
            created_at=created_at,
            updated_at=updated_at,
            **kwargs
        )
        self.title = title
        self.description = description
        self.status = status
        self.due_date = due_date
        self.priority = priority
        self.tags = tags or []
        self.project = project

        # Recurrence fields
        self.is_recurring = is_recurring
        self.recurrence_frequency = recurrence_frequency
        self.recurrence_start_date = recurrence_start_date or datetime.now().isoformat()
        self.recurrence_next_run = recurrence_next_run
        self.recurrence_enabled = recurrence_enabled

        # Calendar integration fields
        self.calendar_sync = calendar_sync
        self.calendar_id = calendar_id
        self.calendar_provider = calendar_provider

        # Calculate next run date for recurring tasks
        if self.is_recurring and not self.recurrence_next_run:
            self.recurrence_next_run = self.calculate_next_recurrence()

    def update(self, data: Dict[str, Any]) -> None:
        """
        Update task with new data.

        Args:
            data: Dictionary containing fields to update
        """
        # Update basic fields
        if 'title' in data:
            self.title = data['title']
        if 'description' in data:
            self.description = data['description']
        if 'status' in data:
            self.status = data['status']
        if 'due_date' in data:
            self.due_date = data['due_date']
        if 'priority' in data:
            self.priority = data['priority']
        if 'tags' in data:
            self.tags = data['tags']
        if 'project' in data:
            self.project = data['project']

        # Update recurrence fields
        if 'is_recurring' in data:
            self.is_recurring = data['is_recurring']
        if 'recurrence_frequency' in data:
            self.recurrence_frequency = data['recurrence_frequency']
        if 'recurrence_start_date' in data:
            self.recurrence_start_date = data['recurrence_start_date']
        if 'recurrence_enabled' in data:
            self.recurrence_enabled = data['recurrence_enabled']

        # Update calendar fields
        if 'calendar_sync' in data:
            self.calendar_sync = data['calendar_sync']
        if 'calendar_id' in data:
            self.calendar_id = data['calendar_id']
        if 'calendar_provider' in data:
            self.calendar_provider = data['calendar_provider']

        # Recalculate next run date if needed
        if self.is_recurring and (
            'is_recurring' in data or
            'recurrence_frequency' in data or
            'recurrence_start_date' in data
        ):
            self.recurrence_next_run = self.calculate_next_recurrence()

        # Always update the updated_at timestamp
        self.updated_at = datetime.now().isoformat()

    def mark_completed(self) -> None:
        """
        Mark the task as completed.
        If the task is recurring, schedule the next occurrence.
        """
        self.status = self.STATUS_COMPLETED
        self.updated_at = datetime.now().isoformat()

        if self.is_recurring and self.recurrence_enabled:
            self.recurrence_next_run = self.calculate_next_recurrence()
            # Reset status for the next occurrence
            self.status = self.STATUS_PENDING

    def calculate_next_recurrence(self) -> Optional[str]:
        """
        Calculate the next occurrence date for a recurring task.

        Returns:
            ISO format date string of the next occurrence or None if not recurring
        """
        if not self.is_recurring or not self.recurrence_frequency:
            return None

        # Parse the start date
        start_date = self.due_date or self.recurrence_start_date or datetime.now().isoformat()

        try:
            base_date = datetime.fromisoformat(start_date)
        except ValueError:
            # Handle date format issue, default to now
            base_date = datetime.now()

        # Calculate next date based on frequency
        if self.recurrence_frequency == self.FREQUENCY_DAILY:
            next_date = base_date + timedelta(days=1)
        elif self.recurrence_frequency == self.FREQUENCY_WEEKLY:
            next_date = base_date + timedelta(weeks=1)
        elif self.recurrence_frequency == self.FREQUENCY_MONTHLY:
            # Add a month (handle different month lengths)
            if base_date.month == 12:
                next_date = base_date.replace(year=base_date.year + 1, month=1)
            else:
                # Handle month length differences (e.g., Jan 31 -> Feb 28)
                try:
                    next_date = base_date.replace(month=base_date.month + 1)
                except ValueError:
                    # Handle case for months with fewer days
                    next_month = base_date.month + 1
                    last_day = self._get_last_day_of_month(
                        base_date.year, next_month)
                    next_date = base_date.replace(
                        month=next_month, day=last_day)
        else:
            # Default to daily if frequency is invalid
            next_date = base_date + timedelta(days=1)

        return next_date.isoformat()

    @staticmethod
    def _get_last_day_of_month(year: int, month: int) -> int:
        """
        Get the last day of a given month.

        Args:
            year: Year
            month: Month (1-12)

        Returns:
            Last day of the month
        """
        if month == 12:
            # Last day of December is always 31
            return 31

        # Get the first day of the next month and subtract one day
        next_month_date = dt.date(year, month + 1, 1)
        last_day = next_month_date - dt.timedelta(days=1)
        return last_day.day
