from flask import Blueprint, request, jsonify, current_app, send_from_directory
import os
from werkzeug.utils import secure_filename
from graph_space_v2.api.middleware.auth import token_required
from graph_space_v2.api.middleware.validation import validate_id_parameter

documents_bp = Blueprint('documents', __name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'md', 'csv', 'xlsx'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@documents_bp.route('/documents', methods=['GET'])
@token_required
def get_documents():
    try:
        graphspace = current_app.config['GRAPHSPACE']
        documents = graphspace.core.services.query_service.get_nodes_by_type(
            'document')
        return jsonify({'documents': documents})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@documents_bp.route('/documents/<doc_id>', methods=['GET'])
@token_required
@validate_id_parameter
def get_document(doc_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']
        document = graphspace.core.services.query_service.get_node_by_id(
            doc_id)

        if not document or document.get('type') != 'document':
            return jsonify({'error': 'Document not found'}), 404

        return jsonify(document)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@documents_bp.route('/upload_document', methods=['POST'])
@token_required
def upload_document():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in the request'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not allowed_file(file.filename):
            return jsonify({
                'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400

        filename = secure_filename(file.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Extract metadata from request form data
        metadata = {
            'title': request.form.get('title', filename),
            'description': request.form.get('description', ''),
            'tags': request.form.get('tags', '').split(',') if request.form.get('tags') else [],
            'category': request.form.get('category', 'uncategorized')
        }

        # Process document through document processor pipeline
        graphspace = current_app.config['GRAPHSPACE']
        doc_id = graphspace.integrations.document.document_processor.process_document(
            file_path, metadata=metadata
        )

        return jsonify({
            'success': True,
            'document_id': doc_id,
            'filename': filename
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@documents_bp.route('/documents/<doc_id>/download', methods=['GET'])
@token_required
@validate_id_parameter
def download_document(doc_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']
        document = graphspace.core.services.query_service.get_node_by_id(
            doc_id)

        if not document or document.get('type') != 'document':
            return jsonify({'error': 'Document not found'}), 404

        # Get the file path from document data
        file_path = document.get('file_path', '')

        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'Document file not found'}), 404

        # Get directory and filename
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)

        return send_from_directory(directory, filename, as_attachment=True)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@documents_bp.route('/documents/<doc_id>', methods=['DELETE'])
@token_required
@validate_id_parameter
def delete_document(doc_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']

        # Get document data
        document = graphspace.core.services.query_service.get_node_by_id(
            doc_id)

        if not document or document.get('type') != 'document':
            return jsonify({'error': 'Document not found'}), 404

        # Get file path to delete the file as well
        file_path = document.get('file_path', '')

        # Remove document from knowledge graph
        graphspace.core.graph.relationship.remove_all_relationships(doc_id)
        success = graphspace.core.graph.node_manager.remove_node(doc_id)

        if not success:
            return jsonify({'error': 'Failed to delete document from knowledge graph'}), 500

        # Delete the file if it exists
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                # Log but don't fail if file deletion fails
                print(f"Warning: Could not delete file {file_path}: {e}")

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
