"""
Authentication endpoints and functionality for the PCAP Server API
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

    # Check test user credentials
    try:
        test_username = config.get('TEST_USER', 'username')
        test_password = config.get('TEST_USER', 'password')
        if username == test_username and password == test_password:
            logger.debug("Test user authentication successful")
            return True
    except:
        pass

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
        # Check test user first
        test_username = config.get('TEST_USER', 'username')
        test_role = config.get('TEST_USER', 'role', fallback='admin')

        if username == test_username:
            logger.debug(f"Test user {username} assigned role: {test_role}")
            return test_role

        # Check admin_users table for role
        result = db("SELECT EXISTS(SELECT 1 FROM admin_users WHERE username = %s)", (username,))
        is_admin = result[0][0] if result else False

        role = 'admin' if is_admin else 'user'
        logger.debug(f"User {username} assigned role: {role}")
        return role

    except Exception as e:
        logger.error(f"Error getting user role: {e}")
        return 'user'  # Default to regular user on error

def create_user_session(username):
    """Create a new user session and return the session token"""
    try:
        session_token = str(uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)  # 30 day expiry

        # Insert new session record
        result = db("""
            INSERT INTO user_sessions (username, session_token, expires_at)
            VALUES (%s, %s, %s)
            RETURNING session_token
        """, (username, session_token, expires_at))

        if result and result[0]:
            logger.info(f"Created new session for user: {username}")
            return result[0][0]

        logger.error(f"Failed to create session for user: {username}")
        return None

    except Exception as e:
        logger.error(f"Error creating user session: {e}")
        return None

def cleanup_old_sessions():
    """Clean up expired sessions"""
    try:
        db("""
            DELETE FROM user_sessions
            WHERE expires_at < NOW()
        """)
        logger.debug("Cleaned up expired user sessions")
    except Exception as e:
        logger.error(f"Error cleaning up sessions: {e}")

def update_user_activity(username):
    """Update user's session expiry"""
    try:
        # First try to update existing session
        new_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
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

        logger.debug(f"Updated session expiry for user: {username}")
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

        # Clean username if domain provided
        if '\\' in username:
            username = username.split('\\')[-1]

        # Rate limiting check
        rate_limit_key = f"login_attempts:{username}"
        attempts = int(redis_client.get(rate_limit_key) or 0)
        if attempts >= 5:  # Max 5 attempts per 15 minutes
            remaining = redis_client.ttl(rate_limit_key)
            return jsonify({
                "error": "Too many login attempts",
                "retry_after_seconds": remaining
            }), 429

        user_authenticated = False
        role = None

        # Check local users first
        try:
            local_users = config.items('LOCAL_USERS')
            for username_key, user_json in local_users:
                user = json.loads(user_json)
                if user['username'].lower() == username.lower():
                    if bcrypt.checkpw(password.encode(), user['password'].encode()):
                        user_authenticated = True
                        role = user.get('role', 'user')
                        break
        except Exception as e:
            logger.error(f"Local authentication error: {e}")

        # If not found locally, try LDAP
        if not user_authenticated:
            if ldap_authenticate(username, password):
                user_authenticated = True
                role = get_user_role(username)

        if user_authenticated and role:
            # First cleanup any existing sessions
            db("""
                DELETE FROM user_sessions
                WHERE username = %s
            """, (username,))

            # Generate tokens
            refresh_token = create_refresh_token(identity=username)
            access_token = create_access_token(
                identity=username,
                additional_claims={'role': role}
            )

            # Store refresh token
            refresh_expires = int(config.get('JWT', 'refresh_token_expires'))
            redis_client.setex(
                f"refresh_token:{username}",
                refresh_expires,
                refresh_token
            )

            # Reset failed login attempts
            redis_client.delete(rate_limit_key)

            # Create user session
            session_id = create_user_session(username)
            if not session_id:
                logger.error(f"Failed to create session for user: {username}")

            logger.info(f"Successful login for user: {username}")
            return jsonify({
                'access_token': access_token,
                'refresh_token': refresh_token,
                'role': role
            }), 200

        # Increment failed login attempts
        pipe = redis_client.pipeline()
        pipe.incr(rate_limit_key)
        pipe.expire(rate_limit_key, 900)  # 15 minutes expiry
        pipe.execute()

        logger.warning(f"Failed login attempt for user: {username}")
        return jsonify({"error": "Invalid credentials"}), 401

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({"error": "Authentication failed"}), 500

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
