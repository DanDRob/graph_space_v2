from flask import request, jsonify, current_app
import jwt
from functools import wraps
import os
from datetime import datetime, timedelta

# List of endpoints that don't require authentication
PUBLIC_ENDPOINTS = [
    '/',
    '/api/auth/login',
    '/api/auth/register',
]


def jwt_middleware():
    if request.path in PUBLIC_ENDPOINTS:
        return None

    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        # For development, allow requests without tokens
        # In production, you'd return a 401 here
        return None

    token = auth_header.split(' ')[1]
    try:
        # In production, use a proper secret key from environment variables
        SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'development_secret_key')
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        request.user = payload
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401

    return None


def generate_token(user_id, username, expiration_days=7):
    SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'development_secret_key')
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': datetime.utcnow() + timedelta(days=expiration_days)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(request, 'user'):
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated
