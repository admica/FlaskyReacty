"""
Subnet mapping endpoints for the PCAP Server API
PATH: api/subnet_mapping.py
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
import re
from datetime import datetime, timezone

from core import logger, db, rate_limit
from api.auth import admin_required

# Create blueprint
subnet_mapping_bp = Blueprint('subnet_mapping', __name__)

def is_valid_subnet(subnet: str) -> bool:
    """Validate subnet format (e.g., '192.168.1.0/24')"""
    try:
        # Split into IP and prefix
        if '/' not in subnet:
            return False
        ip, prefix = subnet.split('/')

        # Validate prefix
        if not prefix.isdigit() or not 0 <= int(prefix) <= 32:
            return False

        # Validate IP format
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        return all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)
    except Exception:
        return False

def is_valid_location(location: str) -> bool:
    """Validate location exists in locations table"""
    try:
        # First check basic format
        if not bool(re.match(r'^[a-zA-Z0-9_]+$', location)):
            return False

        # Then check if location exists in locations table (case insensitive)
        rows = db("SELECT site FROM locations WHERE site = %s", (location,))
        return len(rows) > 0
    except Exception as e:
        logger.error(f"Error validating location: {e}")
        return False

@subnet_mapping_bp.route('/api/v1/admin/subnet_mapping', methods=['POST'])
@jwt_required()
@rate_limit()
@admin_required()
def add_subnet_mapping():
    """Add a new subnet mapping"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate required fields
        required_fields = ['src_subnet', 'dst_subnet', 'src_location', 'dst_location',
                         'first_seen', 'last_seen', 'packet_count']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400

        # Validate subnet formats
        if not is_valid_subnet(data['src_subnet']):
            return jsonify({"error": "Invalid source subnet format"}), 400
        if not is_valid_subnet(data['dst_subnet']):
            return jsonify({"error": "Invalid destination subnet format"}), 400

        # Validate location formats and existence
        if not is_valid_location(data['src_location']):
            return jsonify({"error": "Invalid source location - must be a valid sensor location"}), 400
        if not is_valid_location(data['dst_location']):
            return jsonify({"error": "Invalid destination location - must be a valid sensor location"}), 400

        # Validate timestamps
        if not isinstance(data['first_seen'], int) or not isinstance(data['last_seen'], int):
            return jsonify({"error": "Timestamps must be integers"}), 400
        if data['first_seen'] > data['last_seen']:
            return jsonify({"error": "first_seen cannot be after last_seen"}), 400

        # Validate packet count
        if not isinstance(data['packet_count'], int) or data['packet_count'] < 0:
            return jsonify({"error": "packet_count must be a non-negative integer"}), 400

        # Insert mapping
        db("""
            INSERT INTO subnet_location_map (
                src_subnet,
                dst_subnet,
                src_location,
                dst_location,
                first_seen,
                last_seen,
                packet_count
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (id, last_seen) DO UPDATE SET
                first_seen = LEAST(subnet_location_map.first_seen, EXCLUDED.first_seen),
                packet_count = subnet_location_map.packet_count + EXCLUDED.packet_count,
                last_updated = CURRENT_TIMESTAMP
        """, (
            data['src_subnet'],
            data['dst_subnet'],
            data['src_location'],
            data['dst_location'],
            data['first_seen'],
            data['last_seen'],
            data['packet_count']
        ))

        return jsonify({"message": "Subnet mapping added successfully"}), 201

    except Exception as e:
        logger.error(f"Error adding subnet mapping: {e}")
        return jsonify({"error": "Failed to add subnet mapping"}), 500

@subnet_mapping_bp.route('/api/v1/admin/subnet_mapping', methods=['GET'])
@jwt_required()
@rate_limit()
@admin_required()
def get_subnet_mappings():
    """Get subnet mappings with optional filters"""
    try:
        # Get query parameters
        src_subnet = request.args.get('src_subnet')
        dst_subnet = request.args.get('dst_subnet')
        src_location = request.args.get('src_location')
        dst_location = request.args.get('dst_location')

        # Validate location requirements for subnet searches
        if src_subnet and not src_location:
            return jsonify({"error": "Source location is required when searching by source subnet"}), 400
        if dst_subnet and not dst_location:
            return jsonify({"error": "Destination location is required when searching by destination subnet"}), 400

        # Get canonical location names (preserving case from database)
        src_loc_canonical = None
        dst_loc_canonical = None
        if src_location:
            if not is_valid_location(src_location):
                return jsonify({"error": "Invalid source location"}), 400
            rows = db("SELECT site FROM locations WHERE site = %s", (src_location,))
            src_loc_canonical = rows[0][0] if rows else None

        if dst_location:
            if not is_valid_location(dst_location):
                return jsonify({"error": "Invalid destination location"}), 400
            rows = db("SELECT site FROM locations WHERE site = %s", (dst_location,))
            dst_loc_canonical = rows[0][0] if rows else None

        # Handle subnet search patterns
        if src_subnet and dst_subnet:
            # Pattern 3: Source with specific destination
            if not is_valid_subnet(src_subnet) or not is_valid_subnet(dst_subnet):
                return jsonify({"error": "Invalid subnet format"}), 400

            # Query the subnet_location_map table directly
            query = """
                SELECT DISTINCT
                    src_subnet,
                    dst_subnet,
                    src_location,
                    dst_location,
                    first_seen,
                    last_seen,
                    packet_count
                FROM subnet_location_map
                WHERE src_subnet >>= %s::inet
                AND dst_subnet >>= %s::inet
                AND src_location = %s
                AND dst_location = %s
                AND last_seen >= EXTRACT(EPOCH FROM NOW() - INTERVAL '24 hours')::bigint
            """

            try:
                rows = db(query, [src_subnet, dst_subnet, src_loc_canonical, dst_loc_canonical])
                mappings = [{
                    'src_subnet': str(row[0]),
                    'dst_subnet': str(row[1]),
                    'src_location': row[2],
                    'dst_location': row[3],
                    'first_seen': row[4],
                    'last_seen': row[5],
                    'packet_count': row[6]
                } for row in rows]

                return jsonify({
                    'mappings': mappings,
                    'count': len(mappings)
                }), 200

            except Exception as e:
                logger.error(f"Error querying subnet mappings: {e}")
                return jsonify({"error": "Failed to query subnet mappings"}), 500

        elif src_subnet:
            # Pattern 1: Source-only search
            if not is_valid_subnet(src_subnet):
                return jsonify({"error": "Invalid source subnet format"}), 400

            query = """
                SELECT DISTINCT
                    src_subnet,
                    src_location,
                    first_seen,
                    last_seen,
                    packet_count
                FROM subnet_location_map
                WHERE src_subnet >>= %s::inet
                AND src_location = %s
                AND last_seen >= EXTRACT(EPOCH FROM NOW() - INTERVAL '24 hours')::bigint
            """

            try:
                rows = db(query, [src_subnet, src_loc_canonical])
                mappings = [{
                    'src_subnet': str(row[0]),
                    'location': row[1],
                    'first_seen': row[2],
                    'last_seen': row[3],
                    'packet_count': row[4]
                } for row in rows]

                return jsonify({
                    'mappings': mappings,
                    'count': len(mappings)
                }), 200

            except Exception as e:
                logger.error(f"Error querying source subnet mappings: {e}")
                return jsonify({"error": "Failed to query source subnet mappings"}), 500

        elif dst_subnet:
            # Pattern 2: Destination-only search
            if not is_valid_subnet(dst_subnet):
                return jsonify({"error": "Invalid destination subnet format"}), 400

            query = """
                SELECT DISTINCT
                    dst_subnet,
                    dst_location,
                    first_seen,
                    last_seen,
                    packet_count
                FROM subnet_location_map
                WHERE dst_subnet >>= %s::inet
                AND dst_location = %s
                AND last_seen >= EXTRACT(EPOCH FROM NOW() - INTERVAL '24 hours')::bigint
            """

            try:
                rows = db(query, [dst_subnet, dst_loc_canonical])
                mappings = [{
                    'dst_subnet': str(row[0]),
                    'location': row[1],
                    'first_seen': row[2],
                    'last_seen': row[3],
                    'packet_count': row[4]
                } for row in rows]

                return jsonify({
                    'mappings': mappings,
                    'count': len(mappings)
                }), 200

            except Exception as e:
                logger.error(f"Error querying destination subnet mappings: {e}")
                return jsonify({"error": "Failed to query destination subnet mappings"}), 500

        # If no subnet filters, return location-based summary from materialized view
        if src_location or dst_location:
            query = """
                SELECT
                    src_location,
                    dst_location,
                    unique_src_subnets,
                    unique_dst_subnets,
                    total_packets,
                    earliest_seen,
                    latest_seen
                FROM network_traffic_summary
                WHERE 1=1
            """
            params = []
            if src_loc_canonical:
                query += " AND src_location = %s"
                params.append(src_loc_canonical)
            if dst_loc_canonical:
                query += " AND dst_location = %s"
                params.append(dst_loc_canonical)

            rows = db(query, params)
            mappings = [{
                'src_location': row[0],
                'dst_location': row[1],
                'unique_src_subnets': row[2],
                'unique_dst_subnets': row[3],
                'total_packets': row[4],
                'earliest_seen': row[5],
                'latest_seen': row[6]
            } for row in rows]

            return jsonify({
                'mappings': mappings,
                'count': len(mappings)
            }), 200

        # No filters provided
        return jsonify({
            'mappings': [],
            'count': 0
        }), 200

    except Exception as e:
        logger.error(f"Error getting subnet mappings: {e}")
        return jsonify({"error": "Failed to get subnet mappings"}), 500
