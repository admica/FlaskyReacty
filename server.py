#!/opt/pcapserver/venv_linux/bin/python3
"""
PCAP Server REST API Backend
Handles all API endpoints and core functionality for the PCAP system
"""
from flask import Flask, jsonify, send_file, abort, request
from flask_jwt_extended import JWTManager
from datetime import timedelta
import os
import threading
import traceback
import json
import hmac
import hashlib
import time
import atexit
import signal
import sys

# Import core components
from core import (
    VERSION, BUILD_DATE, logger, config, db_pool, db,
    CustomJSONEncoder, generate_signed_url, server_status
)

# Import blueprints
from api.auth import auth_bp
from api.job_jobs import jobs_bp
from api.job_tasks import tasks_bp
from api.job_merges import merges_bp
from api.job_downloads import downloads_bp
from api.sensors import sensors_bp
from api.admin import admin_bp
from api.health import health_bp
from api.storage import storage_bp
from api.analytics import analytics_bp
from api.search import search_bp
from api.subnet_mapping import subnet_mapping_bp
from api.network import network_bp
from api.logs import logs_bp
from api.logs_ws import logs_ws_bp, sock

# Import sensor thread management
from api.sensor_threads import (
    sensor_queues, sensor_threads, analysis_queue,
    request_count, request_count_lock
)

# Import network maintenance
from api.network_tasks import maintenance_thread

# Import job monitoring
from job_monitor import job_monitor_thread

# Import Redis client
from cache_utils import redis_client

def cleanup_handler(signo=None, frame=None):
    """Handle cleanup for both normal exit and signals"""
    try:
        logger.info(f"Starting cleanup... (Signal: {signo if signo else 'None'})")

        # Update server status
        server_status['state'] = 'stopping'

        # Stop network maintenance thread
        if maintenance_thread and maintenance_thread.is_alive():
            try:
                logger.info("Stopping network maintenance thread...")
                maintenance_thread.stop()
                maintenance_thread.join(timeout=10)
                if maintenance_thread.is_alive():
                    logger.warning("Network maintenance thread did not stop gracefully")
            except Exception as e:
                logger.error(f"Error stopping network maintenance thread: {e}")

        # Stop job monitor thread
        if job_monitor_thread and job_monitor_thread.is_alive():
            try:
                logger.info("Stopping job monitor thread...")
                job_monitor_thread.stop()
                job_monitor_thread.join(timeout=10)
                if job_monitor_thread.is_alive():
                    logger.warning("Job monitor thread did not stop gracefully")
            except Exception as e:
                logger.error(f"Error stopping job monitor thread: {e}")

        # Stop all sensor threads
        active_threads = list(sensor_queues.keys())
        logger.info(f"Stopping {len(active_threads)} sensor threads...")

        for sensor_name in active_threads:
            try:
                logger.info(f"Stopping thread for sensor: {sensor_name}")
                sensor_queues[sensor_name].put(None)
                if sensor_name in sensor_threads:
                    sensor_threads[sensor_name].join(timeout=10)
                    if sensor_threads[sensor_name].is_alive():
                        logger.warning(f"Thread for sensor {sensor_name} did not stop gracefully")
            except Exception as e:
                logger.error(f"Error stopping thread for sensor {sensor_name}: {e}")

        # Close database connections
        try:
            db_pool.closeall()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")

        # Close Redis connection
        try:
            redis_client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")

        server_status['state'] = 'stopped'
        logger.info("Cleanup complete")

        # If called by signal handler, exit
        if signo:
            sys.exit(0)

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        logger.error(traceback.format_exc())
        if signo:
            sys.exit(1)

# Initialize Flask app
app = Flask(__name__)
app.json_encoder = CustomJSONEncoder

# Initialize WebSocket support
sock.init_app(app)

# Configure JWT
app.config['JWT_SECRET_KEY'] = config.get('JWT', 'secret_key')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(seconds=int(config.get('JWT', 'access_token_expires')))
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(seconds=int(config.get('JWT', 'refresh_token_expires')))
app.config['JWT_TOKEN_LOCATION'] = ['headers']
app.config['JWT_BLOCKLIST_ENABLED'] = True
app.config['JWT_BLOCKLIST_TOKEN_CHECKS'] = ['access', 'refresh']

# Initialize JWT
jwt = JWTManager(app)

# Register token blacklist callback
@jwt.token_in_blocklist_loader
def check_if_token_in_blocklist(jwt_header, jwt_payload):
    """Check if token is in blacklist"""
    jti = jwt_payload['jti']
    token_in_redis = redis_client.get(f'revoked_token:{jti}')
    logger.debug(f"Checking token {jti} in blocklist: {'blocked' if token_in_redis else 'allowed'}")
    return token_in_redis is not None

# Register error handler for revoked tokens
@jwt.revoked_token_loader
def revoked_token_callback(jwt_header, jwt_payload):
    """Handle revoked token errors"""
    return jsonify({
        'error': 'Token has been revoked',
        'code': 'token_revoked'
    }), 401

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(jobs_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(merges_bp)
app.register_blueprint(downloads_bp)
app.register_blueprint(sensors_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(health_bp)
app.register_blueprint(storage_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(search_bp)
app.register_blueprint(subnet_mapping_bp)
app.register_blueprint(network_bp)
app.register_blueprint(logs_bp)
app.register_blueprint(logs_ws_bp)

# Register cleanup handlers
atexit.register(cleanup_handler)
signal.signal(signal.SIGTERM, cleanup_handler)
signal.signal(signal.SIGINT, cleanup_handler)

# File Download Handler
@app.route('/api/v1/files/download', methods=['GET'])
def download_file():
    """Handle signed URL downloads"""
    try:
        file_id = request.args.get('id')
        expires = request.args.get('expires')
        signature = request.args.get('signature')

        if not all([file_id, expires, signature]):
            return jsonify({"error": "Invalid download URL"}), 400

        # Check expiration
        if int(expires) < time.time():
            return jsonify({"error": "Download URL has expired"}), 400

        # Verify signature
        signature_base = f"{file_id}:{expires}"
        expected_signature = hmac.new(
            config.get('SERVER', 'secret_key').encode(),
            signature_base.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            return jsonify({"error": "Invalid signature"}), 400

        # Get file info from Redis
        from cache_utils import redis_client
        url_info = redis_client.get(f"signed_url:{file_id}")
        if not url_info:
            return jsonify({"error": "Download URL not found"}), 404

        url_info = json.loads(url_info)
        file_path = url_info['file_path']

        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404

        return send_file(
            file_path,
            mimetype=url_info['file_type'],
            as_attachment=True,
            download_name=os.path.basename(file_path)
        )

    except Exception as e:
        logger.error(f"File download error: {e}")
        return jsonify({"error": "Failed to download file"}), 500

# Error Handlers
@app.errorhandler(400)
def bad_request_error(error):
    return jsonify({
        'error': 'Bad Request',
        'message': str(error)
    }), 400

@app.errorhandler(401)
def unauthorized_error(error):
    return jsonify({
        'error': 'Unauthorized',
        'message': 'Authentication required'
    }), 401

@app.errorhandler(403)
def forbidden_error(error):
    return jsonify({
        'error': 'Forbidden',
        'message': 'You do not have permission to access this resource'
    }), 403

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested resource was not found'
    }), 404

@app.errorhandler(500)
def internal_server_error(error):
    logger.error(f"Internal server error: {error}")
    logger.error(traceback.format_exc())
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred'
    }), 500

@app.before_request
def before_request():
    """Request counting and circuit breaking middleware"""
    global request_count
    with request_count_lock:
        request_count += 1
        current_count = request_count

        if current_count > 20:
            logger.warning(f"High request count: {current_count}")
            if current_count > 50:
                time.sleep(0.1)
                if current_count > 250:
                    time.sleep(0.25)
                    if current_count > 1000:
                        logger.error("Circuit breaker triggered")
                        abort(503)

@app.after_request
def after_request(response):
    """Post-request operations"""
    global request_count
    with request_count_lock:
        request_count -= 1

    # Allow CORS from frontend
    response.headers['Access-Control-Allow-Origin'] = 'https://localhost:5173'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'

    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

if __name__ == '__main__':
    try:
        # Start maintenance thread
        maintenance_thread.start()
        logger.info("Network maintenance thread started")

        # Start job monitor thread
        job_monitor_thread.start()
        logger.info("Job monitor thread started")

        # Configure SSL context
        ssl_context = None
        if config.has_section('SSL'):
            import ssl
            ssl_context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(
                certfile=config.get('SSL', 'ssl_crt'),
                keyfile=config.get('SSL', 'ssl_key')
            )
            logger.info("SSL configuration loaded")
        else:
            logger.warning("No SSL configuration found, running without SSL")

        # Start the Flask app
        app.run(
            host=config.get('SERVER', 'host'),
            port=config.getint('SERVER', 'port'),
            debug=config.getboolean('SERVER', 'debug'),
            ssl_context=ssl_context
        )
    except Exception as e:
        logger.error(f"Server startup error: {e}")
        logger.error(traceback.format_exc())
    finally:
        cleanup_handler()