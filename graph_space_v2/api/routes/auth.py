from flask import Blueprint, request, jsonify, current_app
from graph_space_v2.api.middleware.auth import generate_token
from graph_space_v2.api.middleware.validation import validate_json_request, validate_required_fields
import uuid
import hashlib
import os

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/auth/login', methods=['POST'])
@validate_json_request
@validate_required_fields('username', 'password')
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    # For simplicity, we'll use a hardcoded user during development
    # In production, you would validate against a user database

    # Simple password hashing for demo purposes
    hashed_password = hashlib.sha256(password.encode()).hexdigest()

    # Check if this is the dev user (admin/admin)
    if username == 'admin' and hashed_password == hashlib.sha256('admin'.encode()).hexdigest():
        user_id = 'user-1'  # Hardcoded ID for demo

        # Generate JWT token
        token = generate_token(user_id, username)

        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'id': user_id,
                'username': username
            }
        })

    return jsonify({
        'success': False,
        'error': 'Invalid username or password'
    }), 401


@auth_bp.route('/auth/register', methods=['POST'])
@validate_json_request
@validate_required_fields('username', 'password')
def register():
    # In production, you would implement proper user registration
    # For this demo, we'll just return a success message

    data = request.json
    username = data.get('username')

    # In production, check if username already exists

    user_id = f"user-{str(uuid.uuid4())[:8]}"

    # Generate token for auto-login
    token = generate_token(user_id, username)

    return jsonify({
        'success': True,
        'message': 'User registered successfully',
        'token': token,
        'user': {
            'id': user_id,
            'username': username
        }
    })


@auth_bp.route('/auth/status', methods=['GET'])
def auth_status():
    # Simple endpoint to check if user is authenticated
    user = getattr(request, 'user', None)

    if user:
        return jsonify({
            'authenticated': True,
            'user': user
        })

    return jsonify({
        'authenticated': False
    })
