"""
Storage status endpoints for the PCAP Server API
"""
import psutil
import os
from datetime import datetime, timezone
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
import configparser

# Import shared resources
from simpleLogger import SimpleLogger
from core import rate_limit
from api.auth import admin_required

# Initialize logger
logger = SimpleLogger('storage')

# Create blueprint
storage_bp = Blueprint('storage', __name__)

def format_bytes(bytes_value):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.2f} PB"

@storage_bp.route('/api/v1/storage', methods=['GET'])
@jwt_required()
@admin_required()
@rate_limit()
def get_storage_status():
    """Get storage usage for configured paths"""
    try:
        # Load config
        config = configparser.ConfigParser()
        config.read('/opt/pcapserver/config.ini')

        # Get configured paths
        storage_paths = {
            'data': config.get('STORAGE_PATHS', 'data'),
            'db': config.get('STORAGE_PATHS', 'db'),
            'tmp': config.get('STORAGE_PATHS', 'tmp')
        }

        storage_info = {}
        for name, path in storage_paths.items():
            try:
                usage = psutil.disk_usage(path)
                storage_info[name] = {
                    'path': path,
                    'total_bytes': usage.total,
                    'used_bytes': usage.used,
                    'free_bytes': usage.free,
                    'percent_used': usage.percent,
                    'human_readable': {
                        'total': format_bytes(usage.total),
                        'used': format_bytes(usage.used),
                        'free': format_bytes(usage.free)
                    }
                }
            except Exception as e:
                logger.error(f"Error getting disk usage for {path}: {e}")
                storage_info[name] = {
                    'path': path,
                    'error': str(e)
                }

        return jsonify({
            'storage': storage_info,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error getting storage status: {e}")
        return jsonify({"error": "Failed to get storage status"}), 500
