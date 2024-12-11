"""
Health check and version endpoints for the PCAP Server API
"""
from datetime import datetime, timezone
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

# Import shared resources
from simpleLogger import SimpleLogger
from cache_utils import redis_client
from core import VERSION, BUILD_DATE, db, rate_limit

# Initialize logger
logger = SimpleLogger('health')

# Create blueprint
health_bp = Blueprint('health', __name__)

@health_bp.route('/api/v1/health', methods=['GET'])
@rate_limit()
def health_check():
    """Get API health status"""
    try:
        # Check database connection
        db("SELECT 1")

        # Check Redis connection
        redis_client.ping()

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'components': {
                'database': 'operational',
                'redis': 'operational'
            }
        }), 200

    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': str(e)
        }), 500

@health_bp.route('/api/v1/version', methods=['GET'])
@rate_limit()
def get_version():
    """Get API version information"""
    try:
        return jsonify({
            'version': VERSION,
            'build_date': BUILD_DATE if 'BUILD_DATE' in globals() else 'development'
        }), 200
    except Exception as e:
        logger.error(f"Version check error: {e}")
        return jsonify({'error': 'Version information unavailable'}), 500
