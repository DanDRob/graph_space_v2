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
    # Disabled for hackathon - no authentication required
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
        # Authentication disabled for hackathon
        return f(*args, **kwargs)
    return decorated
