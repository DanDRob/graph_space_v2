from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from graph_space_v2.api.middleware.auth import token_required
from graph_space_v2.api.middleware.validation import validate_json_request, validate_required_fields

notes_bp = Blueprint('notes', __name__)


@notes_bp.route('/notes', methods=['GET'])
@token_required
def get_notes():
    try:
        graphspace = current_app.config['GRAPHSPACE']
        notes = graphspace.core.services.note_service.get_all_notes()
        return jsonify({'notes': notes})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@notes_bp.route('/notes/<note_id>', methods=['GET'])
@token_required
def get_note(note_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']
        note = graphspace.core.services.note_service.get_note(note_id)

        if not note:
            return jsonify({'error': 'Note not found'}), 404

        return jsonify(note)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@notes_bp.route('/notes', methods=['POST'])
@token_required
@validate_json_request
@validate_required_fields('content')
def add_note():
    try:
        data = request.json

        note_data = {
            'title': data.get('title', 'Untitled Note'),
            'content': data.get('content', ''),
            'tags': data.get('tags', []),
            'created': data.get('created', datetime.now().isoformat()),
            'updated': data.get('updated', datetime.now().isoformat())
        }

        graphspace = current_app.config['GRAPHSPACE']
        note_id = graphspace.core.services.note_service.add_note(note_data)

        return jsonify({'success': True, 'note_id': note_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@notes_bp.route('/notes/<note_id>', methods=['PUT'])
@token_required
@validate_json_request
def update_note(note_id):
    try:
        data = request.json

        # Ensure at least one field is provided for update
        update_fields = ['title', 'content', 'tags']
        if not any(field in data for field in update_fields):
            return jsonify({'error': 'No update fields provided'}), 400

        graphspace = current_app.config['GRAPHSPACE']
        note = graphspace.core.services.note_service.get_note(note_id)

        if not note:
            return jsonify({'error': 'Note not found'}), 404

        # Update note fields
        note_data = note.copy()  # Copy existing note data

        if 'title' in data:
            note_data['title'] = data['title']
        if 'content' in data:
            note_data['content'] = data['content']
        if 'tags' in data:
            note_data['tags'] = data['tags']

        note_data['updated'] = datetime.now().isoformat()

        # Update in service
        success = graphspace.core.services.note_service.update_note(
            note_id, note_data)

        if not success:
            return jsonify({'error': 'Failed to update note'}), 500

        return jsonify({'success': True, 'note_id': note_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@notes_bp.route('/notes/<note_id>', methods=['DELETE'])
@token_required
def delete_note(note_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']
        success = graphspace.core.services.note_service.delete_note(note_id)

        if not success:
            return jsonify({'error': 'Note not found or could not be deleted'}), 404

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
