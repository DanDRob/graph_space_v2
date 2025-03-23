from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from graph_space_v2.api.middleware.auth import token_required
from graph_space_v2.api.middleware.validation import validate_json_request, validate_required_fields

tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('/tasks', methods=['GET'])
@token_required
def get_tasks():
    try:
        graphspace = current_app.config['GRAPHSPACE']
        tasks = graphspace.core.services.task_service.get_all_tasks()
        return jsonify({'tasks': tasks})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/tasks/<task_id>', methods=['GET'])
@token_required
def get_task(task_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']
        task = graphspace.core.services.task_service.get_task(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        return jsonify(task)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/tasks', methods=['POST'])
@token_required
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
            'calendar_provider': data.get('calendar_provider', '')
        }

        graphspace = current_app.config['GRAPHSPACE']
        task_id = graphspace.core.services.task_service.add_task(task_data)

        return jsonify({'success': True, 'task_id': task_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/tasks/<task_id>', methods=['PUT'])
@token_required
@validate_json_request
def update_task(task_id):
    try:
        data = request.json

        graphspace = current_app.config['GRAPHSPACE']
        task = graphspace.core.services.task_service.get_task(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        # Update all fields provided in the request
        task_data = task.copy()

        # List of valid fields that can be updated
        valid_fields = [
            'title', 'description', 'status', 'due_date', 'priority',
            'tags', 'project', 'is_recurring', 'recurrence_frequency',
            'recurrence_start_date', 'recurrence_enabled', 'calendar_sync',
            'calendar_id', 'calendar_provider'
        ]

        # Update fields from request data
        for field in valid_fields:
            if field in data:
                task_data[field] = data[field]

        # Mark as updated
        task_data['updated'] = datetime.now().isoformat()

        # Update in service
        success = graphspace.core.services.task_service.update_task(
            task_id, task_data)

        if not success:
            return jsonify({'error': 'Failed to update task'}), 500

        return jsonify({'success': True, 'task_id': task_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/tasks/<task_id>', methods=['DELETE'])
@token_required
def delete_task(task_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']
        success = graphspace.core.services.task_service.delete_task(task_id)

        if not success:
            return jsonify({'error': 'Task not found or could not be deleted'}), 404

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/tasks/process_recurring', methods=['POST'])
@token_required
def process_recurring_tasks():
    try:
        graphspace = current_app.config['GRAPHSPACE']
        results = graphspace.core.services.task_service.process_recurring_tasks()

        return jsonify({
            'success': True,
            'processed': results.get('processed', 0),
            'created': results.get('created', 0)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
