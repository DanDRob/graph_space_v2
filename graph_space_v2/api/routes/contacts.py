from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from graph_space_v2.api.middleware.auth import token_required
from graph_space_v2.api.middleware.validation import validate_json_request, validate_required_fields
import traceback
from graph_space_v2.utils.errors.exceptions import ServiceError, EntityNotFoundError, KnowledgeGraphError # Added

contacts_bp = Blueprint('contacts', __name__)


@contacts_bp.route('/contacts', methods=['GET'])
@token_required
def get_contacts():
    # TODO: Implement pagination (e.g., using request.args for page and per_page) if the number of contacts can be very large.
    try:
        current_app.logger.info("GET /contacts - Retrieving contacts")
        graphspace = current_app.config['GRAPHSPACE']
        contacts = graphspace.query_service.get_contacts()
        current_app.logger.info(f"Retrieved {len(contacts)} contacts")
        return jsonify({'contacts': contacts}), 200
    except ServiceError as e: # Assuming query_service.get_contacts might raise ServiceError
        current_app.logger.error(f"ServiceError in get_contacts: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception in get_contacts: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while retrieving contacts."}), 500


@contacts_bp.route('/contacts/<contact_id>', methods=['GET'])
@token_required
def get_contact(contact_id):
    try:
        current_app.logger.info(f"GET /contacts/{contact_id} - Retrieving contact.")
        graphspace = current_app.config['GRAPHSPACE']
        # _get_entity might return None or raise if it's part of QueryService that's refactored
        # For now, assuming it returns None if not found based on current structure
        contact = graphspace.query_service._get_entity('contact', contact_id)

        if not contact or contact.get('type') != 'contact':
            current_app.logger.warning(f"Contact with ID {contact_id} not found.")
            return jsonify({'error': 'Contact not found'}), 404

        return jsonify(contact), 200
    except EntityNotFoundError as e: # If _get_entity is changed to raise this
        current_app.logger.warning(f"EntityNotFoundError in get_contact for ID {contact_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 404
    except ServiceError as e: # If query_service raises a general service error
        current_app.logger.error(f"ServiceError in get_contact for ID {contact_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception in get_contact for ID {contact_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred."}), 500


@contacts_bp.route('/contacts', methods=['POST'])
@token_required
@validate_json_request
@validate_required_fields('name')
def add_contact():
    try:
        data = request.json

        contact_data = {
            'name': data.get('name', ''),
            'email': data.get('email', ''),
            'phone': data.get('phone', ''),
            'organization': data.get('organization', ''),
            'role': data.get('role', ''),
            'tags': data.get('tags', []),
            'notes': data.get('notes', ''),
            'created_at': data.get('created_at', datetime.now().isoformat()),
            'updated_at': data.get('updated_at', datetime.now().isoformat()),
            'type': 'contact'
        }

        graphspace = current_app.config['GRAPHSPACE']
        node_id = graphspace.knowledge_graph.add_contact(contact_data)

        # Add relationships if specified
        if 'relationships' in data and isinstance(data['relationships'], list):
            for rel in data['relationships']:
                if all(k in rel for k in ['target_id', 'relationship_type']):
                    # This direct KG call might need its own error handling if add_relationship can fail
                    try:
                        graphspace.knowledge_graph.add_relationship(
                            node_id,
                            rel['target_id'],
                            rel['relationship_type'],
                            rel.get('properties', {})
                        )
                    except KnowledgeGraphError as kge:
                        current_app.logger.error(f"Failed to add relationship for contact {node_id} during creation: {kge}", exc_info=True)
                        # Decide if this should make the whole POST fail or just be a partial success
                        # For now, let's assume it should be transactional or at least report issue.
                        # This error won't be caught by the outer try-except for KnowledgeGraphError unless re-raised or outer catches it.
                        # For simplicity, a high-level error will be caught by the outer block.

        current_app.logger.info(f"POST /contacts - Contact added successfully with ID: {node_id}")
        return jsonify({'message': 'Contact added successfully', 'contact_id': node_id}), 201
    except KnowledgeGraphError as e: # Catch errors from direct KG calls if they raise this
        current_app.logger.error(f"KnowledgeGraphError in add_contact: {e}", exc_info=True)
        return jsonify({'error': f"A knowledge graph error occurred: {str(e)}"}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception in add_contact: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while adding the contact."}), 500


@contacts_bp.route('/contacts/<contact_id>', methods=['PUT'])
@token_required
@validate_json_request
def update_contact(contact_id):
    try:
        data = request.json

        graphspace = current_app.config['GRAPHSPACE']
        contact = graphspace.query_service._get_entity('contact', contact_id)

        if not contact or contact.get('type') != 'contact':
            return jsonify({'error': 'Contact not found'}), 404

        # Update fields
        valid_fields = [
            'name', 'email', 'phone', 'organization', 'role', 'tags', 'notes'
        ]

        updates = {field: data[field]
                   for field in valid_fields if field in data}
        updates['updated_at'] = datetime.now().isoformat()

        success = graphspace.knowledge_graph.update_node(
            contact_id, updates)

        if not success:
            return jsonify({'error': 'Failed to update contact'}), 500

        # Handle relationship updates
        if 'relationships' in data and isinstance(data['relationships'], list):
            # First remove existing relationships if specified
            if data.get('replace_relationships', False):
                try:
                    graphspace.knowledge_graph.remove_all_relationships(contact_id)
                except KnowledgeGraphError as kge:
                     current_app.logger.error(f"Failed to remove all relationships for contact {contact_id} during update: {kge}", exc_info=True)
                     # Potentially return error or just log and continue

            # Add new relationships
            for rel in data['relationships']:
                if all(k in rel for k in ['target_id', 'relationship_type']):
                    try:
                        graphspace.knowledge_graph.add_relationship(
                            contact_id,
                            rel['target_id'],
                            rel['relationship_type'],
                            rel.get('properties', {})
                        )
                    except KnowledgeGraphError as kge:
                        current_app.logger.error(f"Failed to add relationship for contact {contact_id} during update: {kge}", exc_info=True)
                        # Potentially return error or just log and continue

        current_app.logger.info(f"Contact {contact_id} updated successfully.")
        # Fetch the updated contact to return it
        updated_contact_data = graphspace.query_service._get_entity('contact', contact_id)
        if not updated_contact_data: # Should exist after successful update
             return jsonify({'message': 'Contact updated, but failed to retrieve updated version.'}), 200 # Or 500

        return jsonify(updated_contact_data), 200
    except EntityNotFoundError as e: # From query_service._get_entity if used for initial check
        current_app.logger.warning(f"EntityNotFoundError in update_contact for ID {contact_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 404
    except KnowledgeGraphError as e:
        current_app.logger.error(f"KnowledgeGraphError in update_contact for ID {contact_id}: {e}", exc_info=True)
        return jsonify({'error': f"A knowledge graph error occurred: {str(e)}"}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception in update_contact for ID {contact_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while updating the contact."}), 500


@contacts_bp.route('/contacts/<contact_id>', methods=['DELETE'])
@token_required
def delete_contact(contact_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']

        # First check if the contact exists using query_service
        # (assuming _get_entity is robust or raises EntityNotFoundError)
        contact_check = graphspace.query_service._get_entity('contact', contact_id)
        if not contact_check or contact_check.get('type') != 'contact':
            current_app.logger.warning(f"DELETE /contacts/{contact_id} - Contact not found for deletion check.")
            return jsonify({'error': 'Contact not found'}), 404

        # Remove all relationships for this contact
        removed_rels = graphspace.knowledge_graph.remove_all_relationships(contact_id)
        if not removed_rels: # If remove_all_relationships can return False on failure
            current_app.logger.warning(f"Failed to remove all relationships for contact {contact_id}, but proceeding with deletion.")
            # This might not be a critical failure for the delete operation itself.

        # Delete the contact node
        deleted_node = graphspace.knowledge_graph.delete_node(contact_id)
        if not deleted_node: # If delete_node can return False
            # This implies the node was not found by delete_node, even though initial check passed.
            # Or some other KG error.
            current_app.logger.error(f"KnowledgeGraph.delete_node failed for contact {contact_id}, though initial check passed.")
            # It's possible EntityNotFoundError should be raised by delete_node if not found.
            return jsonify({'error': 'Contact could not be deleted from knowledge graph, or was already deleted.'}), 404 # Or 500

        current_app.logger.info(f"Contact {contact_id} and its relationships deleted successfully.")
        return jsonify({'message': 'Contact deleted successfully'}), 200
    except EntityNotFoundError as e: # If query_service._get_entity or KG methods raise this
        current_app.logger.warning(f"EntityNotFoundError in delete_contact for ID {contact_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 404
    except KnowledgeGraphError as e:
        current_app.logger.error(f"KnowledgeGraphError in delete_contact for ID {contact_id}: {e}", exc_info=True)
        return jsonify({'error': f"A knowledge graph error occurred: {str(e)}"}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception in delete_contact for ID {contact_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while deleting the contact."}), 500
