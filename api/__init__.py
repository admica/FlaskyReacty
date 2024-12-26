"""
PCAP Server API Blueprints
"""

from flask import Flask
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from core import config, logger

from api.auth import auth_bp, check_if_token_revoked
from api.jobs import jobs_bp
from api.sensors import sensors_bp
from api.preferences import preferences_bp
from api.health import health_bp
from api.search import search_bp
from api.network import network_bp
from api.admin import admin_bp
from api.maintenance import start_maintenance_thread

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)

    # Configure JWT
    app.config['JWT_SECRET_KEY'] = config.get('JWT', 'secret_key')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = int(config.get('JWT', 'access_token_expires'))
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = int(config.get('JWT', 'refresh_token_expires'))

    # Initialize JWT
    jwt = JWTManager(app)
    jwt.token_in_blocklist_loader(check_if_token_revoked)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(sensors_bp)
    app.register_blueprint(preferences_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(network_bp)
    app.register_blueprint(admin_bp)

    # Initialize SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*")

    # Start maintenance operations
    start_maintenance_thread()

    logger.info("Application initialized successfully")
    return app, socketio