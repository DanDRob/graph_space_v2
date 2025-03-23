from typing import Dict, List, Any, Optional, Tuple
import datetime

from graph_space_v2.integrations.calendar.calendar_service import CalendarService, CalendarEvent
from graph_space_v2.core.services.task_service import TaskService
from graph_space_v2.core.models.task import Task


class TaskCalendarSync:
    def __init__(
        self,
        task_service: TaskService,
        calendar_service: CalendarService
    ):
        self.task_service = task_service
        self.calendar_service = calendar_service

    def sync_task_to_calendar(
        self,
        task: Task,
        provider_id: str,
        calendar_id: str,
        create_if_missing: bool = True
    ) -> Optional[Task]:
        """
        Sync a task to a calendar event.

        Args:
            task: Task to sync
            provider_id: Calendar provider ID
            calendar_id: Calendar ID
            create_if_missing: Whether to create a new event if not found

        Returns:
            Updated task or None if sync failed
        """
        # Check if task is already linked to a calendar event
        if task.calendar_id and task.calendar_provider == provider_id:
            # Update existing event
            try:
                # Convert task to calendar event
                event = self._task_to_event(task, calendar_id)

                # Update the event
                provider = self.calendar_service.get_provider(provider_id)
                updated_event = provider.update_event(calendar_id, event)

                # Update task with event info
                task.calendar_id = updated_event.id
                task.calendar_provider = provider_id
                task.calendar_sync = True

                # Save task
                self.task_service.update_task(task.id, task.to_dict())

                return task
            except Exception as e:
                print(f"Error updating calendar event for task {task.id}: {e}")

                # If event not found, clear the calendar link
                task.calendar_id = ""
                task.calendar_sync = False
                self.task_service.update_task(task.id, task.to_dict())

                # Try to create a new event if requested
                if create_if_missing:
                    return self._create_event_for_task(task, provider_id, calendar_id)

                return None
        elif create_if_missing:
            # Create new event
            return self._create_event_for_task(task, provider_id, calendar_id)

        return None

    def _create_event_for_task(
        self,
        task: Task,
        provider_id: str,
        calendar_id: str
    ) -> Optional[Task]:
        """Create a calendar event for a task"""
        try:
            # Get due date as datetime (or use now + 1 day if not set)
            if task.due_date:
                try:
                    due_date = datetime.datetime.fromisoformat(
                        task.due_date.replace("Z", "+00:00"))
                except ValueError:
                    due_date = datetime.datetime.now() + datetime.timedelta(days=1)
            else:
                due_date = datetime.datetime.now() + datetime.timedelta(days=1)

            # Create event with 1-hour duration by default
            start_time = due_date.replace(
                hour=9, minute=0, second=0, microsecond=0)
            end_time = start_time + datetime.timedelta(hours=1)

            # Create event
            event = self.calendar_service.create_event(
                provider_id=provider_id,
                calendar_id=calendar_id,
                title=f"Task: {task.title}",
                start_time=start_time,
                end_time=end_time,
                description=task.description,
                is_all_day=False
            )

            # Update task with event info
            task.calendar_id = event.id
            task.calendar_provider = provider_id
            task.calendar_sync = True
            self.task_service.update_task(task.id, task.to_dict())

            return task
        except Exception as e:
            print(f"Error creating calendar event for task {task.id}: {e}")
            return None

    def _task_to_event(self, task: Task, calendar_id: str) -> CalendarEvent:
        """Convert a task to a calendar event"""
        # Get due date as datetime (or use now + 1 day if not set)
        if task.due_date:
            try:
                due_date = datetime.datetime.fromisoformat(
                    task.due_date.replace("Z", "+00:00"))
            except ValueError:
                due_date = datetime.datetime.now() + datetime.timedelta(days=1)
        else:
            due_date = datetime.datetime.now() + datetime.timedelta(days=1)

        # Use 1-hour duration by default
        start_time = due_date.replace(
            hour=9, minute=0, second=0, microsecond=0)
        end_time = start_time + datetime.timedelta(hours=1)

        # Create event
        return CalendarEvent(
            id=task.calendar_id,
            title=f"Task: {task.title}",
            description=task.description,
            start_time=start_time,
            end_time=end_time,
            location="",
            calendar_id=calendar_id,
            provider=task.calendar_provider,
            is_all_day=False
        )

    def sync_event_to_task(
        self,
        event: CalendarEvent,
        provider_id: str,
        create_if_missing: bool = True
    ) -> Optional[Task]:
        """
        Sync a calendar event to a task.

        Args:
            event: Calendar event to sync
            provider_id: Calendar provider ID
            create_if_missing: Whether to create a new task if not found

        Returns:
            Updated task or None if sync failed
        """
        # Look for existing task with this calendar event ID
        tasks = self.task_service.get_all_tasks()
        matching_tasks = [t for t in tasks
                          if t.calendar_id == event.id and t.calendar_provider == provider_id]

        if matching_tasks:
            # Update existing task
            task = matching_tasks[0]
            self._update_task_from_event(task, event, provider_id)
            self.task_service.update_task(task.id, task.to_dict())
            return task
        elif create_if_missing:
            # Create new task
            return self._create_task_from_event(event, provider_id)

        return None

    def _create_task_from_event(
        self,
        event: CalendarEvent,
        provider_id: str
    ) -> Optional[Task]:
        """Create a task from a calendar event"""
        try:
            # Extract title (remove "Task: " prefix if it exists)
            title = event.title
            if title.startswith("Task: "):
                title = title[6:]

            # Create task data
            task_data = {
                "title": title,
                "description": event.description,
                "status": Task.STATUS_PENDING,
                "due_date": event.start_time.isoformat(),
                "calendar_id": event.id,
                "calendar_provider": provider_id,
                "calendar_sync": True,
                "tags": ["from_calendar"]
            }

            # Create task
            task_id = self.task_service.add_task(task_data)
            return self.task_service.get_task(task_id)
        except Exception as e:
            print(f"Error creating task from event {event.id}: {e}")
            return None

    def _update_task_from_event(
        self,
        task: Task,
        event: CalendarEvent,
        provider_id: str
    ) -> None:
        """Update a task from a calendar event"""
        # Extract title (remove "Task: " prefix if it exists)
        title = event.title
        if title.startswith("Task: "):
            title = title[6:]

        # Update task fields
        task.title = title
        task.description = event.description
        task.due_date = event.start_time.isoformat()
        task.calendar_id = event.id
        task.calendar_provider = provider_id
        task.calendar_sync = True
        task.updated_at = datetime.datetime.now().isoformat()

    def batch_sync_tasks_to_calendar(
        self,
        tasks: List[Task],
        provider_id: str,
        calendar_id: str
    ) -> Tuple[int, int, List[str]]:
        """
        Sync multiple tasks to calendar events.

        Args:
            tasks: Tasks to sync
            provider_id: Calendar provider ID
            calendar_id: Calendar ID

        Returns:
            Tuple of (success count, error count, error messages)
        """
        success_count = 0
        error_count = 0
        errors = []

        for task in tasks:
            try:
                updated_task = self.sync_task_to_calendar(
                    task, provider_id, calendar_id)
                if updated_task:
                    success_count += 1
                else:
                    error_count += 1
                    errors.append(
                        f"Failed to sync task {task.id}: {task.title}")
            except Exception as e:
                error_count += 1
                errors.append(f"Error syncing task {task.id}: {str(e)}")

        return success_count, error_count, errors

    def batch_sync_events_to_tasks(
        self,
        events: List[CalendarEvent],
        provider_id: str
    ) -> Tuple[int, int, List[str]]:
        """
        Sync multiple calendar events to tasks.

        Args:
            events: Calendar events to sync
            provider_id: Calendar provider ID

        Returns:
            Tuple of (success count, error count, error messages)
        """
        success_count = 0
        error_count = 0
        errors = []

        for event in events:
            try:
                # Skip events that don't look like tasks
                if not (event.title.startswith("Task:") or
                        "task" in event.title.lower() or
                        "todo" in event.title.lower()):
                    continue

                updated_task = self.sync_event_to_task(event, provider_id)
                if updated_task:
                    success_count += 1
                else:
                    error_count += 1
                    errors.append(
                        f"Failed to sync event {event.id}: {event.title}")
            except Exception as e:
                error_count += 1
                errors.append(f"Error syncing event {event.id}: {str(e)}")

        return success_count, error_count, errors

    def get_syncable_tasks(self) -> List[Task]:
        """Get tasks that can be synced to calendar"""
        tasks = self.task_service.get_all_tasks()
        return [t for t in tasks if t.due_date and t.status != Task.STATUS_COMPLETED]

    def get_task_by_calendar_event(self, provider_id: str, event_id: str) -> Optional[Task]:
        """Find a task linked to a calendar event"""
        tasks = self.task_service.get_all_tasks()
        matching_tasks = [t for t in tasks
                          if t.calendar_id == event_id and t.calendar_provider == provider_id]

        return matching_tasks[0] if matching_tasks else None
