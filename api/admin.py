"""
Admin endpoints for the PCAP Server API
PATH: api/admin.py
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
from core import db, rate_limit, config

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
        # Get admin users from local config
        local_admins = []
        local_users = config.items('LOCAL_USERS')
        for _, user_json in local_users:
            try:
                user_data = json.loads(user_json)
                if user_data.get('role') == 'admin':
                    local_admins.append({
                        'username': user_data.get('username'),
                        'created_at': None,  # Local users don't have creation date
                        'last_active': None  # Local users don't track activity
                    })
            except json.JSONDecodeError:
                continue

        # Get admin users from database (LDAP users)
        rows = db("""
            SELECT username, added_date, NULL as last_active
            FROM admin_users
            ORDER BY username
        """)

        # Combine local and LDAP admin users
        admins = local_admins + [{
            'username': row[0],
            'created_at': row[1].isoformat() if row[1] else None,
            'last_active': row[2].isoformat() if row[2] else None
        } for row in rows]

        return jsonify({'admins': admins}), 200

    except Exception as e:
        logger.error(f"Error getting admin users: {e}")
        return jsonify({"error": "Failed to get admin users"}), 500

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
        if not username:
            return jsonify({"error": "Invalid username"}), 400

        # Check if user is already an admin in local config
        local_users = config.items('LOCAL_USERS')
        for _, user_json in local_users:
            try:
                user_data = json.loads(user_json)
                if user_data.get('username') == username and user_data.get('role') == 'admin':
                    return jsonify({"error": "User is already an admin"}), 409
            except json.JSONDecodeError:
                continue

        # Check if user is already an admin in database
        rows = db("SELECT username FROM admin_users WHERE username = %s", [username])
        if rows:
            return jsonify({"error": "User is already an admin"}), 409

        # Add user to admin_users table
        current_user = get_jwt_identity()
        db("""
            INSERT INTO admin_users (username, added_by)
            VALUES (%s, %s)
        """, [username, current_user])

        logger.info(f"Added new admin user: {username} (by {current_user})")
        return jsonify({"message": "Admin user added successfully"}), 201

    except Exception as e:
        logger.error(f"Error adding admin user: {e}")
        return jsonify({"error": "Failed to add admin user"}), 500

@admin_bp.route('/api/v1/admin/users/<username>', methods=['GET'])
@admin_required()
@rate_limit()
def get_admin_user(username):
    """Get details of a specific admin user"""
    try:
        username = username.strip().lower()

        # Check local admins first
        local_users = config.items('LOCAL_USERS')
        for _, user_json in local_users:
            try:
                user_data = json.loads(user_json)
                if user_data.get('username') == username and user_data.get('role') == 'admin':
                    return jsonify({
                        'username': username,
                        'type': 'local',
                        'created_at': None,  # Local users don't have creation date
                        'last_active': None  # Local users don't track activity
                    }), 200
            except json.JSONDecodeError:
                continue

        # Check database for LDAP admin users
        rows = db("""
            SELECT username, added_date, added_by
            FROM admin_users
            WHERE username = %s
        """, [username])

        if not rows:
            return jsonify({"error": "Admin user not found"}), 404

        row = rows[0]
        return jsonify({
            'username': row[0],
            'type': 'ldap',
            'created_at': row[1].isoformat() if row[1] else None,
            'added_by': row[2]
        }), 200

    except Exception as e:
        logger.error(f"Error getting admin user details: {e}")
        return jsonify({"error": "Failed to get admin user details"}), 500

@admin_bp.route('/api/v1/admin/users/<username>', methods=['DELETE'])
@admin_required()
@rate_limit()
def remove_admin_user(username):
    """Remove admin privileges from a user"""
    try:
        username = username.strip().lower()
        current_user = get_jwt_identity()

        # Prevent self-deletion
        if username == current_user:
            return jsonify({"error": "Cannot remove admin privileges from yourself"}), 403

        # Check if user is a local admin (cannot be removed)
        local_users = config.items('LOCAL_USERS')
        for _, user_json in local_users:
            try:
                user_data = json.loads(user_json)
                if user_data.get('username') == username and user_data.get('role') == 'admin':
                    return jsonify({"error": "Cannot remove admin privileges from local admin users"}), 403
            except json.JSONDecodeError:
                continue

        # Remove from admin_users table
        result = db("""
            DELETE FROM admin_users
            WHERE username = %s
            RETURNING username
        """, [username])

        if not result:
            return jsonify({"error": "Admin user not found"}), 404

        logger.info(f"Removed admin privileges from user: {username} (by {current_user})")
        return jsonify({"message": "Admin privileges removed successfully"}), 200

    except Exception as e:
        logger.error(f"Error removing admin user: {e}")
        return jsonify({"error": "Failed to remove admin user"}), 500

@admin_bp.route('/api/v1/admin/audit', methods=['GET'])
@admin_required()
@rate_limit()
def get_admin_audit_log():
    """Get admin user audit log"""
    try:
        # Get optional query parameters
        username = request.args.get('username')
        action = request.args.get('action')  # Should be 'ADD' or 'REMOVE'
        days = request.args.get('days', type=int)
        limit = request.args.get('limit', 100, type=int)  # Default to 100 entries

        # Build query
        query = """
            SELECT id, action, username, changed_by, change_date
            FROM admin_audit_log
            WHERE 1=1
        """
        params = []

        # Add filters if provided
        if username:
            query += " AND username = %s"
            params.append(username)
        if action:
            query += " AND action = %s"
            params.append(action.upper())  # Convert to uppercase to match DB
        if days:
            query += " AND change_date >= NOW() - INTERVAL '%s days'"
            params.append(days)

        # Add order and limit
        query += " ORDER BY change_date DESC LIMIT %s"
        params.append(limit)

        # Execute query
        rows = db(query, params)

        # Format results
        audit_logs = [{
            'id': row[0],
            'action': row[1],  # Will be 'ADD' or 'REMOVE'
            'username': row[2],
            'changed_by': row[3],
            'change_date': row[4].isoformat() if row[4] else None
        } for row in rows]

        return jsonify({
            'audit_logs': audit_logs,
            'total': len(audit_logs),
            'filters': {
                'username': username,
                'action': action,
                'days': days,
                'limit': limit
            }
        }), 200

    except Exception as e:
        logger.error(f"Error getting admin audit log: {e}")
        return jsonify({"error": "Failed to get admin audit log"}), 500

@admin_bp.route('/api/v1/admin/active-users', methods=['GET'])
@admin_required()
@rate_limit()
def get_active_users():
    """Get list of currently active users with their session information"""
    try:
        # Get active sessions with role information
        rows = db("""
            SELECT 
                s.username,
                s.created_at as session_start,
                s.expires_at
            FROM user_sessions s
            WHERE s.expires_at > NOW()
            ORDER BY s.created_at DESC
        """)

        # Get local admin users from config
        local_admins = set()
        local_users = config.items('LOCAL_USERS')
        for _, user_json in local_users:
            try:
                user_data = json.loads(user_json)
                if user_data.get('role') == 'admin':
                    local_admins.add(user_data.get('username'))
            except json.JSONDecodeError:
                continue

        # Get LDAP admin users from database
        db_admins = set()
        admin_rows = db("SELECT username FROM admin_users")
        if admin_rows:
            db_admins = {row[0] for row in admin_rows}

        # Combine results
        active_users = [{
            'username': row[0],
            'session_start': row[1].isoformat() if row[1] else None,
            'session_expires': row[2].isoformat() if row[2] else None,
            'role': 'admin' if row[0] in local_admins or row[0] in db_admins else 'user'
        } for row in rows]

        return jsonify({
            'active_users': active_users,
            'total': len(active_users)
        }), 200

    except Exception as e:
        logger.error(f"Error getting active users: {e}")
        return jsonify({"error": "Failed to get active users"}), 500

@admin_bp.route('/api/v1/admin/user-sessions', methods=['GET'])
@admin_required()
@rate_limit()
def get_user_sessions_summary():
    """Get list of active and recently active users with their latest session information"""
    try:
        # Get local and LDAP admin users
        local_admins = set()
        local_users = config.items('LOCAL_USERS')
        for _, user_json in local_users:
            try:
                user_data = json.loads(user_json)
                if user_data.get('role') == 'admin':
                    local_admins.add(user_data.get('username'))
            except json.JSONDecodeError:
                continue

        db_admins = set()
        admin_rows = db("SELECT username FROM admin_users")
        if admin_rows:
            db_admins = {row[0] for row in admin_rows}

        # Get active sessions (not expired)
        active_rows = db("""
            WITH latest_sessions AS (
                SELECT DISTINCT ON (username)
                    username,
                    created_at as session_start,
                    expires_at,
                    session_token
                FROM user_sessions
                WHERE expires_at > NOW()
                ORDER BY username, created_at DESC
            )
            SELECT * FROM latest_sessions
            ORDER BY session_start DESC
        """)

        # Get recently active sessions (expired in the last 7 days)
        recent_rows = db("""
            WITH latest_sessions AS (
                SELECT DISTINCT ON (username)
                    username,
                    created_at as session_start,
                    expires_at,
                    session_token
                FROM user_sessions
                WHERE expires_at <= NOW()
                  AND expires_at > NOW() - INTERVAL '7 days'
                ORDER BY username, created_at DESC
            )
            SELECT * FROM latest_sessions
            ORDER BY session_start DESC
        """)

        # Process active users
        active_users = []
        active_usernames = set()  # Track active users to exclude from recently active
        if active_rows:
            for row in active_rows:
                username = row[0]
                active_usernames.add(username)
                active_users.append({
                    'username': username,
                    'session_start': row[1].isoformat() if row[1] else None,
                    'session_expires': row[2].isoformat() if row[2] else None,
                    'role': 'admin' if username in local_admins or username in db_admins else 'user'
                })

        # Process recently active users (excluding those who are currently active)
        recent_users = []
        if recent_rows:
            for row in recent_rows:
                username = row[0]
                if username not in active_usernames:  # Only include if not active
                    recent_users.append({
                        'username': username,
                        'session_start': row[1].isoformat() if row[1] else None,
                        'session_expires': row[2].isoformat() if row[2] else None,
                        'role': 'admin' if username in local_admins or username in db_admins else 'user'
                    })

        return jsonify({
            'active_users': active_users,
            'recent_users': recent_users
        }), 200

    except Exception as e:
        logger.error(f"Error getting user sessions summary: {e}")
        return jsonify({"error": "Failed to get user sessions summary"}), 500
