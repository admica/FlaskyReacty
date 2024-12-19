"""
Admin endpoints for the PCAP Server API
"""
import psutil
import os
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
import threading
from functools import wraps
import json

# Import shared resources
from simpleLogger import SimpleLogger
from cache_utils import redis_client
from core import db, rate_limit

# Initialize logger
logger = SimpleLogger('admin')

# Create blueprint
admin_bp = Blueprint('admin', __name__)

def admin_required():
    """Decorator to require admin role"""
    def wrapper(fn):
        @wraps(fn)  # Preserve original function name and attributes
        @jwt_required()
        def decorated_function(*args, **kwargs):
            claims = get_jwt()
            if claims.get('role') != 'admin':
                return jsonify({"error": "Admin privileges required"}), 403
            return fn(*args, **kwargs)
        return decorated_function
    return wrapper

@admin_bp.route('/api/v1/admin/system/status', methods=['GET'])
@admin_required()
@rate_limit()
def get_system_status():
    """Get detailed system status information"""
    try:
        # Get CPU info
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()

        # Get memory info
        memory = psutil.virtual_memory()

        # Get disk info
        disk = psutil.disk_usage('/')

        # Get thread info
        threads = []
        for thread in threading.enumerate():
            threads.append({
                'name': thread.name,
                'id': thread.ident,
                'alive': thread.is_alive(),
                'daemon': thread.daemon
            })

        # Get application stats
        rows = db("SELECT status, COUNT(*) FROM sensors GROUP BY status")
        sensor_status = {
            'online': 0,
            'offline': 0,
            'maintenance': 0,
            'total': 0
        }
        for row in rows:
            status = row[0].lower()
            count = row[1]
            if status == 'online':
                sensor_status['online'] = count
            elif status == 'offline':
                sensor_status['offline'] = count
            elif status == 'maintenance':
                sensor_status['maintenance'] = count
            sensor_status['total'] += count

        # Get job stats
        rows = db("SELECT status, COUNT(*) FROM jobs GROUP BY status")
        job_stats = {
            'active_jobs': 0,
            'queued_jobs': 0
        }
        for row in rows:
            status = row[0].lower()
            count = row[1]
            if status in ['running', 'retrieving']:
                job_stats['active_jobs'] += count
            elif status == 'submitted':
                job_stats['queued_jobs'] += count

        return jsonify({
            'system_info': {
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'frequency': {
                        'current': cpu_freq.current if cpu_freq else None,
                        'min': cpu_freq.min if cpu_freq else None,
                        'max': cpu_freq.max if cpu_freq else None
                    }
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'used': memory.used,
                    'percent': memory.percent
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': disk.percent
                },
                'threads': threads
            },
            'application_stats': {
                'sensor_status': sensor_status,
                **job_stats
            },
            'server_status': 'Healthy'  # TODO: Add logic to determine status
        }), 200

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({"error": "Failed to get system status"}), 500

@admin_bp.route('/api/v1/admin/system/cache', methods=['GET'])
@admin_required()
@rate_limit()
def get_cache_state():
    """Get Redis cache statistics"""
    try:
        # Get Redis info
        info = redis_client.info()

        # Calculate total keys and expires across all databases
        total_keys = 0
        total_expires = 0
        for key, value in info.items():
            if key.startswith('db') and isinstance(value, dict):
                total_keys += value.get('keys', 0)
                total_expires += value.get('expires', 0)

        return jsonify({
            'status': 'connected',
            'version': info.get('redis_version'),
            'uptime': info.get('uptime_in_seconds'),
            'connected_clients': info.get('connected_clients'),
            'used_memory': info.get('used_memory_human'),
            'used_memory_peak': info.get('used_memory_peak_human'),
            'total_commands_processed': info.get('total_commands_processed'),
            'keyspace_hits': info.get('keyspace_hits'),
            'keyspace_misses': info.get('keyspace_misses'),
            'keys': {
                'total': total_keys,
                'expires': total_expires
            }
        }), 200

    except Exception as e:
        logger.error(f"Error getting cache state: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@admin_bp.route('/api/v1/admin/cache/clear', methods=['POST'])
@admin_required()
@rate_limit()
def clear_cache():
    """Clear specific cache type"""
    try:
        data = request.get_json()
        cache_type = data.get('type')

        if not cache_type:
            return jsonify({"error": "Cache type is required"}), 400

        # Handle "all" cache type
        if cache_type == 'all':
            patterns = ['sensors:admin', 'sensors:user', 'device:*']
            total_cleared = 0
            for pattern in patterns:
                keys = redis_client.keys(pattern)
                if keys:
                    redis_client.delete(*keys)
                    total_cleared += len(keys)
            logger.info(f"Cleared all caches, total keys cleared: {total_cleared}")
            return jsonify({"message": "All caches cleared", "keys_cleared": total_cleared}), 200

        # Handle individual cache types
        pattern = cache_type
        if cache_type == 'devices:*':
            pattern = 'device:*'  # Convert to actual Redis key pattern
        elif cache_type == 'sensors:admin':
            pattern = 'sensors:admin'
        elif cache_type == 'sensors:user':
            pattern = 'sensors:user'
        else:
            return jsonify({"error": f"Unknown cache type: {cache_type}"}), 400

        # Delete keys matching the pattern
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
            logger.info(f"Cleared cache for pattern: {pattern}, keys cleared: {len(keys)}")
            return jsonify({"message": f"Cache cleared for {cache_type}", "keys_cleared": len(keys)}), 200

        return jsonify({"message": f"No keys found for {cache_type}"}), 200

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({"error": f"Failed to clear cache: {str(e)}"}), 500

@admin_bp.route('/api/v1/admin/cache/refresh', methods=['POST'])
@admin_required()
@rate_limit()
def refresh_cache():
    """Refresh specific cache type"""
    try:
        data = request.get_json()
        cache_type = data.get('type')

        if not cache_type:
            return jsonify({"error": "Cache type is required"}), 400

        # Handle different cache types
        if cache_type == 'sensors:admin':
            # Refresh admin sensor cache
            sensors = db("SELECT * FROM sensors")
            redis_client.setex('sensors:admin', 3600, json.dumps([dict(s) for s in sensors]))
        elif cache_type == 'sensors:user':
            # Refresh user sensor cache
            sensors = db("SELECT id, name, status FROM sensors")
            redis_client.setex('sensors:user', 3600, json.dumps([dict(s) for s in sensors]))
        elif cache_type == 'devices:*':
            # Refresh device caches - this might need customization based on your needs
            devices = db("SELECT * FROM devices")
            for device in devices:
                redis_client.setex(f"device:{device['id']}", 3600, json.dumps(dict(device)))
        else:
            return jsonify({"error": f"Unknown cache type: {cache_type}"}), 400

        logger.info(f"Refreshed cache for type: {cache_type}")
        return jsonify({"message": f"Cache refreshed for {cache_type}"}), 200

    except Exception as e:
        logger.error(f"Error refreshing cache: {e}")
        return jsonify({"error": f"Failed to refresh cache: {str(e)}"}), 500

@admin_bp.route('/api/v1/admin/cache/metrics', methods=['GET'])
@admin_required()
@rate_limit()
def get_cache_metrics():
    """Get detailed cache metrics"""
    try:
        info = redis_client.info()
        metrics = {
            'sensors': {
                'admin': {
                    'size': len(redis_client.get('sensors:admin') or ''),
                    'ttl': redis_client.ttl('sensors:admin'),
                    'exists': bool(redis_client.exists('sensors:admin'))
                },
                'user': {
                    'size': len(redis_client.get('sensors:user') or ''),
                    'ttl': redis_client.ttl('sensors:user'),
                    'exists': bool(redis_client.exists('sensors:user'))
                }
            },
            'devices': {
                'count': len(redis_client.keys('device:*')),
                'memory_usage': sum(len(v or '') for v in redis_client.mget(redis_client.keys('device:*') or []))
            },
            'performance': {
                'hits': info.get('keyspace_hits', 0),
                'misses': info.get('keyspace_misses', 0),
                'hit_rate': info.get('keyspace_hits', 0) / (info.get('keyspace_hits', 0) + info.get('keyspace_misses', 1)) * 100
            }
        }

        return jsonify(metrics), 200

    except Exception as e:
        logger.error(f"Error getting cache metrics: {e}")
        return jsonify({"error": f"Failed to get cache metrics: {str(e)}"}), 500

@admin_bp.route('/api/v1/admin/users', methods=['GET'])
@admin_required()
@rate_limit()
def get_admin_users():
    """Get list of admin users"""
    try:
        # Query admin_users table
        rows = db("""
            SELECT username, added_by, added_date
            FROM admin_users
            ORDER BY username
        """)
        
        admins = []
        for row in rows:
            admins.append({
                'username': row[0],
                'added_by': row[1],
                'added_date': row[2].isoformat() if row[2] else None
            })
            
        return jsonify({'admins': admins}), 200
        
    except Exception as e:
        logger.error(f"Error getting admin users: {e}")
        return jsonify({"error": "Failed to get admin users"}), 500

@admin_bp.route('/api/v1/admin/users/<username>', methods=['GET'])
@admin_required()
@rate_limit()
def get_admin_user(username):
    """Get details for a specific admin user"""
    try:
        # Query admin_users table
        row = db("""
            SELECT username, added_by, added_date
            FROM admin_users
            WHERE username = %s
        """, (username,))
        
        if not row:
            return jsonify({"error": "Admin user not found"}), 404
            
        return jsonify({
            'username': row[0][0],
            'added_by': row[0][1],
            'added_date': row[0][2].isoformat() if row[0][2] else None
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting admin user {username}: {e}")
        return jsonify({"error": "Failed to get admin user"}), 500

@admin_bp.route('/api/v1/admin/users', methods=['POST'])
@admin_required()
@rate_limit()
def add_admin_user():
    """Add a new admin user"""
    try:
        data = request.get_json()
        if not data or 'username' not in data:
            return jsonify({"error": "Username is required"}), 400
            
        username = data['username'].strip().lower()
        added_by = get_jwt_identity()
        
        # Check if user already exists
        existing = db("SELECT username FROM admin_users WHERE username = %s", (username,))
        if existing:
            return jsonify({"error": "Admin user already exists"}), 409
            
        # Add new admin user
        db("""
            INSERT INTO admin_users (username, added_by)
            VALUES (%s, %s)
        """, (username, added_by))
        
        # Add audit log entry
        db("""
            INSERT INTO admin_audit_log (action, username, changed_by)
            VALUES ('add_admin', %s, %s)
        """, (username, added_by))
        
        logger.info(f"Added new admin user: {username} (by {added_by})")
        return jsonify({"message": "Admin user added successfully"}), 201
        
    except Exception as e:
        logger.error(f"Error adding admin user: {e}")
        return jsonify({"error": "Failed to add admin user"}), 500

@admin_bp.route('/api/v1/admin/users/<username>', methods=['DELETE'])
@admin_required()
@rate_limit()
def remove_admin_user(username):
    """Remove an admin user"""
    try:
        # Check if user exists
        existing = db("SELECT username FROM admin_users WHERE username = %s", (username,))
        if not existing:
            return jsonify({"error": "Admin user not found"}), 404
            
        # Remove admin user
        db("DELETE FROM admin_users WHERE username = %s", (username,))
        
        # Add audit log entry
        changed_by = get_jwt_identity()
        db("""
            INSERT INTO admin_audit_log (action, username, changed_by)
            VALUES ('remove_admin', %s, %s)
        """, (username, changed_by))
        
        logger.info(f"Removed admin user: {username} (by {changed_by})")
        return jsonify({"message": "Admin user removed successfully"}), 200
        
    except Exception as e:
        logger.error(f"Error removing admin user: {e}")
        return jsonify({"error": "Failed to remove admin user"}), 500
