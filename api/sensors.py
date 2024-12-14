"""
Sensor management endpoints and functionality for the PCAP Server API
"""
from flask import Blueprint, jsonify, request, Response
from flask_jwt_extended import jwt_required, get_jwt
import re
from typing import List
import json
import traceback
from datetime import datetime, timezone

from core import logger, db, rate_limit, db_pool, config
from api.auth import admin_required, activity_tracking
from cache_utils import redis_client, get_cache_key

sensors_bp = Blueprint('sensors', __name__)

def initialize_sensors_from_config():
    """Initialize sensors from config.ini if they don't exist in database"""
    try:
        logger.info("Initializing sensors from config.ini")

        # Get all sensors from config
        config_sensors = config.items('SENSORS')
        locations = set()

        for sensor_name, sensor_data in config_sensors:
            try:
                # Parse the JSON-like string into a dict
                sensor_info = eval(sensor_data)  # Safe here as we control the config file
                name = sensor_info['name']
                fqdn = sensor_info['fqdn']
                location = sensor_info['location']
                devices = sensor_info['devices']

                locations.add(location) # Add location to set for table creation
                rows = db("SELECT name FROM sensors WHERE name = %s OR fqdn = %s", (name, fqdn))

                if not rows:
                    # Add new sensor
                    db("""
                        INSERT INTO sensors
                        (name, fqdn, status, location)
                        VALUES (%s, %s, 'Online', %s)
                    """, (name, fqdn, location))
                    logger.info(f"Added new sensor: {name} ({fqdn})")

                    # Add initial status history entry for each device
                    for device_name, device_config in devices.items():
                        try:
                            if isinstance(device_config, (str, int)):
                                port = int(device_config)
                            else:
                                port = int(device_config['port'])

                            db("""
                                INSERT INTO sensor_status_history
                                (sensor_fqdn, sensor_port, old_status, new_status)
                                VALUES (%s, %s, NULL, 'Online')
                            """, (fqdn, port))
                            logger.debug(f"Added initial status history for sensor: {name}, port: {port}")
                        except Exception as e:
                            logger.error(f"Error adding status history for device {device_name}: {e}")

                # Add devices if they don't exist
                for device_name, device_config in devices.items():
                    try:
                        # Handle both simple port format and full format
                        if isinstance(device_config, (str, int)):
                            port = int(device_config)
                            device_type = 'pcapCollect' if device_name.startswith('napa') else 'tcpdump'
                        else:
                            port = int(device_config['port'])
                            device_type = device_config['device_type']

                        db("""
                            INSERT INTO devices
                            (sensor, name, port, device_type, fqdn, status)
                            VALUES (%s, %s, %s, %s, %s, 'Online')
                            ON CONFLICT (sensor, name) DO UPDATE SET
                                port = EXCLUDED.port,
                                device_type = EXCLUDED.device_type,
                                fqdn = EXCLUDED.fqdn
                        """, (name, device_name, port, device_type, fqdn))
                    except Exception as e:
                        logger.error(f"Error adding device {device_name} for sensor {name}: {e}")
                        logger.debug(traceback.format_exc())
                        continue

            except Exception as e:
                logger.error(f"Error processing sensor {sensor_name}: {e}")
                logger.debug(traceback.format_exc())
                continue

        # Create location tables
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                for location in locations:
                    try:
                        success, message = create_location_tables(cur, location)
                        if not success:
                            logger.error(f"Failed to create location tables for {location}: {message}")
                    except Exception as e:
                        logger.error(f"Error creating location tables for {location}: {e}")
                        logger.debug(traceback.format_exc())
                        continue
                conn.commit()
        finally:
            db_pool.putconn(conn)

        logger.info("Completed sensor initialization from config.ini")

    except Exception as e:
        logger.error(f"Error initializing sensors: {e}")
        logger.debug(traceback.format_exc())
        raise

def initialize_locations_from_config():
    """Initialize locations from config.ini if they don't exist in database.

    Note:
        Locations are stored with uppercase site identifiers in the locations table,
        but their associated dynamic tables (loc_src_*, loc_dst_*) use lowercase names.
    """
    try:
        logger.info("Initializing locations from config.ini")

        # Get locations from config
        if not config.has_section('LOCATIONS'):
            logger.warning("No LOCATIONS section found in config.ini")
            return

        config_locations = config.items('LOCATIONS')

        for site, location_data in config_locations:
            try:
                # Parse the JSON-like string into a dict
                location_info = eval(location_data)  # Safe here as we control the config file

                # Always store site in uppercase for consistency
                location_info['site'] = site.strip().upper()

                # Validate required fields
                required_fields = ['name', 'latitude', 'longitude']  # site is already handled
                missing_fields = [field for field in required_fields if field not in location_info]
                if missing_fields:
                    logger.error(f"Missing required fields for location {site}: {missing_fields}")
                    continue

                # Check if location exists
                rows = db("SELECT site FROM locations WHERE site = %s", (location_info['site'],))

                if not rows:
                    # Add new location
                    db("""
                        INSERT INTO locations
                        (site, name, latitude, longitude, description, color)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        location_info['site'],
                        location_info['name'],
                        float(location_info['latitude']),
                        float(location_info['longitude']),
                        location_info.get('description', ''),  # Optional field
                        location_info.get('color', '#FFFFFF')  # Optional field, default white
                    ))
                    logger.info(f"Added new location: {location_info['name']} ({location_info['site']})")
                else:
                    # Update existing location if needed
                    db("""
                        UPDATE locations
                        SET name = %s,
                            latitude = %s,
                            longitude = %s,
                            description = %s,
                            color = %s
                        WHERE site = %s
                        AND (
                            name != %s OR
                            latitude != %s OR
                            longitude != %s OR
                            COALESCE(description, '') != COALESCE(%s, '') OR
                            COALESCE(color, '') != COALESCE(%s, '')
                        )
                    """, (
                        location_info['name'],
                        float(location_info['latitude']),
                        float(location_info['longitude']),
                        location_info.get('description', ''),
                        location_info.get('color', '#FFFFFF'),
                        location_info['site'],
                        location_info['name'],
                        float(location_info['latitude']),
                        float(location_info['longitude']),
                        location_info.get('description', ''),
                        location_info.get('color', '#FFFFFF')
                    ))
                    logger.debug(f"Updated location if needed: {location_info['name']} ({location_info['site']})")

            except Exception as e:
                logger.error(f"Error processing location {site}: {e}")
                logger.debug(traceback.format_exc())
                continue

        logger.info("Completed location initialization from config.ini")

    except Exception as e:
        logger.error(f"Error initializing locations: {e}")
        logger.debug(traceback.format_exc())
        raise

# Call initialize_sensors_from_config when the blueprint is registered
@sensors_bp.record_once
def on_blueprint_init(state):
    """Initialize sensors and locations when the blueprint is registered"""
    try:
        initialize_sensors_from_config()
        initialize_locations_from_config()
    except Exception as e:
        logger.error(f"Failed to initialize sensors and locations: {e}")
        # Don't raise the error - allow the app to start even if initialization fails

def create_location_tables(cur, location):
    """Create source and destination subnet tables for a location if they don't exist.

    Args:
        cur: Database cursor
        location: Location identifier (will be converted to lowercase for table names)

    Note:
        This function always creates tables with lowercase names for PostgreSQL compatibility,
        regardless of the input case. The application should handle display case separately.
    """
    try:
        # Always use lowercase for table names (PostgreSQL best practice)
        # Strip whitespace to prevent edge cases
        location = location.strip().lower()
        if not location: return False, "Location name cannot be empty"

        # Validate location name format (alphanumeric and underscores only)
        if not all(c.isalnum() or c == '_' for c in location):
            return False, "Location can only contain letters, numbers, and underscores"

        logger.info(f"Checking/Creating location tables for {location}")

        # Check if tables already exist
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s)", (f'loc_src_{location}',))
        src_exists = cur.fetchone()[0]
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s)", (f'loc_dst_{location}',))
        dst_exists = cur.fetchone()[0]

        # Create source subnet table if it doesn't exist
        if not src_exists:
            logger.debug(f"Creating source subnet table loc_src_{location}")
            cur.execute(f"""
                CREATE TABLE loc_src_{location} (
                    subnet cidr NOT NULL,
                    count bigint NOT NULL DEFAULT 0,
                    first_seen bigint NOT NULL,
                    last_seen bigint NOT NULL,
                    sensor varchar(255) NOT NULL,
                    device varchar(255) NOT NULL,
                    PRIMARY KEY (subnet, sensor, device)
                );
                -- GiST index for efficient subnet lookups
                CREATE INDEX idx_src_{location}_subnet
                ON loc_src_{location} USING gist (subnet inet_ops);
                -- Index for time-based queries and pruning
                CREATE INDEX idx_src_{location}_time
                ON loc_src_{location} (last_seen, first_seen);
            """)

        # Create destination subnet table if it doesn't exist
        if not dst_exists:
            logger.debug(f"Creating destination subnet table loc_dst_{location}")
            cur.execute(f"""
                CREATE TABLE loc_dst_{location} (
                    subnet cidr NOT NULL,
                    count bigint NOT NULL DEFAULT 0,
                    first_seen bigint NOT NULL,
                    last_seen bigint NOT NULL,
                    sensor varchar(255) NOT NULL,
                    device varchar(255) NOT NULL,
                    PRIMARY KEY (subnet, sensor, device)
                );
                -- GiST index for efficient subnet lookups
                CREATE INDEX idx_dst_{location}_subnet
                ON loc_dst_{location} USING gist (subnet inet_ops);
                -- Index for time-based queries and pruning
                CREATE INDEX idx_dst_{location}_time
                ON loc_dst_{location} (last_seen, first_seen);
            """)

        # Set optimal table storage parameters
        if src_exists or dst_exists:
            for prefix in ['src', 'dst']:
                cur.execute(f"""
                    ALTER TABLE loc_{prefix}_{location} SET (
                        autovacuum_vacuum_scale_factor = 0.1,
                        autovacuum_analyze_scale_factor = 0.05,
                        autovacuum_vacuum_threshold = 1000,
                        autovacuum_analyze_threshold = 1000
                    );
                """)

        tables_created = (not src_exists) or (not dst_exists)
        if tables_created:
            logger.info(f"Successfully created missing subnet tables for location: {location}")
        else:
            logger.debug(f"Subnet tables already exist for location: {location}")

        return True, "Location tables verified/created successfully"

    except Exception as e:
        error_msg = f"Error managing subnet tables for location {location}: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)

def analyze_location_tables(cur, location):
    """Analyze tables for better query planning"""
    try:
        # Convert location to lowercase
        location = location.strip().lower()
        logger.info(f"Analyzing location tables for {location}")
        for prefix in ['src', 'dst']:
            table_name = f'loc_{prefix}_{location}'
            cur.execute(f"ANALYZE VERBOSE {table_name}")
        logger.info(f"Completed analysis of location tables for {location}")
        return True
    except Exception as e:
        logger.error(f"Error analyzing location tables for {location}: {e}")
        return False

def vacuum_location_tables(cur, location):
    """Vacuum tables after large deletes"""
    try:
        # Convert location to lowercase
        location = location.strip().lower()
        logger.info(f"Vacuuming location tables for {location}")
        # Need to be outside a transaction for vacuum
        cur.execute("COMMIT")
        for prefix in ['src', 'dst']:
            table_name = f'loc_{prefix}_{location}'
            cur.execute(f"VACUUM ANALYZE {table_name}")
        logger.info(f"Completed vacuum of location tables for {location}")
        return True
    except Exception as e:
        logger.error(f"Error vacuuming location tables for {location}: {e}")
        return False

def check_table_bloat(cur, location):
    """Check and warn about table bloat"""
    try:
        # Convert location to lowercase
        location = location.strip().lower()
        for prefix in ['src', 'dst']:
            table_name = f'loc_{prefix}_{location}'
            quoted_table = f'"{table_name}"'
            cur.execute(f"""
                SELECT pg_size_pretty(pg_total_relation_size(%s)) as total_size,
                       pg_size_pretty(pg_table_size(%s)) as table_size,
                       pg_size_pretty(pg_indexes_size(%s)) as index_size,
                       n_dead_tup::float / n_live_tup as dead_ratio
                FROM pg_stat_user_tables
                WHERE relname = %s
            """, (quoted_table, quoted_table, quoted_table, table_name))

            result = cur.fetchone()
            if result and result[3] > 0.2:  # More than 20% dead tuples
                logger.warning(
                    f"Table {table_name} has significant bloat:\n"
                    f"Total size: {result[0]}\n"
                    f"Table size: {result[1]}\n"
                    f"Index size: {result[2]}\n"
                    f"Dead/Live ratio: {result[3]:.2f}"
                )
        return True
    except Exception as e:
        logger.error(f"Error checking table bloat for {location}: {e}")
        return False

def drop_location_tables(cur, location):
    """Drop source and destination subnet tables for a location if they exist"""
    try:
        # Just strip spaces, preserve case
        location = location.strip()

        logger.info(f"Starting deletion of location tables for {location}")

        # Begin transaction
        cur.execute("BEGIN")

        # Drop source subnet table if exists
        logger.debug(f"Dropping source subnet table loc_src_{location}")
        cur.execute(f"""
            DROP TABLE IF EXISTS loc_src_{location};
        """)

        # Drop destination subnet table if exists
        logger.debug(f"Dropping destination subnet table loc_dst_{location}")
        cur.execute(f"""
            DROP TABLE IF EXISTS loc_dst_{location};
        """)

        # Commit transaction
        cur.execute("COMMIT")
        logger.info(f"Successfully dropped subnet tables for location: {location}")

    except Exception as e:
        # Rollback on error
        cur.execute("ROLLBACK")
        logger.error(f"Error dropping subnet tables for location {location}: {e}")
        raise

def get_location_tables(cur, search_type='src') -> List[str]:
    """Get list of location tables for a search type"""
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name LIKE %s
        AND table_schema = 'public'
    """, (f'loc_{search_type}_%',))
    return [row[0] for row in cur.fetchall()]

def is_valid_ip(ip):
    """Validate IP address format"""
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        return False
    return all(0 <= int(part) <= 255 for part in ip.split('.'))

@sensors_bp.route('/api/v1/sensors', methods=['GET'])
@jwt_required()
@rate_limit()
def get_sensors():
    """Get list of all sensors and their status"""
    try:
        claims = get_jwt()
        is_admin = claims.get('role') == 'admin'

        # Check cache
        cache_key = get_cache_key('sensors', 'admin' if is_admin else 'user')
        cached = redis_client.get(cache_key)
        if cached:
            return cached, 200

        rows = db("SELECT name, status, pcap_avail, totalspace, usedspace, last_update, fqdn, version, location FROM sensors")
        response_data = []
        for sensor in rows:
            sensor_data = {
                'name': sensor[0],
                'status': sensor[1],
                'pcap_avail': sensor[2],
                'totalspace': sensor[3],
                'usedspace': sensor[4],
                'last_update': sensor[5].isoformat() if sensor[5] else None,
                'fqdn': sensor[6],
                'version': sensor[7],
                'location': sensor[8]
            }
            response_data.append(sensor_data)

        response = {'sensors': response_data}

        # Cache the response
        redis_client.setex(
            cache_key,
            300,  # 5 minutes
            json.dumps(response)
        )

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting sensors: {e}")
        logger.debug(traceback.format_exc())
        return jsonify({'error': 'Failed to fetch sensors'}), 500

@sensors_bp.route('/api/v1/sensors/<sensor_name>/status', methods=['GET'])
@jwt_required()
@rate_limit()
def get_sensor_status(sensor_name):
    """Get detailed status for a specific sensor"""
    try:
        claims = get_jwt()
        is_admin = claims.get('role') == 'admin'

        # Get cache key based on role
        cache_key = get_cache_key('sensor', 'admin' if is_admin else 'user', sensor_name)

        # Check cache first
        cached_data = redis_client.get(cache_key)
        if cached_data:
            return Response(cached_data, mimetype='application/json'), 200

        rows = db("""
            SELECT name, status, pcap_avail, totalspace, usedspace,
                   last_update, fqdn
            FROM sensors
            WHERE name = %s
        """, (sensor_name,))

        if not rows:
            return jsonify({"error": "Sensor not found"}), 404

        sensor = rows[0]

        response_data = {
            'name': sensor[0],
            'status': sensor[1],
            'pcap_avail': sensor[2],
            'totalspace': sensor[3],
            'last_update': sensor[5].isoformat() if sensor[5] else None
        }

        if is_admin:
            response_data.update({
                'fqdn': sensor[6],
                'usedspace': sensor[4]
            })

        result = jsonify(response_data)
        redis_client.setex(cache_key, 15, result.get_data())
        return result, 200

    except Exception as e:
        logger.error(f"Error fetching sensor status: {e}")
        return jsonify({"error": "Failed to fetch sensor status"}), 500

@sensors_bp.route('/api/v1/admin/sensor_add', methods=['PUT'])
@jwt_required()
@rate_limit()
@admin_required()
def add_sensor():
    """Add a new sensor to the system"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate required fields
        required_fields = ['name', 'fqdn', 'location', 'devices']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400

        name = data['name']
        fqdn = data['fqdn']
        location = data['location'].upper() # Convert to uppercase
        devices = data['devices']

        # Validate sensor name format
        if not name or not all(c.isalnum() or c == '_' for c in name):
            return jsonify({
                "error": "Sensor name can only contain letters, numbers, and underscores"
            }), 400

        # Validate FQDN format
        if not fqdn or not all(c.isalnum() or c in '.-_' for c in fqdn):
            return jsonify({
                "error": "Invalid FQDN format"
            }), 400

        # Validate and normalize location
        location = location.strip()
        if not location:
            return jsonify({
                "error": "Location cannot be empty"
            }), 400
        if not all(c.isalnum() or c == '_' for c in location):
            return jsonify({
                "error": "Location can only contain letters, numbers, and underscores"
            }), 400

        # Validate devices format and configuration
        if not isinstance(devices, dict) or not devices:
            return jsonify({
                "error": "Devices must be a non-empty object"
            }), 400

        device_configs = {}
        used_ports = set()
        for device_name, value in devices.items():
            try:
                # Validate device name
                if not device_name or not all(c.isalnum() or c in '_-' for c in device_name):
                    return jsonify({
                        "error": f"Invalid device name format: {device_name}"
                    }), 400

                # Handle both simple port format and full format
                if isinstance(value, (str, int)):
                    port = int(value)
                    device_type = 'pcapCollect' if device_name.startswith('napa') else 'tcpdump'
                else:
                    if not isinstance(value, dict):
                        return jsonify({
                            "error": f"Invalid device configuration for {device_name}"
                        }), 400

                    port = int(value.get('port', 0))
                    device_type = value.get('device_type')

                    if not device_type or device_type not in ['pcapCollect', 'tcpdump']:
                        return jsonify({
                            "error": f"Invalid device type for {device_name}. Must be 'pcapCollect' or 'tcpdump'"
                        }), 400

                # Validate port
                if not (1 <= port <= 65535):
                    return jsonify({
                        "error": f"Port {port} for device {device_name} outside valid range (1-65535)"
                    }), 400

                # Check for duplicate ports
                if port in used_ports:
                    return jsonify({
                        "error": f"Duplicate port {port} found in device configurations"
                    }), 400
                used_ports.add(port)

                device_configs[device_name] = {
                    'port': port,
                    'device_type': device_type
                }

            except (ValueError, TypeError) as e:
                return jsonify({
                    "error": f"Invalid configuration for device {device_name}: {str(e)}"
                }), 400

        # Check if sensor exists
        existing = db(
            "SELECT name FROM sensors WHERE name = %s OR fqdn = %s",
            (name, fqdn)
        )

        if existing:
            return jsonify({
                "error": "Sensor with this name or FQDN already exists"
            }), 409

        # Check if this is the first sensor for this location
        existing_loc = db(
            "SELECT COUNT(*) FROM sensors WHERE location = %s",
            (location,)
        )
        is_first_sensor = existing_loc[0][0] == 0

        # Create location tables if this is the first sensor for this location
        if is_first_sensor:
            conn = db_pool.getconn()
            try:
                with conn.cursor() as cur:
                    create_location_tables(cur, location)
                conn.commit()
                logger.info(f"Created location tables for {location}")
            except Exception as e:
                logger.error(f"Error creating location tables: {e}")
                return jsonify({"error": "Failed to create location tables"}), 500
            finally:
                db_pool.putconn(conn)

        # Insert sensor with location
        db("""
            INSERT INTO sensors
            (name, fqdn, status, location)
            VALUES (%s, %s, 'Online', %s)
        """, (name, fqdn, location))

        # Add initial status history entry for each device
        for device_name, device_config in device_configs.items():
            try:
                db("""
                    INSERT INTO sensor_status_history
                    (sensor_fqdn, sensor_port, old_status, new_status)
                    VALUES (%s, %s, NULL, 'Online')
                """, (fqdn, device_config['port']))
                logger.debug(f"Added initial status history for sensor: {name}, port: {device_config['port']}")
            except Exception as e:
                logger.error(f"Error adding status history for device {device_name}: {e}")

        # Add devices
        for device_name, device_config in device_configs.items():
            try:
                db("""
                    INSERT INTO devices
                    (sensor, name, port, device_type, fqdn, status)
                    VALUES (%s, %s, %s, %s, %s, 'Online')
                """, (
                    name,
                    device_name,
                    device_config['port'],
                    device_config['device_type'],
                    fqdn
                ))
            except Exception as e:
                logger.error(f"Error adding device {device_name} for sensor {name}: {e}")

        logger.info(f"Added new sensor: {name} ({fqdn}) with {len(devices)} devices")
        return jsonify({
            "message": "Sensor added successfully",
            "name": name,
            "devices": len(devices),
            "location_tables_created": is_first_sensor
        }), 201

    except Exception as e:
        logger.error(f"Error adding sensor: {e}")
        return jsonify({"error": str(e)}), 500

@sensors_bp.route('/api/v1/admin/sensor_del/<sensor_name>', methods=['DELETE'])
@jwt_required()
@rate_limit()
@admin_required()
def delete_sensor(sensor_name):
    """Delete an existing sensor and its devices"""
    try:
        # Check if sensor exists and get its status and location
        sensor = db("SELECT status, location FROM sensors WHERE name = %s", (sensor_name,))
        if not sensor:
            return jsonify({"error": "Sensor not found"}), 404

        status, location = sensor[0]

        # Check if sensor is in a state that allows deletion
        if status == 'Busy':
            return jsonify({"error": "Cannot delete sensor while it is busy"}), 409

        # Check for active or pending jobs
        active_jobs = db("""
            SELECT COUNT(*) FROM jobs
            WHERE sensor = %s
            AND status IN ('Submitted', 'Running', 'Retrieving')
        """, (sensor_name,))

        if active_jobs[0][0] > 0:
            return jsonify({"error": "Cannot delete sensor with active or pending jobs"}), 409

        # Get count of devices before deletion for logging
        devices = db("SELECT COUNT(*) FROM devices WHERE sensor = %s", (sensor_name,))
        device_count = devices[0][0] if devices else 0

        logger.info(f"Deleting sensor '{sensor_name}' with {device_count} devices")

        # Get a connection for transaction
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                # Start transaction
                cur.execute("BEGIN")

                # First delete devices explicitly
                cur.execute("DELETE FROM devices WHERE sensor = %s", (sensor_name,))

                # Then delete the sensor
                cur.execute("DELETE FROM sensors WHERE name = %s RETURNING name", (sensor_name,))
                if not cur.fetchone():
                    conn.rollback()
                    logger.error(f"Sensor '{sensor_name}' not found during deletion")
                    return jsonify({"error": "Sensor not found"}), 404

                # Check if this was the last sensor for this location
                cur.execute("SELECT COUNT(*) FROM sensors WHERE location = %s", (location,))
                remaining_sensors = cur.fetchone()[0]

                # If this was the last sensor for this location, drop the location tables
                if remaining_sensors == 0:
                    logger.info(f"Last sensor for location {location}, dropping location tables")
                    try:
                        drop_location_tables(cur, location)
                    except Exception as e:
                        logger.error(f"Error dropping location tables: {e}")

                # Commit transaction
                conn.commit()

                logger.info(f"Successfully deleted sensor '{sensor_name}' and {device_count} devices")
                return jsonify({
                    "message": "Sensor deleted successfully",
                    "name": sensor_name,
                    "devices_removed": device_count,
                    "location_tables_dropped": remaining_sensors == 0
                }), 200

        except Exception as e:
            conn.rollback()
            logger.error(f"Error during sensor deletion: {e}")
            return jsonify({"error": "Failed to delete sensor"}), 500
        finally:
            db_pool.putconn(conn)

    except Exception as e:
        logger.error(f"Error in delete_sensor: {e}")
        return jsonify({"error": "Failed to delete sensor"}), 500

@sensors_bp.route('/api/v1/sensors/<sensor_name>/devices', methods=['GET'])
@jwt_required()
@rate_limit()
def get_sensor_devices(sensor_name):
    """Get list of devices for a specific sensor"""
    try:
        claims = get_jwt()
        is_admin = claims.get('role') == 'admin'

        # Check cache
        cache_key = get_cache_key('device', 'admin' if is_admin else 'user', sensor_name)
        cached = redis_client.get(cache_key)
        if cached:
            return cached, 200

        # Check if sensor exists
        sensor = db("SELECT name FROM sensors WHERE name = %s", (sensor_name,))
        if not sensor:
            return jsonify({"error": "Sensor not found"}), 404

        # Get all device fields
        rows = db("""
            SELECT name, port, device_type, status, last_checked,
                   runtime, workers, src_subnets, dst_subnets,
                   uniq_subnets, avg_idle_time, avg_work_time,
                   overflows, size, version, output_path, proc,
                   stats_date
            FROM devices
            WHERE sensor = %s
            ORDER BY name
        """, (sensor_name,))

        devices = [{
            'name': row[0],
            'port': row[1],
            'type': row[2],
            'status': row[3],
            'last_checked': row[4].isoformat() if row[4] else None,
            'runtime': row[5],
            'workers': row[6],
            'src_subnets': row[7],
            'dst_subnets': row[8],
            'uniq_subnets': row[9],
            'avg_idle_time': row[10],
            'avg_work_time': row[11],
            'overflows': row[12],
            'size': row[13],
            'version': row[14],
            'output_path': row[15],
            'proc': row[16],
            'stats_date': row[17].isoformat() if row[17] else None
        } for row in rows]

        response = {
            'sensor': sensor_name,
            'devices': devices,
            'count': len(devices)
        }

        # Cache the response
        redis_client.setex(
            cache_key,
            300,  # 5 minutes
            json.dumps(response)
        )

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error fetching devices for sensor {sensor_name}: {e}")
        logger.debug(traceback.format_exc())
        return jsonify({"error": "Failed to fetch devices"}), 500

@sensors_bp.route('/api/v1/locations', methods=['GET'])
@jwt_required()
@rate_limit()
def get_locations():
    """Get all locations.

    Returns locations with uppercase site identifiers for display purposes.
    The actual database tables for each location use lowercase names internally.
    """
    try:
        # Try to get from cache first
        cache_key = get_cache_key('locations', 'all')
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

        # Get locations from database (sites are already stored uppercase)
        locations = db("""
            SELECT site, name, latitude, longitude, description, color
            FROM locations
            ORDER BY name
        """)

        if locations is None:
            logger.error("Database query returned None for locations")
            return jsonify({"error": "Database error"}), 500

        # Format the response (site is already uppercase from database)
        location_list = [{
            'site': loc[0],  # Already uppercase from database
            'name': loc[1],
            'latitude': float(loc[2]),
            'longitude': float(loc[3]),
            'description': loc[4],
            'color': loc[5]
        } for loc in locations]

        # Cache the results for 1 hour
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
        logger.error(f"Error getting locations: {e}")
        return jsonify({"error": "Failed to get location data"}), 500
