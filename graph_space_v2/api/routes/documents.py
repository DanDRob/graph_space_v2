from flask import Blueprint, request, jsonify, current_app, send_from_directory
import os
import traceback
from datetime import datetime
from werkzeug.utils import secure_filename
from graph_space_v2.api.middleware.validation import validate_id_parameter

documents_bp = Blueprint('documents', __name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'md', 'csv', 'xlsx'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@documents_bp.route('/documents', methods=['GET'])
def get_documents():
    try:
        print("GET /documents - Retrieving documents")
        graphspace = current_app.config['GRAPHSPACE']

        documents = graphspace.query_service.get_entities_by_tag('document')
        print(f"Retrieved {len(documents)} documents")

        return jsonify({'documents': documents})
    except Exception as e:
        print(f"Error getting documents: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@documents_bp.route('/documents/<doc_id>', methods=['GET'])
@validate_id_parameter
def get_document(doc_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']
        document = graphspace.query_service._get_entity('document', doc_id)

        if not document or document.get('type') != 'document':
            return jsonify({'error': 'Document not found'}), 404

        return jsonify(document)
    except Exception as e:
        print(f"Error getting document {doc_id}: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@documents_bp.route('/upload_document', methods=['POST'])
def upload_document():
    try:
        print(f"Upload request received: {request.files}")
        print(f"Upload form data: {request.form}")
        if 'file' not in request.files:
            print("No file part in the request")
            return jsonify({'error': 'No file part in the request'}), 400

        file = request.files['file']
        print(f"Received file: {file.filename}")

        if file.filename == '':
            print("No file selected")
            return jsonify({'error': 'No file selected'}), 400

        if not allowed_file(file.filename):
            print(f"File type not allowed: {file.filename}")
            return jsonify({
                'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400

        filename = secure_filename(file.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        print(f"Saving file to: {file_path}")
        print(
            f"Upload folder exists: {os.path.exists(current_app.config['UPLOAD_FOLDER'])}")
        file.save(file_path)
        print(f"File saved successfully: {os.path.exists(file_path)}")

        # Extract metadata from request form data
        metadata = {
            'title': request.form.get('title', filename),
            'description': request.form.get('description', ''),
            'tags': request.form.get('tags', '').split(',') if request.form.get('tags') else [],
            'category': request.form.get('category', 'uncategorized'),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }

        print(f"Processing document with metadata: {metadata}")

        # Process document through document processor pipeline
        graphspace = current_app.config['GRAPHSPACE']
        result = graphspace.process_document(file_path, metadata=metadata)

        print(f"Document processed: {result}")

        # Check if processing was successful
        if result.get('error'):
            print(f"Error processing document: {result['error']}")
            return jsonify({'error': result['error']}), 500

        # Use the filename as the document ID
        doc_id = os.path.basename(file_path)

        return jsonify({
            'success': True,
            'document_id': doc_id,
            'filename': filename
        })

    except Exception as e:
        print(f"Error uploading document: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@documents_bp.route('/documents/<doc_id>/download', methods=['GET'])
@validate_id_parameter
def download_document(doc_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']
        document = graphspace.query_service._get_entity('document', doc_id)

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
        print(f"Error downloading document {doc_id}: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@documents_bp.route('/documents/<doc_id>', methods=['DELETE'])
@validate_id_parameter
def delete_document(doc_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']

        # Get document data
        document = graphspace.query_service._get_entity('document', doc_id)

        if not document or document.get('type') != 'document':
            return jsonify({'error': 'Document not found'}), 404

        # Get file path to delete the file as well
        file_path = document.get('file_path', '')

        # Remove document from knowledge graph
        graphspace.knowledge_graph.remove_all_relationships(doc_id)
        success = graphspace.knowledge_graph.delete_node(doc_id)

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
        print(f"Error deleting document {doc_id}: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
