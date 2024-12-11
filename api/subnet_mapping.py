"""
Subnet mapping endpoints for the PCAP Server API
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
        rows = db("SELECT site FROM locations WHERE UPPER(site) = UPPER(%s)", (location,))
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
                subnet,
                src_location,
                dst_location,
                first_seen,
                last_seen,
                count
            ) VALUES (
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (subnet, src_location, dst_location)
            DO UPDATE SET
                last_seen = GREATEST(subnet_location_map.last_seen, EXCLUDED.last_seen),
                first_seen = LEAST(subnet_location_map.first_seen, EXCLUDED.first_seen),
                count = EXCLUDED.count
        """, (
            data['src_subnet'],
            data['src_location'],
            data['dst_location'],
            data['first_seen'],
            data['last_seen'],
            data['packet_count']
        ))

        return jsonify({
            "message": "Subnet mapping added successfully",
            "mapping": data
        }), 201

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
            rows = db("SELECT site FROM locations WHERE UPPER(site) = UPPER(%s)", (src_location,))
            src_loc_canonical = rows[0][0] if rows else None

        if dst_location:
            if not is_valid_location(dst_location):
                return jsonify({"error": "Invalid destination location"}), 400
            rows = db("SELECT site FROM locations WHERE UPPER(site) = UPPER(%s)", (dst_location,))
            dst_loc_canonical = rows[0][0] if rows else None

        # Handle subnet search patterns
        if src_subnet and dst_subnet:
            # Pattern 3: Source with specific destination
            if not is_valid_subnet(src_subnet) or not is_valid_subnet(dst_subnet):
                return jsonify({"error": "Invalid subnet format"}), 400
            
            # Query both source and destination location tables
            src_query = f"""
                SELECT DISTINCT subnet, sensor, device
                FROM loc_src_{src_loc_canonical.lower()}
                WHERE subnet >>= %s::inet
            """
            dst_query = f"""
                SELECT DISTINCT subnet, sensor, device
                FROM loc_dst_{dst_loc_canonical.lower()}
                WHERE subnet >>= %s::inet
            """
            
            try:
                src_rows = db(src_query, [src_subnet])
                dst_rows = db(dst_query, [dst_subnet])
            except Exception as e:
                logger.error(f"Error querying location tables: {e}")
                return jsonify({"error": "Failed to query location tables"}), 500

            # Find matching sensor/device pairs
            mappings = []
            for src in src_rows:
                for dst in dst_rows:
                    if src[1] == dst[1] and src[2] == dst[2]:  # Same sensor and device
                        mappings.append({
                            'src_subnet': str(src[0]),
                            'dst_subnet': str(dst[0]),
                            'src_location': src_loc_canonical,
                            'dst_location': dst_loc_canonical,
                            'sensor': src[1],
                            'device': src[2]
                        })
            
            return jsonify({
                'mappings': mappings,
                'count': len(mappings)
            }), 200

        elif src_subnet:
            # Pattern 1: Source-only search
            if not is_valid_subnet(src_subnet):
                return jsonify({"error": "Invalid source subnet format"}), 400
            
            # Query the specific location's source table
            query = f"""
                SELECT DISTINCT subnet, sensor, device
                FROM loc_src_{src_loc_canonical.lower()}
                WHERE subnet >>= %s::inet
            """
            
            try:
                rows = db(query, [src_subnet])
                mappings = [{
                    'src_subnet': str(row[0]),
                    'location': src_loc_canonical,
                    'sensor': row[1],
                    'device': row[2]
                } for row in rows]
                
                return jsonify({
                    'mappings': mappings,
                    'count': len(mappings)
                }), 200

            except Exception as e:
                logger.error(f"Error querying source location table: {e}")
                return jsonify({"error": "Failed to query source location table"}), 500

        elif dst_subnet:
            # Pattern 2: Destination-only search
            if not is_valid_subnet(dst_subnet):
                return jsonify({"error": "Invalid destination subnet format"}), 400
            
            # Query the specific location's destination table
            query = f"""
                SELECT DISTINCT subnet, sensor, device
                FROM loc_dst_{dst_loc_canonical.lower()}
                WHERE subnet >>= %s::inet
            """
            
            try:
                rows = db(query, [dst_subnet])
                mappings = [{
                    'dst_subnet': str(row[0]),
                    'location': dst_loc_canonical,
                    'sensor': row[1],
                    'device': row[2]
                } for row in rows]
                
                return jsonify({
                    'mappings': mappings,
                    'count': len(mappings)
                }), 200

            except Exception as e:
                logger.error(f"Error querying destination location table: {e}")
                return jsonify({"error": "Failed to query destination location table"}), 500

        # If no subnet filters, return location-based summary
        if src_location or dst_location:
            query = """
                SELECT src_location, dst_location, COUNT(*) as count
                FROM subnet_location_map
                WHERE 1=1
            """
            params = []
            if src_loc_canonical:
                query += " AND src_location = %s"
                params.append(src_loc_canonical)
            if dst_loc_canonical:
                query += " AND dst_location = %s"
                params.append(dst_loc_canonical)
            
            query += " GROUP BY src_location, dst_location ORDER BY count DESC LIMIT 100"
            
            rows = db(query, params)
            mappings = [{
                'src_location': row[0],
                'dst_location': row[1],
                'count': row[2]
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