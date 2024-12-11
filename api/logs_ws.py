"""
WebSocket endpoints for log tailing functionality
"""
from flask import Blueprint, current_app
from flask_sock import Sock, ConnectionClosed
from flask_jwt_extended import decode_token
import os
import json
import traceback
from core import logger, rate_limit

# Create blueprint and socket
logs_ws_bp = Blueprint('logs_ws', __name__)
sock = Sock()

@sock.route('/api/v1/logs/tail/<path:log_file>')
def tail_log(ws, log_file):
    """WebSocket endpoint for tailing a log file"""
    client_id = os.urandom(4).hex()  # Generate unique ID for this connection
    logger.info(f"[{client_id}] New WebSocket connection initializing for {log_file}")

    try:
        # Wait for authentication token with timeout
        try:
            logger.debug(f"[{client_id}] Waiting for auth message...")
            auth_message = ws.receive(timeout=5)
            logger.debug(f"[{client_id}] Received auth message")
        except ConnectionClosed as e:
            logger.error(f"[{client_id}] Connection closed during auth: {e}")
            return
        except Exception as e:
            logger.error(f"[{client_id}] Error receiving auth message: {e}")
            logger.error(f"[{client_id}] Traceback: {traceback.format_exc()}")
            return

        try:
            auth_data = json.loads(auth_message)
            token = auth_data.get('token')
            if not token:
                logger.warning(f"[{client_id}] No token provided")
                ws.send('Authentication required')
                return

            # Verify token and check admin role
            try:
                decoded = decode_token(token)
                username = decoded.get('sub', 'unknown')
                role = decoded.get('role', 'none')
                logger.debug(f"[{client_id}] Auth success - User: {username}, Role: {role}")

                if role != 'admin':
                    logger.warning(f"[{client_id}] Non-admin access denied for user: {username}")
                    ws.send('Admin access required')
                    return
            except Exception as e:
                logger.error(f"[{client_id}] Token validation failed: {e}")
                ws.send('Invalid authentication token')
                return

        except json.JSONDecodeError as e:
            logger.error(f"[{client_id}] Invalid auth message format: {e}")
            ws.send('Invalid authentication message format')
            return

        # Basic validation of log file path
        if not log_file or '..' in log_file:
            logger.warning(f"[{client_id}] Invalid log file path: {log_file}")
            ws.send('Invalid log file path')
            return

        # Get absolute path to log file
        log_path = os.path.join('/var/log/pcapserver', log_file)
        if not os.path.exists(log_path):
            logger.warning(f"[{client_id}] Log file not found: {log_path}")
            ws.send(f'Log file not found: {log_file}')
            return

        logger.info(f"[{client_id}] Starting log tail for {log_file}")

        # Open and tail the file
        with open(log_path, 'r') as f:
            # Seek to end
            f.seek(0, 2)
            logger.debug(f"[{client_id}] Seeked to end of {log_file}")

            try:
                while True:
                    try:
                        line = f.readline()
                        if line:
                            ws.send(line.rstrip('\n'))
                        else:
                            # No new lines, wait a bit
                            ws.sleep(1)
                    except ConnectionClosed as e:
                        logger.info(f"[{client_id}] Client disconnected: {e}")
                        return
                    except Exception as e:
                        logger.error(f"[{client_id}] Error sending log line: {e}")
                        return
            except Exception as e:
                logger.error(f"[{client_id}] Error while tailing: {e}")
                logger.error(f"[{client_id}] Traceback: {traceback.format_exc()}")
                ws.send(f"Error: {str(e)}")
                return

    except ConnectionClosed as e:
        logger.error(f"[{client_id}] WebSocket connection closed: {e}")
    except Exception as e:
        logger.error(f"[{client_id}] Unexpected error: {e}")
        logger.error(f"[{client_id}] Traceback: {traceback.format_exc()}")
        try:
            ws.send(f"Error: {str(e)}")
        except:
            pass
    finally:
        logger.info(f"[{client_id}] WebSocket connection closed for {log_file}")
