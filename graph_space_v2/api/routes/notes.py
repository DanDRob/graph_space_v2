from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import traceback
import uuid
import json
import os
from graph_space_v2.utils.helpers.path_utils import get_user_data_path, debug_data_file
from graph_space_v2.api.middleware.validation import validate_json_request, validate_required_fields

notes_bp = Blueprint('notes', __name__)


@notes_bp.route('/notes', methods=['GET'])
def get_notes():
    try:
        print("GET /notes - Retrieving notes")
        graphspace = current_app.config['GRAPHSPACE']

        # Add debugging info
        print(f"GraphSpace instance: {graphspace}")

        # Explicitly check if note_service is initialized
        if not hasattr(graphspace, 'note_service'):
            print("ERROR: note_service not found on graphspace instance")
            return jsonify({'error': 'Note service not initialized'}), 500

        # Retrieve notes with extra debugging
        try:
            print("Calling note_service.get_all_notes()")
            notes = graphspace.note_service.get_all_notes()
            print(f"Retrieved {len(notes)} notes")

            # Return raw notes as they are, already in dictionary format
            return jsonify({'notes': notes})
        except Exception as e:
            print(f"Error in note_service.get_all_notes(): {e}")
            traceback.print_exc()
            return jsonify({'error': str(e), 'details': traceback.format_exc()}), 500
    except Exception as e:
        print(f"Unhandled exception in get_notes: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e), 'details': traceback.format_exc()}), 500


@notes_bp.route('/notes/<note_id>', methods=['GET'])
def get_note(note_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']
        note = graphspace.note_service.get_note(note_id)

        if not note:
            return jsonify({'error': 'Note not found'}), 404

        return jsonify(note)
    except Exception as e:
        print(f"Error getting note {note_id}: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@notes_bp.route('/notes', methods=['POST'])
@validate_json_request
@validate_required_fields('content')
def add_note():
    try:
        data = request.json

        note_data = {
            'title': data.get('title', 'Untitled Note'),
            'content': data.get('content', ''),
            'tags': data.get('tags', []),
            'created_at': data.get('created_at', datetime.now().isoformat()),
            'updated_at': data.get('updated_at', datetime.now().isoformat())
        }

        graphspace = current_app.config['GRAPHSPACE']
        note_id = graphspace.note_service.add_note(note_data)

        return jsonify({'success': True, 'note_id': note_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@notes_bp.route('/notes/<note_id>', methods=['PUT'])
@validate_json_request
def update_note(note_id):
    try:
        data = request.json

        # Ensure at least one field is provided for update
        update_fields = ['title', 'content', 'tags']
        if not any(field in data for field in update_fields):
            return jsonify({'error': 'No update fields provided'}), 400

        graphspace = current_app.config['GRAPHSPACE']
        note = graphspace.note_service.get_note(note_id)

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

        note_data['updated_at'] = datetime.now().isoformat()

        # Update in service
        success = graphspace.note_service.update_note(
            note_id, note_data)

        if not success:
            return jsonify({'error': 'Failed to update note'}), 500

        return jsonify({'success': True, 'note_id': note_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@notes_bp.route('/notes/<note_id>', methods=['DELETE'])
def delete_note(note_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']
        success = graphspace.note_service.delete_note(note_id)

        if not success:
            return jsonify({'error': 'Note not found or could not be deleted'}), 404

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@notes_bp.route('/debug/notes/create_test', methods=['GET'])
def create_test_note():
    """
    Debug endpoint to create a test note by directly manipulating the data file.
    This bypasses all the normal flows to help diagnose issues.
    """
    try:
        # Get the data file path
        data_path = get_user_data_path()
        print(f"Debug: Creating test note in {data_path}")

        # Debug the data file and get current data
        data = debug_data_file()

        # Create a simple test note
        test_note = {
            "id": f"test-{uuid.uuid4()}",
            "title": "Test Note",
            "content": "This is a test note created directly via the debug endpoint.",
            "tags": ["test", "debug"],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        # Add the test note to the data
        if "notes" not in data:
            data["notes"] = []
        data["notes"].append(test_note)

        # Write the updated data back to the file
        with open(data_path, 'w') as f:
            json.dump(data, f, indent=2)

        return jsonify({
            "success": True,
            "message": "Test note created successfully",
            "note": test_note
        })
    except Exception as e:
        print(f"Error creating test note: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500
