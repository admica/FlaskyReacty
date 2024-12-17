"""
Core shared resources for the PCAP Server API
"""
from functools import wraps
from flask import jsonify, request
import redis
import time
import configparser
import os
from psycopg2.pool import SimpleConnectionPool
from simpleLogger import SimpleLogger
from datetime import datetime, timezone, timedelta
import pytz
from dateutil import parser
import hmac
import hashlib
import urllib.parse
import json
from typing import Dict, Any, List
from decimal import Decimal

# Version info
VERSION = '3.0.0'
BUILD_DATE = '2024-12-11'

# Initialize logger
logger = SimpleLogger('core')

# Server status tracking
server_status = {
    'start_time': datetime.now(timezone.utc).isoformat(),
    'version': VERSION,
    'build_date': BUILD_DATE,
    'state': 'running'
}

# Load and validate configuration
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), 'config.ini')

if not os.path.exists(config_path):
    logger.error(f"Config file not found: {config_path}")
    raise SystemExit("Configuration file not found")

try:
    config.read(config_path)

    # Validate required sections
    required_sections = [
        'JWT', 'DB', 'SERVER', 'STORAGE_PATHS',
        'DOWNLOADS', 'STATUS', 'RESULTS', 'EVENT'
    ]
    missing_sections = [sect for sect in required_sections if sect not in config.sections()]
    if missing_sections:
        raise configparser.Error(f"Missing required sections: {', '.join(missing_sections)}")

    # Load and validate critical values
    PCAP_PATH = os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        config.get('DOWNLOADS', 'pcap_path')
    ))
    # Ensure directory exists
    os.makedirs(PCAP_PATH, exist_ok=True)

    URL_EXPIRATION = 21600  # 6 hours in seconds
    URL_SECRET = config.get('SERVER', 'secret_key')
    if not URL_SECRET: raise ValueError("Server secret key not configured")

    # Validate database configuration
    db_config = {
        'host': config.get('DB', 'hostname'),
        'database': config.get('DB', 'database'),
        'user': config.get('DB', 'username'),
        'password': config.get('DB', 'password'),
        'min': config.getint('DB', 'pool_min'),
        'max': config.getint('DB', 'pool_max')
    }
    if not all(db_config.values()): raise ValueError("Invalid database configuration")

    # Initialize database pool
    db_pool = SimpleConnectionPool(
        db_config['min'],
        db_config['max'],
        host=db_config['host'],
        database=db_config['database'],
        user=db_config['user'],
        password=db_config['password']
    )

    # Load status mappings
    STATUS = {
        'Submitted': str(config.get('STATUS', 'Submitted')),
        'Running': str(config.get('STATUS', 'Running')),
        'Retrieving': str(config.get('STATUS', 'Retrieving')),
        'Merging': str(config.get('STATUS', 'Merging')),
        'Complete': str(config.get('STATUS', 'Complete')),
        'Incomplete': str(config.get('STATUS', 'Incomplete')),
        'Cancelled': str(config.get('STATUS', 'Cancelled'))
    }
    if not all(STATUS.values()): raise ValueError("Invalid status configuration")

    RESULTS = {
        'No-data': str(config.get('RESULTS', 'No-data')),
        'Data': str(config.get('RESULTS', 'Data'))
    }
    if not all(RESULTS.values()):
        raise ValueError("Invalid results configuration")

except (configparser.Error, ValueError) as e:
    logger.error(f"Configuration error: {e}")
    raise SystemExit(f"Failed to load configuration: {e}")

except Exception as e:
    logger.error(f"Unexpected error loading configuration: {e}")
    raise SystemExit("Failed to initialize core components")

def rate_limit():
    """Rate limiting decorator"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get client IP
            client_ip = request.remote_addr

            # Create rate limit key
            endpoint = request.endpoint or 'unknown'
            rate_limit_key = f"rate_limit:{client_ip}:{endpoint}"

            try:
                from cache_utils import redis_client
                # Check rate limit
                attempts = int(redis_client.get(rate_limit_key) or 0)
                if attempts >= 3000:  # Allow more requests
                    remaining = redis_client.ttl(rate_limit_key)
                    return jsonify({
                        "error": "Rate limit exceeded",
                        "retry_after_seconds": remaining
                    }), 429

                # Increment counter with shorter window
                pipe = redis_client.pipeline()
                pipe.incr(rate_limit_key)
                pipe.expire(rate_limit_key, 300) # 5 mins
                pipe.execute()

            except Exception as e:
                logger.error(f"Rate limit error: {e}")
                # Continue if Redis fails
                pass

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def db(sql, params=None, max_retries=3):
    """Execute database query using connection pool"""
    conn = None
    results = None
    for attempt in range(max_retries):
        try:
            conn = db_pool.getconn()
            with conn.cursor() as cur:
                expanded_sql = cur.mogrify(sql, params).decode('utf-8')
                logger.debug(f'DB: EXECUTING EXPANDED SQL: {expanded_sql}')

                cur.execute(sql, params)
                if sql.strip().upper().startswith('SELECT'):
                    results = cur.fetchall()
                    logger.debug(f'DB: RESULTS={results}')
                elif 'RETURNING' in sql.upper():
                    results = cur.fetchone()
                    logger.debug(f'DB: RETURNING={results}')
                    conn.commit()
                else:
                    conn.commit()
                    logger.debug(f'DB: COMMITTED')
                break
        except Exception as e:
            if attempt >= max_retries:
                logger.error(f"DB ERROR: {e}")
                raise
            attempt += 1
            logger.warning(f"DB RETRY {attempt}/{max_retries} AFTER: {e}")
            time.sleep(1)
        finally:
            if conn: db_pool.putconn(conn)
    return results

def parse_and_convert_to_utc(time_str, tz_str):
    """Convert time string to UTC datetime"""
    if not time_str:
        return None

    try:
        # Try to parse as epoch time
        epoch_time = float(time_str)
        return datetime.fromtimestamp(epoch_time, pytz.UTC)
    except ValueError:
        try:
            # Parse the string format
            dt = parser.parse(time_str)
            if dt.tzinfo is None:
                # If no timezone info, assume it's in the specified timezone
                if tz_str.startswith('UTC'):
                    tz_str = tz_str[3:]  # Remove 'UTC' prefix
                if tz_str:
                    sign = 1 if tz_str[0] == '+' else -1
                    hours, minutes = map(int, tz_str[1:].split(':'))
                    tz = pytz.FixedOffset(sign * (hours * 60 + minutes))
                else:
                    tz = pytz.UTC
                dt = tz.localize(dt)
            return dt.astimezone(pytz.UTC)
        except (ValueError, IndexError):
            return None

def generate_signed_url(file_path, file_type):
    """Generate signed URL for file download"""
    try:
        from uuid import uuid4
        from cache_utils import redis_client

        file_id = str(uuid4())
        expires = int(time.time()) + URL_EXPIRATION
        signature_base = f"{file_id}:{file_path}:{expires}"

        # Generate signature
        signature = hmac.new(
            URL_SECRET.encode(),
            signature_base.encode(),
            hashlib.sha256
        ).hexdigest()

        # Store URL info in Redis
        url_info = {
            'file_path': file_path,
            'file_type': file_type,
            'expires': expires
        }
        redis_client.setex(f"signed_url:{file_id}", URL_EXPIRATION, json.dumps(url_info))

        # Generate URL
        params = {
            'id': file_id,
            'expires': expires,
            'signature': signature
        }
        url = f"/api/v1/files/download?{urllib.parse.urlencode(params)}"

        return {
            'url': url,
            'expires_at': datetime.fromtimestamp(expires).isoformat(),
            'filename': os.path.basename(file_path)
        }

    except Exception as e:
        logger.error(f"Error generating signed URL: {e}")
        return None

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Decimal types"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)
