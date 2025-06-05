from flask import Blueprint, request, jsonify, current_app
from graph_space_v2.api.middleware.auth import generate_token
from graph_space_v2.api.middleware.validation import validate_json_request, validate_required_fields
import uuid
import hashlib
import os
import logging # Added
from graph_space_v2.utils.errors.exceptions import AuthenticationError, ServiceError # Added

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__) # Added


@auth_bp.route('/auth/login', methods=['POST'])
@validate_json_request
@validate_required_fields('username', 'password')
def login():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')

        # Simple password hashing for demo purposes
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        # Check if this is the dev user (admin/admin)
        # In a real app, this would involve a database lookup and password verification
        # which could raise AuthenticationError or other ServiceErrors.
        if username == 'admin' and hashed_password == hashlib.sha256('admin'.encode()).hexdigest():
            user_id = 'user-1'  # Hardcoded ID for demo
            token = generate_token(user_id, username)
            logger.info(f"User '{username}' logged in successfully.")
            return jsonify({
                'success': True,
                'token': token,
                'user': {
                    'id': user_id,
                    'username': username
                }
            }), 200
        else:
            logger.warning(f"Failed login attempt for username: {username}")
            return jsonify({'error': 'Invalid username or password'}), 401

    except Exception as e:
        logger.error(f"Unhandled exception during login for username {data.get('username', 'N/A')}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred during login."}), 500


@auth_bp.route('/auth/register', methods=['POST'])
@validate_json_request
@validate_required_fields('username', 'password')
def register():
    # This is a placeholder implementation.
    # A real implementation would interact with a user service/database
    # and could raise AuthenticationError (e.g., username exists) or ServiceError.
    try:
        data = request.json
        username = data.get('username')
        # password = data.get('password') # Password would be hashed and stored

        # Placeholder: In production, check if username already exists, hash password, store user.
        # For now, we assume registration is always "successful" for demo purposes.
        user_id = f"user-{str(uuid.uuid4())[:8]}"
        token = generate_token(user_id, username) # Auto-login by providing a token

        logger.info(f"User '{username}' (ID: {user_id}) registered (placeholder).")
        return jsonify({
            'message': 'User registered successfully (placeholder implementation)',
            'token': token, # Providing token for immediate use
            'user': {
                'id': user_id,
                'username': username
            }
        }), 201 # 201 Created for successful registration
    except Exception as e:
        logger.error(f"Unhandled exception during registration for username {data.get('username', 'N/A')}: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred during registration."}), 500


@auth_bp.route('/auth/status', methods=['GET'])
def auth_status():
    # Simple endpoint to check if user is authenticated
    try:
        user = getattr(request, 'user', None) # Assuming 'user' is injected by @token_required on other routes

        if user:
            logger.debug(f"Auth status check: User '{user.get('username')}' is authenticated.")
            return jsonify({
                'authenticated': True,
                'user': user # 'user' here is the payload from the JWT token
            }), 200
        else:
            logger.debug("Auth status check: No authenticated user found in request context.")
            return jsonify({'authenticated': False}), 200 # Still 200 OK, just indicates not authenticated
    except Exception as e:
        logger.error(f"Unhandled exception during auth status check: {e}", exc_info=True)
        return jsonify({'error': "An unexpected error occurred while checking auth status."}), 500
