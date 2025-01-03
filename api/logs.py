"""
Log management endpoints for the PCAP Server API
PATH: api/logs.py
"""
import os
import glob
from datetime import datetime
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
import configparser
from collections import deque

# Import shared resources
from simpleLogger import SimpleLogger
from core import rate_limit
from api.auth import admin_required

# Initialize logger
logger = SimpleLogger('logs')

# Create blueprint
logs_bp = Blueprint('logs', __name__)

# Load config
config = configparser.ConfigParser()
config.read('/opt/pcapserver/config.ini')
LOG_PATH = config.get('LOG', 'log_path')

def get_log_files():
    """Get list of log files with metadata"""
    log_files = []
    for ext in ['*.log', '*.log.[0-9]*', '*.out', '*.err']:
        pattern = os.path.join(LOG_PATH, ext)
        for file_path in glob.glob(pattern):
            try:
                stats = os.stat(file_path)
                log_files.append({
                    'name': os.path.basename(file_path),
                    'size': stats.st_size,
                    'modified': datetime.fromtimestamp(stats.st_mtime).isoformat()
                })
            except Exception as e:
                logger.error(f"Error getting stats for {file_path}: {e}")
    return sorted(log_files, key=lambda x: x['modified'], reverse=True)

def tail_file(file_path, num_lines=1000):
    """Get the last N lines of a file"""
    try:
        logger.debug(f"Opening file for tailing: {file_path}")
        with open(file_path, 'r') as f:
            logger.debug("File opened successfully, reading lines")
            lines = list(deque(f, num_lines))
            logger.debug(f"Read {len(lines)} lines from file")
            return lines
    except Exception as e:
        logger.error(f"Error tailing file {file_path}: {e}")
        logger.debug(f"Tail file exception details: {type(e).__name__}: {str(e)}")
        return []

@logs_bp.route('/api/v1/logs', methods=['GET'])
@jwt_required()
@admin_required()
@rate_limit()
def list_logs():
    """Get list of available log files"""
    try:
        files = get_log_files()
        return jsonify({
            'files': files,
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Error listing log files: {e}")
        return jsonify({"error": "Failed to list log files"}), 500

@logs_bp.route('/api/v1/logs/<path:log_file>/content', methods=['GET'])
@jwt_required()
@admin_required()
@rate_limit()
def get_log_content(log_file):
    """Get content of a log file"""
    try:
        logger.debug(f"Attempting to get content for log file: {log_file}")

        # Basic validation of log file path
        if not log_file or '..' in log_file:
            logger.debug(f"Invalid log file path detected: {log_file}")
            return jsonify({"error": "Invalid log file path"}), 400

        # Get absolute path to log file
        log_path = os.path.join(LOG_PATH, log_file)
        logger.debug(f"Full log path: {log_path}")

        if not os.path.exists(log_path):
            logger.debug(f"Log file not found at path: {log_path}")
            return jsonify({"error": "Log file not found"}), 404

        # Log file stats
        stats = os.stat(log_path)
        logger.debug(f"Log file size: {stats.st_size} bytes")
        logger.debug(f"Log file permissions: {oct(stats.st_mode)}")

        # Get last 1000 lines by default
        logger.debug("Attempting to read last 1000 lines")
        lines = tail_file(log_path)
        logger.debug(f"Successfully read {len(lines)} lines from log file")

        return jsonify({
            'content': lines,
            'timestamp': datetime.now().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error getting log content: {str(e)}")
        logger.debug(f"Exception details: {type(e).__name__}: {str(e)}")
        return jsonify({"error": "Failed to get log content"}), 500
