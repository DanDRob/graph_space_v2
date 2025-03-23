from flask import request, jsonify
from functools import wraps


def validate_json_request(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        return f(*args, **kwargs)
    return decorated


def validate_required_fields(*required_fields):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not request.is_json:
                return jsonify({"error": "Request must be JSON"}), 400

            data = request.json
            missing_fields = [
                field for field in required_fields if field not in data or not data[field]]

            if missing_fields:
                return jsonify({
                    "error": "Missing required fields",
                    "fields": missing_fields
                }), 400

            return f(*args, **kwargs)
        return decorated
    return decorator


def validate_id_parameter(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        id_param = kwargs.get('id')
        if not id_param or not id_param.strip():
            return jsonify({"error": "Invalid ID parameter"}), 400
        return f(*args, **kwargs)
    return decorated
