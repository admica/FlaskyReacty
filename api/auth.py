"""
Authentication endpoints and functionality for the PCAP Server API
PATH: api/auth.py
"""
from flask import Blueprint, jsonify, request, Response
from flask_jwt_extended import (
    jwt_required, create_access_token,
    create_refresh_token, get_jwt_identity, get_jwt
)
import ldap
import bcrypt
from datetime import datetime, timezone, timedelta
import json
import time
import hmac
import hashlib
from uuid import uuid4
from functools import wraps
import traceback

from core import logger, db, rate_limit, config
from cache_utils import redis_client

auth_bp = Blueprint('auth', __name__)

def admin_required():
    """Decorator to check for admin role in JWT token"""
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            claims = get_jwt()
            if claims.get('role') != 'admin':
                logger.warning(f"Admin access denied for user: {get_jwt_identity()}")
                return jsonify({"error": "Admin access required"}), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper

def ldap_authenticate(username, password):
    """Authenticate user against LDAP server"""
    logger.debug(f"Attempting LDAP authentication for user: {username}")

    LDAP_SERVERS = [value for name, value in config.items('LDAP_SERVERS')]
    LDAP_PORT = config.getint('AUTH', 'ldap_port')
    LDAP_BIND_DN = str(config.get('AUTH', 'ldap_bind_dn'))
    LDAP_BIND_PASSWORD = str(config.get('AUTH', 'ldap_bind_password'))
    LDAP_SEARCH_BASE = str(config.get('AUTH', 'ldap_search_base'))
    LDAP_SEARCH_FILTER = str(config.get('AUTH', 'ldap_search_filter'))

    for server in LDAP_SERVERS:
        try:
            url = f'ldaps://{server}:{LDAP_PORT}'
            search_filter = f'({LDAP_SEARCH_FILTER}={username})'

            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
            ldap_client = ldap.initialize(url)
            ldap_client.set_option(ldap.OPT_REFERRALS, 0)

            # Bind and search for user
            ldap_client.simple_bind_s(LDAP_BIND_DN, LDAP_BIND_PASSWORD)
            result = ldap_client.search_s(LDAP_SEARCH_BASE, ldap.SCOPE_SUBTREE, search_filter)

            if result:
                user_dn = result[0][0]
                ldap_client.simple_bind_s(user_dn, password)
                ldap_client.unbind_s()
                logger.info(f"LDAP authentication successful for {username}")
                return True

        except ldap.INVALID_CREDENTIALS:
            logger.warning(f"Invalid credentials for {username}")
            return False
        except ldap.LDAPError as e:
            logger.error(f"LDAP error with server {server}: {e}")
            continue
        finally:
            if 'ldap_client' in locals():
                try:
                    ldap_client.unbind_s()
                except:
                    pass

    return False

def get_user_role(username):
    """Get user role from config or database"""
    try:
        # Check test users first if test mode is enabled
        if config.getboolean('TEST_MODE', 'allow_test_login', fallback=False):
            test_users = config.items('TEST_USERS')
            for _, user_json in test_users:
                try:
                    user_data = json.loads(user_json)
                    if username == user_data.get('username'):
                        role = user_data.get('role', 'user')
                        logger.debug(f"Test user {username} assigned role: {role}")
                        return role
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in TEST_USERS config")
                    continue

        # Check if user is a local user
        local_users = config.items('LOCAL_USERS')
        for local_username, user_json in local_users:
            try:
                user_data = json.loads(user_json)
                if username == user_data.get('username'):
                    role = user_data.get('role', 'user')
                    logger.debug(f"Local user {username} assigned role: {role}")
                    return role
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in LOCAL_USERS config for {local_username}")
                continue

        # If not a local user, check admin_users table for LDAP user role
        result = db("SELECT EXISTS(SELECT 1 FROM admin_users WHERE username = %s)", (username,))
        is_admin = result[0][0] if result else False

        role = 'admin' if is_admin else 'user'
        logger.debug(f"LDAP user {username} assigned role: {role}")
        return role

    except Exception as e:
        logger.error(f"Error getting user role: {e}")
        return 'user'  # Default to regular user on error

def create_user_session(username):
    """Create a new user session and return the session token"""
    try:
        session_token = str(uuid4())
        logger.debug(f"Generated session token: {session_token}")
        retention_days = config.getint('SERVER', 'user_sessions_keep_days', fallback=30)
        expires_at = datetime.now(timezone.utc) + timedelta(days=retention_days)

        # Insert new session record
        db("""
            INSERT INTO user_sessions (username, session_token, expires_at)
            VALUES (%s, %s, %s)
        """, (username, session_token, expires_at))

        logger.info(f"Created new session for user: {username} with token {session_token} (expires in {retention_days} days)")
        return session_token

    except Exception as e:
        logger.error(f"Error creating user session: {e}")
        return None

def cleanup_old_sessions():
    """Clean up expired sessions and sessions older than configured retention period"""
    try:
        # Get retention period from config
        retention_days = config.getint('SERVER', 'user_sessions_keep_days', fallback=30)

        result = db("""
            WITH deleted_sessions AS (
                DELETE FROM user_sessions
                WHERE expires_at < NOW() 
                   OR created_at < NOW() - INTERVAL '%s days'
                RETURNING id
            )
            SELECT COUNT(*) FROM deleted_sessions
        """, [retention_days])

        deleted_count = result[0][0] if result and result[0] else 0

        if deleted_count > 0:
            # Log maintenance operation
            db("""
                INSERT INTO maintenance_operations 
                (timestamp, operation_type, items_processed, items_removed, details)
                VALUES (
                    NOW(),
                    'session_cleanup',
                    %s,
                    %s,
                    jsonb_build_object(
                        'reason', 'Automated cleanup of expired and old sessions',
                        'retention_days', %s
                    )
                )
            """, [deleted_count, deleted_count, retention_days])

            logger.info(f"Cleaned up {deleted_count} expired or old user sessions (retention: {retention_days} days)")
        else:
            logger.debug(f"No sessions needed cleanup (retention: {retention_days} days)")

    except Exception as e:
        logger.error(f"Error cleaning up sessions: {e}")
        logger.error(traceback.format_exc())

def update_user_activity(username):
    """Update user's session expiry"""
    try:
        # Get retention period from config
        retention_days = config.getint('SERVER', 'user_sessions_keep_days', fallback=30)
        new_expires_at = datetime.now(timezone.utc) + timedelta(days=retention_days)

        # First try to update existing session
        result = db("""
            UPDATE user_sessions
            SET expires_at = %s
            WHERE username = %s
            RETURNING id
        """, (new_expires_at, username))

        # If no session exists, create a new one
        if not result:
            session_token = str(uuid4())
            db("""
                INSERT INTO user_sessions (username, session_token, expires_at)
                VALUES (%s, %s, %s)
            """, (username, session_token, new_expires_at))

        logger.debug(f"Updated session expiry for user: {username} (expires in {retention_days} days)")
    except Exception as e:
        logger.error(f"Error updating user session: {e}")

def activity_tracking():
    """Decorator to track user activity in user_sessions table"""
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            try:
                username = get_jwt_identity()
                if username:
                    update_user_activity(username)
            except Exception as e:
                logger.error(f"Error tracking user activity: {e}")
            return fn(*args, **kwargs)
        return decorator
    return wrapper

def check_if_token_revoked(jwt_header, jwt_payload):
    """Callback to check if a token has been revoked"""
    jti = jwt_payload['jti']
    token_in_redis = redis_client.get(f'revoked_token:{jti}')
    return token_in_redis is not None

@auth_bp.route('/api/v1/logout', methods=['POST'])
@jwt_required()
@rate_limit()
def logout():
    """Logout user and invalidate their tokens"""
    try:
        # Get current token info
        jwt_claims = get_jwt()
        jti = jwt_claims['jti']
        username = get_jwt_identity()

        logger.debug(f"Logging out user {username} with token {jti}")

        # Add token to blacklist with same expiry as token
        token_exp = jwt_claims['exp']
        token_ttl = token_exp - int(time.time())
        if token_ttl > 0:
            redis_client.setex(
                f'revoked_token:{jti}',
                token_ttl,
                '1'
            )
            logger.debug(f"Added token {jti} to blocklist with TTL {token_ttl}")

        # Remove refresh token
        redis_client.delete(f"refresh_token:{username}")

        # Remove user session
        db("""
            DELETE FROM user_sessions
            WHERE username = %s
        """, (username,))

        logger.info(f"User logged out: {username}")
        return jsonify({"message": "Successfully logged out"}), 200

    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({"error": "Logout failed"}), 500

@auth_bp.route('/api/v1/login', methods=['POST'])
@rate_limit()
def login():
    """Authenticate user and issue JWT tokens"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        username = data.get('username', '').strip().lower()
        password = data.get('password', '').strip()

        if not username or not password:
            return jsonify({"error": "Username and password required"}), 400

        # First check test users if test mode is enabled
        if config.getboolean('TEST_MODE', 'allow_test_login', fallback=False):
            try:
                test_users = config.items('TEST_USERS')
                for _, user_json in test_users:
                    try:
                        user_data = json.loads(user_json)
                        if username == user_data.get('username') and password == user_data.get('password'):
                            logger.info(f"Test user authentication successful: {username}")
                            role = user_data.get('role', 'user')
                            # Create session first to include token in JWT
                            session_token = create_user_session(username)
                            logger.debug(f"Got session token from create_user_session: {session_token}")
                            if not session_token:
                                return jsonify({"error": "Failed to create session"}), 500

                            # Create tokens with session info
                            access_token = create_access_token(
                                identity=username,
                                additional_claims={
                                    'role': role,
                                    'session_token': session_token
                                }
                            )
                            refresh_token = create_refresh_token(identity=username)

                            response_data = {
                                'access_token': access_token,
                                'refresh_token': refresh_token,
                                'session_token': session_token,
                                'role': role
                            }
                            logger.debug(f"Login response data: {response_data}")
                            return jsonify(response_data), 200
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in TEST_USERS config")
                        continue
            except Exception as e:
                logger.warning(f"Error checking test users: {e}")

        # Then try local user authentication
        local_users = config.items('LOCAL_USERS')
        for local_username, user_json in local_users:
            try:
                user_data = json.loads(user_json)
                if username == user_data.get('username'):
                    stored_password = user_data.get('password')
                    if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
                        logger.info(f"Local user authentication successful: {username}")
                        role = user_data.get('role', 'user')
                        # Create session first to include token in JWT
                        session_token = create_user_session(username)
                        if not session_token:
                            return jsonify({"error": "Failed to create session"}), 500

                        # Create tokens with session info
                        access_token = create_access_token(
                            identity=username,
                            additional_claims={
                                'role': role,
                                'session_token': session_token
                            }
                        )
                        refresh_token = create_refresh_token(identity=username)

                        return jsonify({
                            'access_token': access_token,
                            'refresh_token': refresh_token,
                            'session_token': session_token,
                            'role': role
                        }), 200
                    else:
                        logger.warning(f"Invalid password for local user: {username}")
                        return jsonify({"error": "Invalid credentials"}), 401
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in LOCAL_USERS config for {local_username}")
                continue

        # If not a local user, try LDAP authentication
        if ldap_authenticate(username, password):
            # Get role from admin_users table for LDAP users
            role = get_user_role(username)

            # Create session first to include token in JWT
            session_token = create_user_session(username)
            if not session_token:
                return jsonify({"error": "Failed to create session"}), 500

            # Create tokens with session info
            access_token = create_access_token(
                identity=username,
                additional_claims={
                    'role': role,
                    'session_token': session_token
                }
            )
            refresh_token = create_refresh_token(identity=username)

            return jsonify({
                'access_token': access_token,
                'refresh_token': refresh_token,
                'session_token': session_token,
                'role': role
            }), 200

        return jsonify({"error": "Invalid credentials"}), 401

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"error": "Login failed"}), 500

@auth_bp.route('/api/v1/refresh', methods=['POST'])
@jwt_required(refresh=True)
@rate_limit()
def refresh():
    """Issue new access token using refresh token"""
    try:
        # Get identity from refresh token
        current_user = get_jwt_identity()

        # Clean up old sessions periodically
        cleanup_old_sessions()

        # Update current user's activity
        update_user_activity(current_user)

        # Get stored refresh token
        stored_token = redis_client.get(f"refresh_token:{current_user}")
        if not stored_token:
            return jsonify({"error": "Invalid refresh token"}), 401

        # Get user role
        role = get_user_role(current_user)

        # Create new access token
        new_access_token = create_access_token(
            identity=current_user,
            additional_claims={'role': role}
        )

        # Create new refresh token
        new_refresh_token = create_refresh_token(identity=current_user)

        # Store new refresh token
        refresh_expires = int(config.get('JWT', 'refresh_token_expires'))
        redis_client.setex(
            f"refresh_token:{current_user}",
            refresh_expires,
            new_refresh_token
        )

        return jsonify({
            'access_token': new_access_token,
            'refresh_token': new_refresh_token,
            'role': role
        }), 200

    except Exception as e:
        logger.error(f"Refresh error: {e}")
        return jsonify({"error": "Token refresh failed"}), 500

@auth_bp.route('/api/v1/users/sessions', methods=['GET'])
@jwt_required()
@rate_limit()
def get_user_sessions():
    """Get list of active sessions for the current user or all users if admin"""
    try:
        username = get_jwt_identity()
        jwt_claims = get_jwt()
        current_session = jwt_claims.get('session_token')
        role = jwt_claims.get('role', 'user')
        logger.debug(f"User sessions request - username: {username}, role: {role}, session: {current_session}, claims: {jwt_claims}")

        # Get all sessions from the last 7 days
        # If admin, get all users' sessions, otherwise just the current user's
        query = """
            SELECT 
                username,
                created_at,
                expires_at,
                session_token
            FROM user_sessions
            WHERE created_at > NOW() - INTERVAL '7 days'
            {}
            ORDER BY created_at DESC
        """
        
        if role != 'admin':
            query = query.format("AND username = %s")
            rows = db(query, [username]) or []
        else:
            query = query.format("")
            rows = db(query) or []

        # Format sessions
        sessions = [{
            'username': row[0],
            'created_at': row[1].isoformat() if row[1] else None,
            'expires_at': row[2].isoformat() if row[2] else None,
            'is_current': current_session == row[3],
            'role': get_user_role(row[0])  # Get the correct role for each user
        } for row in rows]

        return jsonify({
            'sessions': sessions
        }), 200

    except Exception as e:
        logger.error(f"Error getting user sessions: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": "Failed to get user sessions"}), 500
