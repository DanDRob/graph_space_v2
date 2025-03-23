from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from graph_space_v2.api.middleware.auth import token_required
from graph_space_v2.api.middleware.validation import validate_json_request, validate_required_fields
import traceback

contacts_bp = Blueprint('contacts', __name__)


@contacts_bp.route('/contacts', methods=['GET'])
@token_required
def get_contacts():
    try:
        print("GET /contacts - Retrieving contacts")
        graphspace = current_app.config['GRAPHSPACE']

        # Get contacts directly from the query service
        contacts = graphspace.query_service.get_contacts()
        print(f"Retrieved {len(contacts)} contacts")

        return jsonify({'contacts': contacts})
    except Exception as e:
        print(f"Error getting contacts: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/contacts/<contact_id>', methods=['GET'])
@token_required
def get_contact(contact_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']
        contact = graphspace.query_service._get_entity('contact', contact_id)

        if not contact or contact.get('type') != 'contact':
            return jsonify({'error': 'Contact not found'}), 404

        return jsonify(contact)
    except Exception as e:
        print(f"Error getting contact {contact_id}: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


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
                    graphspace.knowledge_graph.add_relationship(
                        node_id,
                        rel['target_id'],
                        rel['relationship_type'],
                        rel.get('properties', {})
                    )

        return jsonify({'success': True, 'contact_id': node_id})
    except Exception as e:
        print(f"Error creating contact: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


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
                graphspace.knowledge_graph.remove_all_relationships(
                    contact_id)

            # Add new relationships
            for rel in data['relationships']:
                if all(k in rel for k in ['target_id', 'relationship_type']):
                    graphspace.knowledge_graph.add_relationship(
                        contact_id,
                        rel['target_id'],
                        rel['relationship_type'],
                        rel.get('properties', {})
                    )

        return jsonify({'success': True, 'contact_id': contact_id})
    except Exception as e:
        print(f"Error updating contact {contact_id}: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/contacts/<contact_id>', methods=['DELETE'])
@token_required
def delete_contact(contact_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']

        # First check if the contact exists
        contact = graphspace.query_service._get_entity('contact', contact_id)
        if not contact or contact.get('type') != 'contact':
            return jsonify({'error': 'Contact not found'}), 404

        # Remove all relationships for this contact
        graphspace.knowledge_graph.remove_all_relationships(contact_id)

        # Delete the contact node
        success = graphspace.knowledge_graph.delete_node(contact_id)

        if not success:
            return jsonify({'error': 'Contact could not be deleted'}), 500

        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting contact {contact_id}: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
