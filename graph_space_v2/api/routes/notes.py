from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import traceback
import uuid
import json
import os
from graph_space_v2.utils.helpers.path_utils import get_user_data_path, debug_data_file
from graph_space_v2.api.middleware.validation import validate_json_request, validate_required_fields
from graph_space_v2.utils.errors.exceptions import NoteServiceError, EntityNotFoundError, ServiceError # Added

notes_bp = Blueprint('notes', __name__)


@notes_bp.route('/notes', methods=['GET'])
def get_notes():
    # TODO: Implement pagination (e.g., using request.args for page and per_page) if the number of notes can be very large.
    try:
        current_app.logger.info("GET /notes - Retrieving all notes")
        graphspace = current_app.config['GRAPHSPACE']

        if not hasattr(graphspace, 'note_service'):
            current_app.logger.error("Note service not found on graphspace instance.")
            return jsonify({'error': 'Note service not initialized'}), 500

        notes = graphspace.note_service.get_all_notes() # This now returns list of dicts
        current_app.logger.info(f"Retrieved {len(notes)} notes.")
        return jsonify({'notes': notes}), 200
    except NoteServiceError as e:
        current_app.logger.error(f"NoteServiceError in get_notes: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception in get_notes: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while retrieving notes."}), 500


@notes_bp.route('/notes/<note_id>', methods=['GET'])
def get_note(note_id):
    try:
        current_app.logger.info(f"GET /notes/{note_id} - Retrieving note.")
        graphspace = current_app.config['GRAPHSPACE']
        note = graphspace.note_service.get_note(note_id) # Returns Note object or raises
        return jsonify(note.to_dict()), 200 # Convert Note object to dict for jsonify
    except EntityNotFoundError as e:
        current_app.logger.warning(f"EntityNotFoundError in get_note for ID {note_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 404
    except NoteServiceError as e:
        current_app.logger.error(f"NoteServiceError in get_note for ID {note_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception in get_note for ID {note_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred."}), 500


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
        current_app.logger.info(f"POST /notes - Note added successfully with ID: {note_id}")
        # Return 201 Created status code
        return jsonify({'message': 'Note added successfully', 'note_id': note_id}), 201
    except NoteServiceError as e:
        current_app.logger.error(f"NoteServiceError in add_note: {e}", exc_info=True)
        # Consider if some NoteServiceErrors could be 400 (e.g. validation within service)
        return jsonify({'error': str(e)}), 500
    except Exception as e: # Catch-all for unexpected errors
        current_app.logger.error(f"Unhandled exception in add_note: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while adding the note."}), 500


@notes_bp.route('/notes/<note_id>', methods=['PUT'])
@validate_json_request
def update_note(note_id):
    try:
    data = request.json
    current_app.logger.info(f"PUT /notes/{note_id} - Updating note with data: {data}")

    # Ensure at least one field is provided for update (basic validation)
    # More advanced validation (e.g. field types) can be done by a dedicated schema validator
    update_fields = ['title', 'content', 'tags']
    if not data or not any(field in data for field in update_fields):
        current_app.logger.warning(f"PUT /notes/{note_id} - Bad request: No update fields provided.")
        return jsonify({'error': 'No update fields provided or empty payload.'}), 400

    graphspace = current_app.config['GRAPHSPACE']
    # NoteService.update_note now expects a dict of fields to update, not the full note object.
    # It also returns the updated Note object or raises an error.
    updated_note = graphspace.note_service.update_note(note_id, data)

    current_app.logger.info(f"Note {note_id} updated successfully.")
    return jsonify(updated_note.to_dict()), 200

    # Removed the old logic of fetching, manually updating dict, then calling service.
    # The service layer should handle the logic of what can be updated.
    # If specific fields are not allowed, the service should enforce it or validation layer should.

    except EntityNotFoundError as e:
        current_app.logger.warning(f"EntityNotFoundError in update_note for ID {note_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 404
    except NoteServiceError as e: # Specific errors from the service that are not "Not Found"
        current_app.logger.error(f"NoteServiceError in update_note for ID {note_id}: {e}", exc_info=True)
        # Check if it's a validation-like error from service, could be 400
        if "validation" in str(e).lower() or "invalid input" in str(e).lower(): # Simple check
             return jsonify({'error': str(e)}), 400
        return jsonify({'error': str(e)}), 500
    except Exception as e: # Catch-all for unexpected errors
        current_app.logger.error(f"Unhandled exception in update_note for ID {note_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while updating the note."}), 500


@notes_bp.route('/notes/<note_id>', methods=['DELETE'])
def delete_note(note_id):
    try:
        current_app.logger.info(f"DELETE /notes/{note_id} - Deleting note.")
        graphspace = current_app.config['GRAPHSPACE']
        graphspace.note_service.delete_note(note_id) # Now returns True or raises error
        current_app.logger.info(f"Note {note_id} deleted successfully.")
        return jsonify({'message': 'Note deleted successfully'}), 200
    except EntityNotFoundError as e: # Assuming delete_note might raise this if KG says not found
        current_app.logger.warning(f"EntityNotFoundError in delete_note for ID {note_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 404
    except NoteServiceError as e:
        current_app.logger.error(f"NoteServiceError in delete_note for ID {note_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500 # Or 404 if the error message implies it wasn't found
    except Exception as e:
        current_app.logger.error(f"Unhandled exception in delete_note for ID {note_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while deleting the note."}), 500


@notes_bp.route('/debug/notes/create_test', methods=['GET'])
def create_test_note():
    """
    Debug endpoint to create a test note by directly manipulating the data file.
    This bypasses all the normal flows to help diagnose issues.
    """
    try:
        # Get the data file path
        data_path = get_user_data_path()
        current_app.logger.info(f"Debug: Creating test note in {data_path}")

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
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error creating test note via debug endpoint: {e}", exc_info=True)
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500
