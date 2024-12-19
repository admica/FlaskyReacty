"""
IP search endpoints for the PCAP Server API
"""
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from typing import List
import re
import time

# Import shared resources
from simpleLogger import SimpleLogger
from core import db, rate_limit

# Initialize logger
logger = SimpleLogger('search')

# Create blueprint
search_bp = Blueprint('search', __name__)

def ensure_test_tables_exist():
    """Ensure test location tables exist"""
    try:
        for table_type in ['src', 'dst']:
            # Create table if it doesn't exist
            db(f"""CREATE TABLE IF NOT EXISTS loc_{table_type}_test (
                subnet cidr PRIMARY KEY,
                count bigint NOT NULL DEFAULT 0,
                first_seen bigint,
                last_seen bigint,
                sensor varchar(255),
                device varchar(255)
            )""")

            # Check if table exists and has data
            table_exists = db("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = %s
                    AND table_schema = 'public'
                )
            """, (f'loc_{table_type}_test',))[0][0]

            if not table_exists:
                logger.error(f"Failed to create table loc_{table_type}_test")
                return False

            # Check if table is empty
            count = db(f"SELECT COUNT(*) FROM loc_{table_type}_test")[0][0]
            if count == 0:
                # Insert test data with UNIX timestamps
                current_time = int(time.time())

                # Use test data from config
                if table_type == 'src':
                    test_subnets = [
                        ('192.168.1.0/24', 'test_sensor1', 'napa0'),  # For test case 1
                        ('172.16.0.0/24', 'test_sensor2', 'napa0'),   # For test case 3
                        ('10.0.0.0/24', 'test_sensor3', 'napa1')      # For test case 4
                    ]
                else:
                    test_subnets = [
                        ('10.1.0.0/24', 'test_sensor1', 'napa0'),     # For test case 2
                        ('192.168.2.0/24', 'test_sensor2', 'napa0'),  # For test case 3
                        ('172.16.1.0/24', 'test_sensor3', 'napa1')    # For test case 4
                    ]

                try:
                    for subnet, sensor, device in test_subnets:
                        # Insert test data with transaction
                        db(f"""
                            BEGIN;
                            INSERT INTO loc_{table_type}_test
                            (subnet, count, first_seen, last_seen, sensor, device)
                            VALUES
                            (%s, 100, %s, %s, %s, %s)
                            ON CONFLICT (subnet) DO UPDATE
                            SET count = loc_{table_type}_test.count + 100,
                                last_seen = EXCLUDED.last_seen;
                            COMMIT;
                        """, (subnet, current_time - 3600, current_time, sensor, device))

                        # Verify data was inserted
                        verify = db(f"""
                            SELECT COUNT(*)
                            FROM loc_{table_type}_test
                            WHERE subnet = %s::cidr
                        """, (subnet,))[0][0]

                        if verify == 0:
                            logger.error(f"Failed to verify test data for {table_type} subnet {subnet}")
                            return False

                except Exception as e:
                    logger.error(f"Error inserting test data for {table_type}: {str(e)}")
                    return False

        return True

    except Exception as e:
        logger.error(f"Error ensuring test tables exist: {str(e)}")
        return False

def get_location_tables(search_type='src') -> List[str]:
    """Get list of location tables for a search type"""
    rows = db("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name LIKE %s
        AND table_schema = 'public'
    """, (f'loc_{search_type}_%',))
    return [row[0] for row in rows]

def is_valid_ip(ip):
    """Validate IP address format"""
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        return False
    return all(0 <= int(part) <= 255 for part in ip.split('.'))

@search_bp.route('/api/v1/search/ip', methods=['POST'])
@jwt_required()
@rate_limit()
def search_ip():
    """Search for an IP address or IP pair across location tables"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate input
        src_ip = data.get('src_ip')
        dst_ip = data.get('dst_ip')
        start_time = data.get('start_time')  # Optional timestamp
        end_time = data.get('end_time')      # Optional timestamp

        # Convert timestamps if provided
        try:
            start_ts = int(start_time) if start_time else None
            end_ts = int(end_time) if end_time else None
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid timestamp format: {e}")
            return jsonify({"error": "Invalid timestamp format"}), 400

        # Validate at least one IP is provided
        if not src_ip and not dst_ip:
            return jsonify({"error": "At least one IP (source or destination) is required"}), 400

        # Validate IP formats
        if src_ip and not is_valid_ip(src_ip):
            return jsonify({"error": "Invalid source IP format"}), 400
        if dst_ip and not is_valid_ip(dst_ip):
            return jsonify({"error": "Invalid destination IP format"}), 400

        # Get all location tables
        src_tables = get_location_tables('src') if src_ip else []
        dst_tables = get_location_tables('dst') if dst_ip else []

        results = []
        sensor_confidences = {}  # Track confidence per sensor

        if src_ip and dst_ip:
            # Search for source-destination pairs
            for loc in set(t.replace('loc_src_', '') for t in src_tables):
                src_matches = []
                dst_matches = []

                # Search source table for this location
                src_table = f'loc_src_{loc}'
                try:
                    src_rows = db(f"""
                        SELECT subnet, count, first_seen, last_seen, sensor, device
                        FROM {src_table}
                        WHERE subnet >>= %s::inet
                    """, (src_ip,))
                    src_matches.extend(src_rows)
                except Exception as e:
                    logger.error(f"Error searching {src_table}: {e}")
                    continue

                # Search destination table for this location
                dst_table = f'loc_dst_{loc}'
                try:
                    dst_rows = db(f"""
                        SELECT subnet, count, first_seen, last_seen, sensor, device
                        FROM {dst_table}
                        WHERE subnet >>= %s::inet
                    """, (dst_ip,))
                    dst_matches.extend(dst_rows)
                except Exception as e:
                    logger.error(f"Error searching {dst_table}: {e}")
                    continue

                # Find matching sensor/device pairs in this location
                for src in src_matches:
                    for dst in dst_matches:
                        if src[4] == dst[4] and src[5] == dst[5]:  # Same sensor and device
                            sensor_name = src[4]
                            match = {
                                'location': loc,
                                'sensor': sensor_name,
                                'device': src[5],
                                'src_subnet': str(src[0]),
                                'dst_subnet': str(dst[0]),
                                'src_count': src[1],
                                'dst_count': dst[1],
                                'src_first_seen': src[2],
                                'src_last_seen': src[3],
                                'dst_first_seen': dst[2],
                                'dst_last_seen': dst[3]
                            }

                            # Calculate confidence for this sensor
                            if start_ts or end_ts:
                                src_in_range = (not start_ts or src[2] <= start_ts) and (not end_ts or src[3] >= end_ts)
                                dst_in_range = (not start_ts or dst[2] <= start_ts) and (not end_ts or dst[3] >= end_ts)

                                if src_in_range and dst_in_range:
                                    sensor_confidences[sensor_name] = {
                                        "level": "high",
                                        "reason": "Data spans entire timeframe"
                                    }
                                else:
                                    sensor_confidences[sensor_name] = {
                                        "level": "low",
                                        "reason": "Data does not span entire timeframe"
                                    }
                            else:
                                sensor_confidences[sensor_name] = {
                                    "level": "high",
                                    "reason": "No timeframe specified"
                                }

                            results.append(match)

        else:
            # Single IP search
            tables = src_tables if src_ip else dst_tables
            search_ip = src_ip if src_ip else dst_ip

            for table in tables:
                loc = table.replace('loc_src_', '').replace('loc_dst_', '')
                quoted_table = f'"{table}"'
                try:
                    rows = db(f"""
                        SELECT subnet, count, first_seen, last_seen, sensor, device
                        FROM {quoted_table}
                        WHERE subnet >>= %s::inet
                    """, (search_ip,))

                    for row in rows:
                        sensor_name = row[4]
                        match = {
                            'location': loc,
                            'sensor': sensor_name,
                            'device': row[5],
                            'subnet': str(row[0]),
                            'count': row[1],
                            'first_seen': row[2],
                            'last_seen': row[3]
                        }

                        # Calculate confidence for this sensor
                        if start_ts or end_ts:
                            in_range = (not start_ts or row[2] <= start_ts) and (not end_ts or row[3] >= end_ts)
                            if in_range:
                                sensor_confidences[sensor_name] = {
                                    "level": "high",
                                    "reason": "Data spans entire timeframe"
                                }
                            else:
                                sensor_confidences[sensor_name] = {
                                    "level": "low",
                                    "reason": "Data does not span entire timeframe"
                                }
                        else:
                            sensor_confidences[sensor_name] = {
                                "level": "high",
                                "reason": "No timeframe specified"
                            }

                        results.append(match)
                except Exception as e:
                    logger.error(f"Error searching {table}: {e}")
                    continue

        # Calculate overall confidence
        if not results:
            confidence = {
                "level": "low",
                "reason": "No matches found"
            }
        else:
            # If any sensor has high confidence, overall confidence is high
            high_confidence_sensors = [s for s, c in sensor_confidences.items() if c["level"] == "high"]
            if high_confidence_sensors:
                confidence = {
                    "level": "high",
                    "reason": f"High confidence data from sensor(s): {', '.join(high_confidence_sensors)}"
                }
            else:
                confidence = {
                    "level": "low",
                    "reason": "No sensors with high confidence data"
                }

        # Sort results by last_seen timestamp
        if src_ip and dst_ip:
            results.sort(key=lambda x: max(x['src_last_seen'], x['dst_last_seen']), reverse=True)
        else:
            results.sort(key=lambda x: x['last_seen'], reverse=True)

        return jsonify({
            'src_ip': src_ip,
            'dst_ip': dst_ip,
            'timeframe': {
                'start': start_time,
                'end': end_time
            } if start_time or end_time else None,
            'matches': results,
            'confidence': confidence,
            'sensor_confidences': sensor_confidences
        }), 200

    except Exception as e:
        logger.error(f"Error in search_ip: {str(e)}")
        return jsonify({"error": "Search failed"}), 500
