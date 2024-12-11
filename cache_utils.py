import redis
import configparser
import logging
import traceback
from typing import List, Optional

# Setup logging
logger = logging.getLogger(__name__)

# Load config
config = configparser.ConfigParser()
config.read('/opt/pcapserver/config.ini')

# Initialize Redis client
redis_client = redis.Redis(
    host=config.get('REDIS', 'host'),
    port=config.getint('REDIS', 'port'),
    db=config.getint('REDIS', 'db'),
    socket_timeout=config.getint('REDIS', 'sock_timeout'),
    socket_connect_timeout=config.getint('REDIS', 'sock_connect_timeout')
)

# Cache key constants
CACHE_KEYS = {
    'sensors': {
        'admin': 'sensors:admin',
        'user': 'sensors:user'
    },
    'sensor': {
        'admin': lambda name: f"sensor_{name}:admin",
        'user': lambda name: f"sensor_{name}:user"
    },
    'device': {
        'admin': lambda name: f"devices:{name}:admin",
        'user': lambda name: f"devices:{name}:user"
    }
}

def get_cache_key(key_type: str, *args) -> str:
    """Generate a cache key with consistent formatting

    Args:
        key_type: Type of cache key ('sensor', 'device', 'user', 'admin', 'analytics', 'sensors')
        *args: Additional components to build the key

    Returns:
        Formatted cache key string
    """
    valid_types = {'sensor', 'device', 'user', 'admin', 'analytics', 'sensors'}
    if key_type not in valid_types:
        raise ValueError(f"Invalid key type: {key_type}")

    # Special handling for predefined cache keys
    if key_type in CACHE_KEYS:
        role = args[0] if args else 'user'
        if role not in ['admin', 'user']:
            raise ValueError(f"Invalid role: {role}")

        key_template = CACHE_KEYS[key_type][role]
        if callable(key_template):
            if len(args) < 2:
                raise ValueError(f"sensor_name required for key type: {key_type}")
            return key_template(args[1])
        return key_template

    # Dynamic key generation for analytics
    return f"{key_type}:{':'.join(str(arg) for arg in args)}"
def invalidate_caches(sensor_name: Optional[str] = None) -> None:
    """
    Invalidate sensor-related caches.
    Args: sensor_name: Optional specific sensor name to invalidate. If None, only invalidates list caches.
    """
    try:
        keys_to_delete = []

        # Always invalidate main sensors list for both roles
        keys_to_delete.extend([
            get_cache_key('sensors', 'admin'),
            get_cache_key('sensors', 'user')
        ])

        if sensor_name:
            # Invalidate specific sensor and device caches for both roles
            keys_to_delete.extend([
                get_cache_key('sensor', 'admin', sensor_name),
                get_cache_key('sensor', 'user', sensor_name),
                get_cache_key('device', 'admin', sensor_name),
                get_cache_key('device', 'user', sensor_name)
            ])

        # Delete all collected keys if any exist
        if keys_to_delete:
            redis_client.delete(*keys_to_delete)
            logger.debug(f"Cleared cache keys: {keys_to_delete}")

    except Exception as e:
        logger.error(f"Error invalidating sensor caches: {e}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
