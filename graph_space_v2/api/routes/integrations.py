from flask import Blueprint, request, jsonify, current_app, redirect, session, url_for
import os
from datetime import datetime, timedelta
import threading
import json
import logging # Added

from graph_space_v2.integrations.google.web_auth import GoogleWebAuth
from graph_space_v2.integrations.google.drive_service import GoogleDriveService
from graph_space_v2.integrations.calendar.providers.google_calendar import GoogleCalendarProvider
from graph_space_v2.integrations.calendar.calendar_service import CalendarService
from graph_space_v2.utils.errors.exceptions import IntegrationError, APIError, EntityNotFoundError, ServiceError, TaskServiceError # Added relevant exceptions

integrations_bp = Blueprint('integrations', __name__)
logger = logging.getLogger(__name__) # Added logger instance

# Initialize Google Web Auth


@integrations_bp.before_request
def initialize_google_auth():
    if 'google_auth' not in session:
        session['google_auth'] = {}

# Helper function to get GoogleWebAuth instance


def get_google_web_auth():
    # Get Google credentials from environment variables
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    client_type = os.environ.get('GOOGLE_CLIENT_TYPE', 'web')

    if not client_id or not client_secret:
        raise IntegrationError('Google API credentials not configured')

    return GoogleWebAuth(
        client_id=client_id,
        client_secret=client_secret,
        client_type=client_type
    )

# Google Auth Routes


@integrations_bp.route('/integrations/google/auth/status', methods=['GET'])
def google_auth_status():
    """Check if user is authenticated with Google"""
    user_id = session.get('user_id', 'default')

    try:
        # Get GoogleWebAuth instance
        google_auth = get_google_web_auth()

        # Check if user has valid credentials
        creds = google_auth.get_credentials(user_id)

        return jsonify({
            'authenticated': creds is not None and not (hasattr(creds, 'expired') and creds.expired)
        }), 200
    except IntegrationError as e:
        logger.error(f"IntegrationError in google_auth_status: {e}", exc_info=True)
        return jsonify({'authenticated': False, 'error': str(e)}), 502 # Bad Gateway or Service Unavailable for integration issues
    except Exception as e:
        logger.error(f"Unhandled exception in google_auth_status: {e}", exc_info=True)
        return jsonify({'authenticated': False, 'error': "An unexpected error occurred."}), 500


@integrations_bp.route('/integrations/google/auth/start', methods=['GET'])
def google_auth_start():
    """Start Google OAuth flow using the local server approach"""
    user_id = session.get('user_id', 'default')

    def run_auth_in_thread():
        try:
            # Get GoogleWebAuth instance
            google_auth = get_google_web_auth()

            # This will open a browser and run a local server for auth
            creds = google_auth.authenticate(user_id=user_id)
            if creds:
                logger.info(f"Google authentication successful in thread for user {user_id}")
            else:
                logger.warning(f"Google authentication in thread for user {user_id} did not return credentials.")
        except Exception as e_thread:
            logger.error(f"Error during Google authentication thread for user {user_id}: {e_thread}", exc_info=True)

    # Start authentication in a separate thread to not block the response
    try:
        auth_thread = threading.Thread(target=run_auth_in_thread)
        auth_thread.start()
        logger.info(f"Google authentication thread started for user {user_id}.")
        return jsonify({
            'message': 'Authentication process started. Please complete the steps in your browser or console.'
        }), 202 # Accepted
    except Exception as e:
        logger.error(f"Failed to start Google authentication thread for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': "Failed to start authentication process."}), 500


@integrations_bp.route('/integrations/google/auth/logout', methods=['POST'])
def google_auth_logout():
    """Revoke Google OAuth token"""
    user_id = session.get('user_id', 'default')

    try:
        # Get GoogleWebAuth instance
        google_auth = get_google_web_auth()

        # Revoke token
        revoked = google_auth.revoke_token(user_id)
        logger.info(f"Google token revocation attempt for user {user_id}, result: {revoked}")
        return jsonify({'success': revoked}), 200
    except IntegrationError as e:
        logger.error(f"IntegrationError in google_auth_logout for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 502
    except Exception as e:
        logger.error(f"Unhandled exception in google_auth_logout for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred during logout."}), 500

# Google Drive Routes


@integrations_bp.route('/integrations/google/drive/files', methods=['GET'])
def google_drive_files():
    """List files from Google Drive"""
    user_id = session.get('user_id', 'default')

    # Get optional query parameters
    folder_id = request.args.get('folder_id')
    query = request.args.get('query')
    mime_types = request.args.getlist('mime_type')
    max_results = int(request.args.get('max_results', 500))
    order_by = request.args.get('order_by', 'modifiedTime desc')

    try:
        # Get GoogleWebAuth instance
        google_auth = get_google_web_auth()

        # Get credentials
        creds = google_auth.get_credentials(user_id)
        if not creds:
            return jsonify({'error': 'Not authenticated with Google Drive'}), 401

        # Get GraphSpace instance
        graphspace = current_app.config['GRAPHSPACE']

        # Get drive service or create a new one if GraphSpace doesn't have one
        if graphspace.use_google_drive:
            drive_service = graphspace.google_drive_service

            # If not authenticated, set credentials
            if not drive_service.authenticated:
                drive_service.set_credentials(creds)
        else:
            # Create a standalone drive service
            drive_service = GoogleDriveService(
                document_processor=graphspace.document_processor
            )
            drive_service.set_credentials(creds)

        # List files
        files = drive_service.list_files(
            folder_id=folder_id,
            mime_types=mime_types if mime_types else None,
            query=query,
            max_results=max_results,
            order_by=order_by
        )
        logger.info(f"Retrieved {len(files)} files from Google Drive for user {user_id}.")
        return jsonify({'files': files}), 200
    except IntegrationError as e: # Covers auth issues from get_credentials or drive_service issues
        logger.error(f"IntegrationError listing Google Drive files for user {user_id}: {e}", exc_info=True)
        if "Not authenticated" in str(e):
            return jsonify({'error': str(e)}), 401
        return jsonify({'error': str(e)}), 502
    except Exception as e: # General errors
        logger.error(f"Unhandled exception listing Google Drive files for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while listing Google Drive files."}), 500


@integrations_bp.route('/integrations/google/drive/download/<file_id>', methods=['GET'])
def google_drive_download(file_id):
    """Download a file from Google Drive and process it"""
    user_id = session.get('user_id', 'default')

    try:
        # Get GoogleWebAuth instance
        google_auth = get_google_web_auth()

        # Get credentials
        creds = google_auth.get_credentials(user_id)
        if not creds:
            return jsonify({'error': 'Not authenticated with Google Drive', 'success': False}), 401

        # Get GraphSpace instance
        graphspace = current_app.config['GRAPHSPACE']
        if not graphspace:
            return jsonify({'error': 'GraphSpace instance not found', 'success': False}), 500

        # Get drive service or create a new one if GraphSpace doesn't have one
        try:
            if graphspace.use_google_drive:
                drive_service = graphspace.google_drive_service

                # If not authenticated, set credentials
                if not drive_service.authenticated:
                    drive_service.set_credentials(creds)
            else:
                # Create a standalone drive service
                drive_service = GoogleDriveService(
                    document_processor=graphspace.document_processor
                )
                drive_service.set_credentials(creds)
        except IntegrationError as ie: # Catch specific init error from drive_service if it raises one
             logger.error(f"Failed to initialize Google Drive service for user {user_id} during download: {ie}", exc_info=True)
             return jsonify({'error': f'Failed to initialize Google Drive service: {str(ie)}', 'success': False}), 502
        except Exception as e_init_drive:
            logger.error(f"Error initializing drive service for user {user_id} during download: {e_init_drive}", exc_info=True)
            return jsonify({'error': f'Failed to initialize Google Drive service: {str(e_init_drive)}', 'success': False}), 500

        if not drive_service.authenticated: # Should be handled if set_credentials failed
            logger.warning(f"Google Drive service not authenticated for user {user_id} during download.")
            return jsonify({'error': 'Google Drive service not authenticated', 'success': False}), 401

        # Get file metadata
        file_metadata = drive_service.service.files().get( # This call might raise Google API errors
            fileId=file_id, fields="name,mimeType").execute()
        logger.info(f"Retrieved metadata for file: {file_metadata.get('name')} for user {user_id}")

        # Import document directly
        # This involves downloading, processing, and adding to KG. Can raise various errors.
        document_id = drive_service.import_document(file_id)
        logger.info(f"Successfully imported document with ID: {document_id} for user {user_id}")

        return jsonify({
            'message': 'Document downloaded and processed successfully.',
            'document_id': document_id,
            'filename': file_metadata.get('name')
        }), 200 # Or 201 if a new resource (document node) is reliably created here

    except IntegrationError as e_auth: # Covers auth issues from get_credentials
        logger.warning(f"Google Drive authentication/authorization error for user {user_id} during download: {e_auth}", exc_info=True)
        return jsonify({'error': str(e_auth), 'success': False}), 401
    except APIError as e_api: # If drive_service methods raise APIError for Google API issues
        logger.error(f"Google APIError during download for file {file_id}, user {user_id}: {e_api}", exc_info=True)
        return jsonify({'error': f'Google API error: {str(e_api)}', 'success': False}), 502
    except DocumentProcessingError as e_doc:
        logger.error(f"DocumentProcessingError during download for file {file_id}, user {user_id}: {e_doc}", exc_info=True)
        return jsonify({'error': f'Failed to process downloaded document: {str(e_doc)}', 'success': False}), 500
    except Exception as e: # General catch-all
        logger.error(f"Unexpected error in google_drive_download for file {file_id}, user {user_id}: {e}", exc_info=True)
        return jsonify({'error': f"An unexpected error occurred: {str(e)}", 'success': False}), 500

# Google Calendar Routes


@integrations_bp.route('/integrations/google/calendar/events', methods=['GET'])
def google_calendar_events():
    """List events from Google Calendar"""
    user_id = session.get('user_id', 'default')

    # Get required parameters
    calendar_id = request.args.get('calendar_id', 'primary')

    # Parse date parameters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str:
        start_date = datetime.now()
    else:
        start_date = datetime.fromisoformat(
            start_date_str.replace('Z', '+00:00'))

    if not end_date_str:
        end_date = start_date + timedelta(days=30)
    else:
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))

    try:
        # Get GoogleWebAuth instance
        google_auth = get_google_web_auth()

        # Get credentials
        creds = google_auth.get_credentials(user_id)
        if not creds:
            return jsonify({'error': 'Not authenticated with Google Calendar'}), 401

        # Create GoogleCalendarProvider
        calendar_provider = GoogleCalendarProvider(calendar_ids=[calendar_id])

        # Set credentials directly
        from googleapiclient.discovery import build
        calendar_provider.service = build('calendar', 'v3', credentials=creds)

        # Get events
        events = calendar_provider.get_events(
            calendar_id, start_date, end_date)
        return jsonify({
            'events': [event.to_dict() for event in events]
        }), 200
    except IntegrationError as e_auth:
        logger.warning(f"Google Calendar authentication/authorization error for user {user_id}: {e_auth}", exc_info=True)
        return jsonify({'error': str(e_auth)}), 401
    except APIError as e_api: # If calendar_provider methods raise APIError
        logger.error(f"Google APIError listing calendar events for user {user_id}: {e_api}", exc_info=True)
        return jsonify({'error': f'Google API error: {str(e_api)}'}), 502
    except Exception as e:
        logger.error(f"Unhandled exception listing calendar events for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred."}), 500


@integrations_bp.route('/integrations/google/calendar/calendars', methods=['GET'])
def google_calendar_list():
    """List available Google Calendars"""
    user_id = session.get('user_id', 'default')

    try:
        # Get GoogleWebAuth instance
        google_auth = get_google_web_auth()

        # Get credentials
        creds = google_auth.get_credentials(user_id)
        if not creds:
            return jsonify({'error': 'Not authenticated with Google Calendar'}), 401

        # Create GoogleCalendarProvider
        calendar_provider = GoogleCalendarProvider()

        # Set credentials directly
        from googleapiclient.discovery import build
        calendar_provider.service = build('calendar', 'v3', credentials=creds)

        # Get calendars
        calendars = calendar_provider.get_calendars()
        return jsonify({
            'calendars': [calendar.to_dict() for calendar in calendars]
        }), 200
    except IntegrationError as e_auth:
        logger.warning(f"Google Calendar authentication/authorization error for user {user_id} (list calendars): {e_auth}", exc_info=True)
        return jsonify({'error': str(e_auth)}), 401
    except APIError as e_api:
        logger.error(f"Google APIError listing calendars for user {user_id}: {e_api}", exc_info=True)
        return jsonify({'error': f'Google API error: {str(e_api)}'}), 502
    except Exception as e:
        logger.error(f"Unhandled exception listing calendars for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred."}), 500


@integrations_bp.route('/integrations/google/calendar/sync-tasks', methods=['POST'])
def google_calendar_sync_tasks():
    """Sync tasks with Google Calendar"""
    user_id = session.get('user_id', 'default')

    # Get parameters
    calendar_id = request.json.get('calendar_id', 'primary')
    task_ids = request.json.get('task_ids', [])

    try:
        # Get GoogleWebAuth instance
        google_auth = get_google_web_auth()

        # Get credentials
        creds = google_auth.get_credentials(user_id)
        if not creds:
            return jsonify({'error': 'Not authenticated with Google Calendar'}), 401

        # Create GoogleCalendarProvider
        calendar_provider = GoogleCalendarProvider(calendar_ids=[calendar_id])

        # Set credentials directly
        from googleapiclient.discovery import build
        calendar_provider.service = build('calendar', 'v3', credentials=creds)

        # Get GraphSpace instance
        graphspace = current_app.config['GRAPHSPACE']

        # Create CalendarService and add Google provider
        calendar_service = CalendarService()
        calendar_service.add_provider('google', calendar_provider)

        # Create TaskCalendarSync
        from graph_space_v2.integrations.calendar.task_sync import TaskCalendarSync
        task_sync = TaskCalendarSync(graphspace.task_service, calendar_service)

        # Sync tasks
        results = []
        for task_id in task_ids:
            try:
                task = graphspace.task_service.get_task(task_id)
                if not task:
                    results.append({
                        'task_id': task_id,
                        'success': False,
                        'error': 'Task not found',
                        'message': str(e_task_not_found)
                    })
                    continue
                except Exception as e_task_get: # Other errors getting task
                    logger.error(f"Error retrieving task {task_id} for calendar sync (user {user_id}): {e_task_get}", exc_info=True)
                    results.append({'task_id': task_id, 'success': False, 'error': f"Failed to retrieve task: {str(e_task_get)}"})
                    continue

                updated_task = task_sync.sync_task_to_calendar(task, 'google', calendar_id)
                results.append({
                    'task_id': task_id,
                    'success': updated_task is not None,
                    'calendar_event_id': updated_task.calendar_event_id if updated_task and hasattr(updated_task, 'calendar_event_id') else None,
                    'message': 'Sync successful' if updated_task else 'Sync did not result in an update or failed silently by provider.'
                })
            except IntegrationError as e_sync: # Errors from sync_task_to_calendar itself
                logger.error(f"IntegrationError syncing task {task_id} to calendar for user {user_id}: {e_sync}", exc_info=True)
                results.append({'task_id': task_id, 'success': False, 'error': f"Sync error: {str(e_sync)}"})
            except Exception as e_loop: # Catch-all for unexpected errors in loop
                logger.error(f"Unexpected error syncing task {task_id} in loop for user {user_id}: {e_loop}", exc_info=True)
                results.append({'task_id': task_id, 'success': False, 'error': f"Unexpected sync error: {str(e_loop)}"})

        logger.info(f"Calendar sync task processing completed for user {user_id}. Results: {results}")
        return jsonify({'results': results}), 200
    except IntegrationError as e_auth: # For initial auth/setup issues
        logger.warning(f"Google Calendar authentication/authorization error for user {user_id} (sync tasks): {e_auth}", exc_info=True)
        return jsonify({'error': str(e_auth)}), 401
    except ServiceError as e_service: # e.g. TaskService not available
        logger.error(f"ServiceError during calendar task sync setup for user {user_id}: {e_service}", exc_info=True)
        return jsonify({'error': f"A service error occurred: {str(e_service)}"}), 500
    except Exception as e: # General catch-all for setup before loop
        logger.error(f"Unhandled exception setting up calendar task sync for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred during task sync setup."}), 500
