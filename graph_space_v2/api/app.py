from flask import Flask, render_template, send_from_directory
from flask_cors import CORS
import os
import datetime


def create_app(graphspace_instance=None):
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__))), "ui", "templates"),
                static_folder=os.path.join(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__))), "ui", "static"))
    CORS(app)  # Enable CORS for all routes

    # Configure app
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "data", "uploads")
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Store GraphSpace instance
    app.config['GRAPHSPACE'] = graphspace_instance

    # Add context processor for template variables
    @app.context_processor
    def inject_now():
        return {'now': datetime.datetime.now()}

    # Register middleware
    from graph_space_v2.api.middleware.auth import jwt_middleware
    app.before_request(jwt_middleware)

    # Register routes
    from graph_space_v2.api.routes.notes import notes_bp
    from graph_space_v2.api.routes.tasks import tasks_bp
    from graph_space_v2.api.routes.contacts import contacts_bp
    from graph_space_v2.api.routes.documents import documents_bp
    from graph_space_v2.api.routes.query import query_bp

    app.register_blueprint(notes_bp, url_prefix='/api')
    app.register_blueprint(tasks_bp, url_prefix='/api')
    app.register_blueprint(contacts_bp, url_prefix='/api')
    app.register_blueprint(documents_bp, url_prefix='/api')
    app.register_blueprint(query_bp, url_prefix='/api')

    # UI routes
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/notes')
    def notes():
        return render_template('notes.html')

    @app.route('/tasks')
    def tasks():
        return render_template('tasks.html')

    @app.route('/contacts')
    def contacts():
        # Redirect to index until contacts.html is created
        return render_template('index.html')

    @app.route('/documents')
    def documents():
        # Redirect to index until documents.html is created
        return render_template('index.html')

    @app.route('/graph')
    def graph():
        # Redirect to index until graph.html is created
        return render_template('index.html')

    @app.route('/settings')
    def settings():
        # Redirect to index until settings.html is created
        return render_template('index.html')

    @app.route('/api/status')
    def api_status():
        return {"status": "Graph Space API is running"}

    return app


def run_app(graphspace_instance, host='127.0.0.1', port=5000, debug=False):
    """Run the Flask application with the provided GraphSpace instance.

    Args:
        graphspace_instance: An instance of the GraphSpace class
        host: Host to run the server on, defaults to '127.0.0.1'
        port: Port to run the server on, defaults to 5000
        debug: Whether to run in debug mode, defaults to False
    """
    app = create_app(graphspace_instance)
    print(f"Starting Graph Space server on http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
