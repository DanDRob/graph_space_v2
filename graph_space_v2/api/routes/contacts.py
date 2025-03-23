from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from graph_space_v2.api.middleware.auth import token_required
from graph_space_v2.api.middleware.validation import validate_json_request, validate_required_fields

contacts_bp = Blueprint('contacts', __name__)


@contacts_bp.route('/contacts', methods=['GET'])
@token_required
def get_contacts():
    try:
        graphspace = current_app.config['GRAPHSPACE']
        contacts = graphspace.core.services.query_service.get_nodes_by_type(
            'contact')
        return jsonify({'contacts': contacts})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/contacts/<contact_id>', methods=['GET'])
@token_required
def get_contact(contact_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']
        contact = graphspace.core.services.query_service.get_node_by_id(
            contact_id)

        if not contact or contact.get('type') != 'contact':
            return jsonify({'error': 'Contact not found'}), 404

        return jsonify(contact)
    except Exception as e:
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
            'created': datetime.now().isoformat(),
            'updated': datetime.now().isoformat(),
            'type': 'contact'
        }

        graphspace = current_app.config['GRAPHSPACE']
        node_id = graphspace.core.graph.node_manager.add_node(contact_data)

        # Add relationships if specified
        if 'relationships' in data and isinstance(data['relationships'], list):
            for rel in data['relationships']:
                if all(k in rel for k in ['target_id', 'relationship_type']):
                    graphspace.core.graph.relationship.add_relationship(
                        node_id,
                        rel['target_id'],
                        rel['relationship_type'],
                        rel.get('properties', {})
                    )

        return jsonify({'success': True, 'contact_id': node_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/contacts/<contact_id>', methods=['PUT'])
@token_required
@validate_json_request
def update_contact(contact_id):
    try:
        data = request.json

        graphspace = current_app.config['GRAPHSPACE']
        contact = graphspace.core.services.query_service.get_node_by_id(
            contact_id)

        if not contact or contact.get('type') != 'contact':
            return jsonify({'error': 'Contact not found'}), 404

        # Update fields
        valid_fields = [
            'name', 'email', 'phone', 'organization', 'role', 'tags', 'notes'
        ]

        updates = {field: data[field]
                   for field in valid_fields if field in data}
        updates['updated'] = datetime.now().isoformat()

        success = graphspace.core.graph.node_manager.update_node(
            contact_id, updates)

        if not success:
            return jsonify({'error': 'Failed to update contact'}), 500

        # Handle relationship updates
        if 'relationships' in data and isinstance(data['relationships'], list):
            # First remove existing relationships if specified
            if data.get('replace_relationships', False):
                graphspace.core.graph.relationship.remove_all_relationships(
                    contact_id)

            # Add new relationships
            for rel in data['relationships']:
                if all(k in rel for k in ['target_id', 'relationship_type']):
                    graphspace.core.graph.relationship.add_relationship(
                        contact_id,
                        rel['target_id'],
                        rel['relationship_type'],
                        rel.get('properties', {})
                    )

        return jsonify({'success': True, 'contact_id': contact_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/contacts/<contact_id>', methods=['DELETE'])
@token_required
def delete_contact(contact_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']

        # First check if contact exists
        contact = graphspace.core.services.query_service.get_node_by_id(
            contact_id)

        if not contact or contact.get('type') != 'contact':
            return jsonify({'error': 'Contact not found'}), 404

        # Remove all relationships first
        graphspace.core.graph.relationship.remove_all_relationships(contact_id)

        # Then remove the node
        success = graphspace.core.graph.node_manager.remove_node(contact_id)

        if not success:
            return jsonify({'error': 'Failed to delete contact'}), 500

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
