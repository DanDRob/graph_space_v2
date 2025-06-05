from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import traceback
from graph_space_v2.api.middleware.validation import validate_json_request, validate_required_fields
from graph_space_v2.utils.errors.exceptions import TaskServiceError, EntityNotFoundError, ServiceError # Added

tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('/tasks', methods=['GET'])
def get_tasks():
    # TODO: Implement pagination (e.g., using request.args for page and per_page) if the number of tasks can be very large.
    try:
        current_app.logger.info("GET /tasks - Retrieving all tasks")
        graphspace = current_app.config['GRAPHSPACE']
        tasks = graphspace.task_service.get_all_tasks() # Returns list of dicts
        current_app.logger.info(f"Retrieved {len(tasks)} tasks.")
        return jsonify({'tasks': tasks}), 200
    except TaskServiceError as e:
        current_app.logger.error(f"TaskServiceError in get_tasks: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception in get_tasks: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while retrieving tasks."}), 500


@tasks_bp.route('/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    try:
        current_app.logger.info(f"GET /tasks/{task_id} - Retrieving task.")
        graphspace = current_app.config['GRAPHSPACE']
        task = graphspace.task_service.get_task(task_id) # Returns Task object or raises
        return jsonify(task.to_dict()), 200 # Convert Task object to dict
    except EntityNotFoundError as e: # TaskService.get_task raises TaskServiceError for not found
        current_app.logger.warning(f"EntityNotFoundError (treated as Task not found) in get_task for ID {task_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 404
    except TaskServiceError as e: # Covers not found and other service errors
        current_app.logger.error(f"TaskServiceError in get_task for ID {task_id}: {e}", exc_info=True)
        if "not found" in str(e).lower(): # More specific check for not found within TaskServiceError
            return jsonify({'error': str(e)}), 404
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception in get_task for ID {task_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred."}), 500


@tasks_bp.route('/tasks', methods=['POST'])
@validate_json_request
@validate_required_fields('title')
def add_task():
    try:
        data = request.json

        # Check if this is a recurring task
        is_recurring = data.get('is_recurring', False)

        if is_recurring and data.get('recurrence_frequency') not in ['daily', 'weekly', 'monthly']:
            return jsonify({'error': 'For recurring tasks, frequency must be daily, weekly, or monthly'}), 400

        # Create task data dictionary
        task_data = {
            'title': data.get('title', ''),
            'description': data.get('description', ''),
            'status': data.get('status', 'pending'),
            'due_date': data.get('due_date', ''),
            'priority': data.get('priority', 'medium'),
            'tags': data.get('tags', []),
            'project': data.get('project', ''),

            # Recurrence fields
            'is_recurring': is_recurring,
            'recurrence_frequency': data.get('recurrence_frequency', ''),
            'recurrence_start_date': data.get('recurrence_start_date', datetime.now().isoformat()),
            'recurrence_enabled': True,

            # Calendar integration
            'calendar_sync': data.get('calendar_sync', False),
            'calendar_id': data.get('calendar_id', ''),
            'calendar_provider': data.get('calendar_provider', ''),

            # Timestamps
            'created_at': data.get('created_at', datetime.now().isoformat()),
            'updated_at': data.get('updated_at', datetime.now().isoformat())
        }

        graphspace = current_app.config['GRAPHSPACE']
        task_id = graphspace.task_service.add_task(task_data)
        current_app.logger.info(f"POST /tasks - Task added successfully with ID: {task_id}")
        return jsonify({'message': 'Task added successfully', 'task_id': task_id}), 201
    except TaskServiceError as e:
        current_app.logger.error(f"TaskServiceError in add_task: {e}", exc_info=True)
        # Check if it's a validation-like error from service
        if "validation" in str(e).lower() or "invalid input" in str(e).lower():
             return jsonify({'error': str(e)}), 400
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception in add_task: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while adding the task."}), 500


@tasks_bp.route('/tasks/<task_id>', methods=['PUT'])
@validate_json_request
def update_task(task_id):
    data = request.json
    current_app.logger.info(f"PUT /tasks/{task_id} - Updating task with data: {data}")

    if not data: # Check for empty payload
        current_app.logger.warning(f"PUT /tasks/{task_id} - Bad request: Empty payload.")
        return jsonify({'error': 'Request payload cannot be empty.'}), 400

    graphspace = current_app.config['GRAPHSPACE']
    # TaskService.update_task expects a dict of fields to update and returns the updated Task object
    updated_task = graphspace.task_service.update_task(task_id, data)

    current_app.logger.info(f"Task {task_id} updated successfully.")
    return jsonify(updated_task.to_dict()), 200

    except EntityNotFoundError as e: # TaskService.update_task raises TaskServiceError for not found
        current_app.logger.warning(f"EntityNotFoundError (treated as Task not found) in update_task for ID {task_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 404
    except TaskServiceError as e:
        current_app.logger.error(f"TaskServiceError in update_task for ID {task_id}: {e}", exc_info=True)
        if "not found" in str(e).lower():
            return jsonify({'error': str(e)}), 404
        if "validation" in str(e).lower() or "invalid input" in str(e).lower():
             return jsonify({'error': str(e)}), 400
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception in update_task for ID {task_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while updating the task."}), 500


@tasks_bp.route('/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    try:
        current_app.logger.info(f"DELETE /tasks/{task_id} - Deleting task.")
        graphspace = current_app.config['GRAPHSPACE']
        graphspace.task_service.delete_task(task_id) # Returns True or raises
        current_app.logger.info(f"Task {task_id} deleted successfully.")
        return jsonify({'message': 'Task deleted successfully'}), 200
    except EntityNotFoundError as e: # TaskService.delete_task raises TaskServiceError for not found
        current_app.logger.warning(f"EntityNotFoundError (treated as Task not found) in delete_task for ID {task_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 404
    except TaskServiceError as e:
        current_app.logger.error(f"TaskServiceError in delete_task for ID {task_id}: {e}", exc_info=True)
        if "not found" in str(e).lower():
            return jsonify({'error': str(e)}), 404
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception in delete_task for ID {task_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while deleting the task."}), 500


@tasks_bp.route('/tasks/process_recurring', methods=['POST'])
def process_recurring_tasks():
    try:
        current_app.logger.info("POST /tasks/process_recurring - Processing recurring tasks.")
        graphspace = current_app.config['GRAPHSPACE']
        # Assuming process_recurring_tasks returns a list of newly created Task objects
        newly_created_tasks = graphspace.task_service.process_recurring_tasks()

        response_data = {
            'message': 'Recurring tasks processed successfully.',
            'created_tasks_count': len(newly_created_tasks),
            'created_tasks': [task.to_dict() for task in newly_created_tasks]
        }
        current_app.logger.info(f"Processed recurring tasks, created {len(newly_created_tasks)} new tasks.")
        return jsonify(response_data), 200
    except TaskServiceError as e:
        current_app.logger.error(f"TaskServiceError in process_recurring_tasks: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception in process_recurring_tasks: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while processing recurring tasks."}), 500
