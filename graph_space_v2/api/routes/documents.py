from flask import Blueprint, request, jsonify, current_app, send_from_directory
import os
import traceback
from datetime import datetime
from werkzeug.utils import secure_filename
from graph_space_v2.api.middleware.validation import validate_id_parameter
from graph_space_v2.utils.errors.exceptions import ServiceError, EntityNotFoundError, DocumentProcessingError, KnowledgeGraphError # Added

documents_bp = Blueprint('documents', __name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'md', 'csv', 'xlsx'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@documents_bp.route('/documents', methods=['GET'])
def get_documents():
    # TODO: Implement pagination (e.g., using request.args for page and per_page) if the number of documents can be very large.
    try:
        current_app.logger.info("GET /documents - Retrieving documents")
        graphspace = current_app.config['GRAPHSPACE']
        # Assuming query_service.get_entities_by_tag is robust or raises ServiceError
        documents = graphspace.query_service.get_entities_by_tag('document')
        current_app.logger.info(f"Retrieved {len(documents)} documents")
        return jsonify({'documents': documents}), 200
    except ServiceError as e:
        current_app.logger.error(f"ServiceError in get_documents: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception in get_documents: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while retrieving documents."}), 500


@documents_bp.route('/documents/<doc_id>', methods=['GET'])
@validate_id_parameter
def get_document(doc_id):
    try:
        current_app.logger.info(f"GET /documents/{doc_id} - Retrieving document.")
        graphspace = current_app.config['GRAPHSPACE']
        document = graphspace.query_service._get_entity('document', doc_id)

        if not document or document.get('type') != 'document':
            current_app.logger.warning(f"Document with ID {doc_id} not found.")
            return jsonify({'error': 'Document not found'}), 404

        return jsonify(document), 200
    except EntityNotFoundError as e: # If _get_entity is updated to raise this
        current_app.logger.warning(f"EntityNotFoundError for document ID {doc_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 404
    except ServiceError as e:
        current_app.logger.error(f"ServiceError retrieving document ID {doc_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception retrieving document ID {doc_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred."}), 500


@documents_bp.route('/upload_document', methods=['POST'])
def upload_document():
    # TODO: For large files or extensive processing, consider making this an asynchronous operation
    # (e.g., using a task queue like Celery) and returning a task ID to check status.
    try:
        current_app.logger.info(f"POST /upload_document - Upload request received. Files: {list(request.files.keys())}, Form: {request.form}")

        if 'file' not in request.files:
            current_app.logger.warning("Upload attempt with no file part in the request.")
            return jsonify({'error': 'No file part in the request'}), 400

        file = request.files['file']
        current_app.logger.info(f"Received file for upload: {file.filename}")

        if file.filename == '':
            current_app.logger.warning("Upload attempt with no file selected.")
            return jsonify({'error': 'No file selected'}), 400

        if not allowed_file(file.filename):
            current_app.logger.warning(f"Upload attempt with disallowed file type: {file.filename}")
            return jsonify({
                'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400

        filename = secure_filename(file.filename)
        # Ensure UPLOAD_FOLDER is configured in Flask app config
        upload_folder = current_app.config.get('UPLOAD_FOLDER', './uploads') # Default if not configured
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            current_app.logger.info(f"Created upload folder: {upload_folder}")

        file_path = os.path.join(upload_folder, filename)
        current_app.logger.info(f"Saving uploaded file to: {file_path}")
        file.save(file_path)
        current_app.logger.info(f"File saved successfully: {file_path}")

        metadata = {
            'title': request.form.get('title', filename),
            'description': request.form.get('description', ''),
            'tags': request.form.get('tags', '').split(',') if request.form.get('tags') else [],
            'category': request.form.get('category', 'uncategorized'),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }

        current_app.logger.info(f"Processing document '{filename}' with metadata: {metadata}")
        graphspace = current_app.config['GRAPHSPACE']

        # process_document might raise DocumentProcessingError or return a dict with error
        result = graphspace.process_document(file_path, metadata=metadata)
        current_app.logger.info(f"Document processing result for '{filename}': {result}")

        if isinstance(result, dict) and result.get('error'): # if process_document returns error dict
            current_app.logger.error(f"Error processing document '{filename}': {result['error']}")
            return jsonify({'error': result['error']}), 500 # Or a more specific code if known

        # Assuming result contains document_id if successful, or can be derived
        # The current process_document in GraphSpace returns a dict which might be the doc itself or processing info.
        # Let's assume the ID is returned or is part of the result.
        # If process_document adds to KG and returns ID, that's better.
        # For now, using filename as a proxy if not in result.
        processed_doc_id = result.get('id', os.path.basename(file_path))


        return jsonify({
            'message': 'Document uploaded and processed successfully.',
            'document_id': processed_doc_id, # This should be the actual ID from KG
            'filename': filename
        }), 201

    except DocumentProcessingError as e:
        current_app.logger.error(f"DocumentProcessingError during upload: {e}", exc_info=True)
        return jsonify({'error': f"Failed to process document: {str(e)}"}), 500
    except FileNotFoundError as e: # If file save fails due to path issues
        current_app.logger.error(f"FileNotFoundError during file save: {e}", exc_info=True)
        return jsonify({'error': f"Failed to save uploaded file: {str(e)}"}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception during document upload: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred during document upload."}), 500


@documents_bp.route('/documents/<doc_id>/download', methods=['GET'])
@validate_id_parameter
def download_document(doc_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']
        current_app.logger.info(f"GET /documents/{doc_id}/download - Attempting to download document.")
        graphspace = current_app.config['GRAPHSPACE']
        document = graphspace.query_service._get_entity('document', doc_id)

        if not document or document.get('type') != 'document':
            current_app.logger.warning(f"Document {doc_id} not found for download.")
            return jsonify({'error': 'Document not found'}), 404

        file_path = document.get('file_path', '')
        if not file_path: # Check if file_path is empty or None
            current_app.logger.error(f"File path not available for document {doc_id}.")
            return jsonify({'error': 'Document file path not available or accessible.'}), 404

        # Security check: Ensure file_path is within an allowed directory, e.g., app.config['UPLOAD_FOLDER']
        # This is crucial to prevent directory traversal attacks.
        # For this example, we assume file_path is absolute and correct from KG.
        # A real implementation should verify this path.
        if not os.path.isabs(file_path): # Example check, might need more robust logic
            # Assuming UPLOAD_FOLDER is where downloadable files are stored
            file_path = os.path.join(current_app.config.get('UPLOAD_FOLDER', './uploads'), os.path.basename(file_path))

        if not os.path.exists(file_path):
            current_app.logger.error(f"Document file {file_path} for doc ID {doc_id} not found on server.")
            return jsonify({'error': 'Document file not found on server.'}), 404

        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        current_app.logger.info(f"Sending file {filename} from directory {directory} for document {doc_id}.")
        return send_from_directory(directory, filename, as_attachment=True)

    except EntityNotFoundError as e: # If _get_entity is updated to raise this
        current_app.logger.warning(f"EntityNotFoundError for document ID {doc_id} during download: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 404
    except ServiceError as e:
        current_app.logger.error(f"ServiceError for document ID {doc_id} during download: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception downloading document {doc_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while downloading the document."}), 500


@documents_bp.route('/documents/<doc_id>', methods=['DELETE'])
@validate_id_parameter
def delete_document(doc_id):
    try:
        graphspace = current_app.config['GRAPHSPACE']

        current_app.logger.info(f"DELETE /documents/{doc_id} - Deleting document.")
        graphspace = current_app.config['GRAPHSPACE']

        document = graphspace.query_service._get_entity('document', doc_id)
        if not document or document.get('type') != 'document':
            current_app.logger.warning(f"Document {doc_id} not found for deletion.")
            return jsonify({'error': 'Document not found'}), 404

        file_path = document.get('file_path')

        # Remove document from knowledge graph
        # These direct KG calls should ideally be wrapped in a document service method
        graphspace.knowledge_graph.remove_all_relationships(doc_id) # Assuming this is safe and idempotent
        deleted_kg_node = graphspace.knowledge_graph.delete_node(doc_id) # Returns True/False

        if not deleted_kg_node:
            current_app.logger.error(f"Failed to delete document node {doc_id} from knowledge graph.")
            # It might be already deleted or another issue.
            # If the goal is to ensure it's gone, and it's not there, it might still be a "success" from client POV.
            # However, if delete_node returns False because it wasn't found, it's consistent with the initial check.
            return jsonify({'error': 'Failed to delete document from knowledge graph, or it was already deleted.'}), 500 # Or 404 if appropriate

        # Delete the physical file if path is known and file exists
        if file_path:
            # Security: ensure file_path is within an allowed base directory
            upload_folder = current_app.config.get('UPLOAD_FOLDER', './uploads')
            if os.path.isabs(file_path) and file_path.startswith(os.path.abspath(upload_folder)):
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        current_app.logger.info(f"Successfully deleted physical file: {file_path}")
                    except OSError as e_file: # Catch specific OS errors for file deletion
                        current_app.logger.warning(f"Could not delete physical file {file_path} for document {doc_id}: {e_file}", exc_info=True)
                        # Don't fail the whole operation if only file deletion fails, KG part was successful.
                else:
                    current_app.logger.warning(f"Physical file {file_path} for document {doc_id} not found for deletion.")
            else:
                current_app.logger.warning(f"Skipping deletion of file {file_path} as it's outside the upload folder or path is relative/invalid.")

        current_app.logger.info(f"Document {doc_id} (node) deleted successfully from knowledge graph.")
        return jsonify({'message': 'Document deleted successfully'}), 200

    except EntityNotFoundError as e: # From _get_entity
        current_app.logger.warning(f"EntityNotFoundError for document ID {doc_id} during deletion: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 404
    except (KnowledgeGraphError, ServiceError) as e: # Catch errors from KG or QueryService
        current_app.logger.error(f"Error during document deletion for ID {doc_id}: {e}", exc_info=True)
        return jsonify({'error': f"A service or graph error occurred: {str(e)}"}), 500
    except Exception as e:
        current_app.logger.error(f"Unhandled exception deleting document {doc_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while deleting the document."}), 500
