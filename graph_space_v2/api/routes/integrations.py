from flask import Blueprint, request, jsonify, current_app, redirect, session, url_for
import os
from datetime import datetime, timedelta
import uuid
import webbrowser

from graph_space_v2.integrations.google.web_auth import GoogleWebAuth
from graph_space_v2.integrations.google.drive_service import GoogleDriveService
from graph_space_v2.integrations.calendar.providers.google_calendar import GoogleCalendarProvider
from graph_space_v2.integrations.calendar.calendar_service import CalendarService
from graph_space_v2.utils.errors.exceptions import IntegrationError

integrations_bp = Blueprint('integrations', __name__)

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
    redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI')

    if not client_id or not client_secret:
        raise IntegrationError('Google API credentials not configured')

    return GoogleWebAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)

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
        })
    except Exception as e:
        return jsonify({'authenticated': False, 'error': str(e)}), 500


@integrations_bp.route('/integrations/google/auth/start', methods=['GET'])
def google_auth_start():
    """Start Google OAuth flow"""
    user_id = session.get('user_id', 'default')

    try:
        # Get GoogleWebAuth instance
        google_auth = get_google_web_auth()

        # Start OAuth flow using the environment variables
        auth_url = google_auth.start_auth_flow(user_id)

        # Open the auth URL in a browser for desktop OAuth flow
        webbrowser.open(auth_url)

        return jsonify({
            'auth_url': auth_url,
            'message': 'Authentication started. Please complete the process in your browser.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@integrations_bp.route('/oauth2callback', methods=['GET'])
def oauth2callback():
    """Handle Google OAuth callback at the registered redirect URI"""
    user_id = session.get('user_id', 'default')

    try:
        # Get GoogleWebAuth instance
        google_auth = get_google_web_auth()

        # Handle callback - state verification happens inside the method
        token_info = google_auth.handle_callback(request.url)

        # Save token for user
        google_auth.save_token(token_info, user_id)

        # Redirect to settings page
        return redirect('/settings?google_auth=success')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@integrations_bp.route('/integrations/google/auth/callback', methods=['GET'])
def google_auth_callback():
    """Additional callback handler for backward compatibility"""
    return oauth2callback()


@integrations_bp.route('/integrations/google/auth/logout', methods=['POST'])
def google_auth_logout():
    """Revoke Google OAuth token"""
    user_id = session.get('user_id', 'default')

    try:
        # Get GoogleWebAuth instance
        google_auth = get_google_web_auth()

        # Revoke token
        revoked = google_auth.revoke_token(user_id)

        return jsonify({'success': revoked})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Google Drive Routes


@integrations_bp.route('/integrations/google/drive/files', methods=['GET'])
def google_drive_files():
    """List files from Google Drive"""
    user_id = session.get('user_id', 'default')

    # Get optional query parameters
    folder_id = request.args.get('folder_id')
    query = request.args.get('query')
    mime_types = request.args.getlist('mime_type')
    max_results = int(request.args.get('max_results', 100))

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
            max_results=max_results
        )
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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

        # Get file metadata
        file_metadata = drive_service.service.files().get(
            fileId=file_id, fields="name,mimeType").execute()

        # Import document directly
        document_id = drive_service.import_document(file_id)

        return jsonify({
            'success': True,
            'document_id': document_id,
            'filename': file_metadata.get('name')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
                        'error': 'Task not found'
                    })
                    continue

                updated_task = task_sync.sync_task_to_calendar(
                    task, 'google', calendar_id)

                results.append({
                    'task_id': task_id,
                    'success': updated_task is not None,
                    'calendar_id': updated_task.calendar_id if updated_task else None
                })
            except Exception as e:
                results.append({
                    'task_id': task_id,
                    'success': False,
                    'error': str(e)
                })

        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
