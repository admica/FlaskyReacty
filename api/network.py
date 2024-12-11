"""
Network visualization endpoints for the PCAP Server API
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from datetime import datetime, timezone
import json

# Import shared resources
from simpleLogger import SimpleLogger
from core import db, rate_limit
from cache_utils import redis_client, get_cache_key

# Initialize logger
logger = SimpleLogger('network')

# Create blueprint
network_bp = Blueprint('network', __name__)

@network_bp.route('/api/v1/network/locations', methods=['GET'])
@jwt_required()
@rate_limit()
def get_locations():
    """Get all NASA center locations"""
    try:
        # Try to get from cache first
        cache_key = get_cache_key('analytics', 'network', 'locations')
        cached_data = redis_client.get(cache_key)

        if cached_data:
            try:
                locations = json.loads(cached_data)
                return jsonify({
                    'locations': locations,
                    'cached': True,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }), 200
            except json.JSONDecodeError:
                # If cache is corrupted, ignore it
                logger.warning("Corrupted cache data for locations")
                redis_client.delete(cache_key)

        # If not in cache, get from database
        try:
            locations = db("""
                SELECT site, name, latitude, longitude, description
                FROM locations
                ORDER BY name
            """)

            if locations is None:
                logger.error("Database query returned None for locations")
                return jsonify({"error": "Database error"}), 500

            # Format the response
            location_list = [{
                'site': loc[0],
                'name': loc[1],
                'latitude': float(loc[2]),
                'longitude': float(loc[3]),
                'description': loc[4]
            } for loc in locations]

            # Cache the results for 1 hour (locations don't change often)
            try:
                redis_client.setex(
                    cache_key,
                    3600,  # 1 hour
                    json.dumps(location_list)
                )
            except Exception as e:
                logger.warning(f"Failed to cache locations: {e}")

            return jsonify({
                'locations': location_list,
                'cached': False,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }), 200

        except Exception as e:
            logger.error(f"Database error getting locations: {e}")
            return jsonify({"error": "Database error"}), 500

    except Exception as e:
        logger.error(f"Error getting locations: {e}")
        return jsonify({"error": "Failed to get location data"}), 500

@network_bp.route('/api/v1/network/connections', methods=['GET'])
@jwt_required()
@rate_limit()
def get_connections():
    """Get all network traffic between locations

    Returns a list of all network connections between locations from the materialized view.
    Each connection includes:
    - src_location: Source location identifier
    - dst_location: Destination location identifier
    - packet_count: Total number of packets for this connection
    - latest_seen: Most recent timestamp this connection was seen
    - earliest_seen: Earliest timestamp this connection was seen

    The data is cached for 1 minute to improve performance.
    Results are ordered by packet count in descending order.
    """
    try:
        # Try to get from cache first
        cache_key = get_cache_key('analytics', 'network', 'connections', 'all')
        cached_data = redis_client.get(cache_key)

        if cached_data:
            try:
                connections = json.loads(cached_data)
                return jsonify({
                    'connections': connections,
                    'cached': True,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }), 200
            except json.JSONDecodeError:
                # If cache is corrupted, ignore it
                logger.warning("Corrupted cache data for connections")
                redis_client.delete(cache_key)

        try:
            # Get all connections from materialized view
            connections = db("""
                SELECT
                    src_location,
                    dst_location,
                    COUNT(*) as unique_subnets,
                    SUM(packet_count) as total_packets,
                    MIN(first_seen) as earliest_seen,
                    MAX(last_seen) as latest_seen
                FROM subnet_location_map
                GROUP BY src_location, dst_location
                ORDER BY total_packets DESC
            """)

            if connections is None:
                logger.error("Database query returned None for connections")
                return jsonify({"error": "Database error"}), 500

            # Format the response
            connection_list = [{
                'src_location': conn[0],
                'dst_location': conn[1],
                'unique_subnets': int(conn[2]) if conn[2] is not None else 0,
                'packet_count': int(conn[3]) if conn[3] is not None else 0,
                'earliest_seen': int(conn[4]) if conn[4] is not None else 0,
                'latest_seen': int(conn[5]) if conn[5] is not None else 0
            } for conn in connections]

            # Cache the results for 1 minute
            try:
                redis_client.setex(
                    cache_key,
                    60,  # 1 minute
                    json.dumps(connection_list)
                )
            except Exception as e:
                logger.warning(f"Failed to cache connections: {e}")

            return jsonify({
                'connections': connection_list,
                'cached': False,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }), 200

        except Exception as e:
            logger.error(f"Database error getting connections: {e}")
            return jsonify({"error": "Database error"}), 500

    except Exception as e:
        logger.error(f"Error getting connections: {e}")
        return jsonify({"error": "Failed to get connection data"}), 500
