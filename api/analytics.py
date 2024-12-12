"""
Analytics endpoints for the PCAP Server API
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from datetime import datetime, timezone, timedelta
import traceback

from core import logger, db, rate_limit, db_pool
from api.auth import activity_tracking

# Create blueprint
analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/api/v1/analytics/sensors/activity', methods=['GET'])
@jwt_required()
@rate_limit()
@activity_tracking()
def get_sensor_activity():
    """Get sensor activity data for the specified time period"""
    try:
        # Get query parameters with defaults
        hours = min(int(request.args.get('hours', 1)), 168)  # Cap at 1 week
        min_packets = max(int(request.args.get('min_packets', 1000)), 1)  # Minimum 1 packet

        # Calculate time range as UNIX timestamp
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)
        start_timestamp = int(start_time.timestamp())

        # Get all locations first
        locations = db("SELECT DISTINCT location FROM sensors WHERE location IS NOT NULL")
        if not locations:
            return jsonify({
                'timeframe': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat(),
                    'hours': hours
                },
                'query': {
                    'min_packets': min_packets
                },
                'summary': {
                    'total_packets': 0,
                    'active_sensors': 0,
                    'total_locations': 0
                },
                'sensors': {},
                'locations': []
            }), 200

        # Process each location
        all_sensors = {}
        all_locations = set()
        total_packets = 0
        active_sensors = 0

        conn = db_pool.getconn()
        try:
            for loc in locations:
                location = loc[0]
                all_locations.add(location)

                with conn.cursor() as cur:
                    # Build and execute optimized query for this location
                    query = f"""
                    WITH src_stats AS (
                        SELECT /*+ PARALLEL(4) */
                            sensor,
                            device,
                            COUNT(DISTINCT subnet) as subnet_count,
                            SUM(count) as packet_count
                        FROM "loc_src_{location}"
                        WHERE last_seen >= %s
                        GROUP BY sensor, device
                    ),
                    dst_stats AS (
                        SELECT /*+ PARALLEL(4) */
                            sensor,
                            device,
                            COUNT(DISTINCT subnet) as subnet_count,
                            SUM(count) as packet_count
                        FROM "loc_dst_{location}"
                        WHERE last_seen >= %s
                        GROUP BY sensor, device
                    ),
                    device_activity AS (
                        SELECT
                            s.name,
                            s.location,
                            d.name as device,
                            d.device_type,
                            d.uniq_subnets,
                            d.last_checked,
                            d.runtime,
                            d.workers,
                            d.avg_idle_time,
                            COALESCE(src.packet_count, 0) as src_packets,
                            COALESCE(dst.packet_count, 0) as dst_packets,
                            COALESCE(src.subnet_count, 0) as src_subnets,
                            COALESCE(dst.subnet_count, 0) as dst_subnets
                        FROM sensors s
                        JOIN devices d ON d.sensor = s.name
                        LEFT JOIN src_stats src ON src.sensor = s.name AND src.device = d.name
                        LEFT JOIN dst_stats dst ON dst.sensor = s.name AND dst.device = d.name
                        WHERE s.location = %s
                        AND (COALESCE(src.packet_count, 0) + COALESCE(dst.packet_count, 0)) >= %s
                    )
                    SELECT
                        name,
                        location,
                        jsonb_agg(jsonb_build_object(
                            'device', device,
                            'type', device_type,
                            'uniq_subnets', uniq_subnets,
                            'last_checked', last_checked,
                            'runtime', runtime,
                            'workers', workers,
                            'avg_idle_time', avg_idle_time,
                            'src_packets', src_packets,
                            'dst_packets', dst_packets,
                            'src_subnets', src_subnets,
                            'dst_subnets', dst_subnets
                        )) as devices,
                        SUM(src_packets + dst_packets) as total_packets,
                        COUNT(DISTINCT CASE WHEN src_subnets > 0 THEN device END) as active_src_devices,
                        COUNT(DISTINCT CASE WHEN dst_subnets > 0 THEN device END) as active_dst_devices
                    FROM device_activity
                    GROUP BY name, location
                    HAVING SUM(src_packets + dst_packets) >= %s
                    ORDER BY total_packets DESC
                    """

                    try:
                        cur.execute(query, (start_timestamp, start_timestamp, location, min_packets, min_packets))
                        rows = cur.fetchall()

                        for row in rows:
                            sensor_name, _, devices, packet_count, src_devices, dst_devices = row
                            active_sensors += 1
                            total_packets += packet_count

                            # Format device data
                            device_list = []
                            for device in devices:
                                device_list.append({
                                    'name': device['device'],
                                    'type': device['type'],
                                    'stats': {
                                        'uniq_subnets': device['uniq_subnets'],
                                        'runtime': device['runtime'],
                                        'workers': device['workers'],
                                        'avg_idle_time': device['avg_idle_time']
                                    },
                                    'activity': {
                                        'source': {
                                            'packets': device['src_packets'],
                                            'subnets': device['src_subnets']
                                        },
                                        'destination': {
                                            'packets': device['dst_packets'],
                                            'subnets': device['dst_subnets']
                                        }
                                    },
                                    'last_checked': device['last_checked'].isoformat() if isinstance(device['last_checked'], datetime) else device['last_checked']
                                })

                            all_sensors[sensor_name] = {
                                'location': location,
                                'total_packets': packet_count,
                                'active_source_devices': src_devices,
                                'active_dest_devices': dst_devices,
                                'devices': device_list
                            }
                    except Exception as e:
                        logger.warning(f"Error querying location {location}: {e}")
                        continue

        finally:
            db_pool.putconn(conn)

        return jsonify({
            'timeframe': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'hours': hours
            },
            'query': {
                'min_packets': min_packets
            },
            'summary': {
                'total_packets': total_packets,
                'active_sensors': active_sensors,
                'total_locations': len(all_locations)
            },
            'sensors': all_sensors,
            'locations': sorted(list(all_locations))
        }), 200

    except ValueError as e:
        logger.error(f"Invalid parameter in sensor activity request: {e}")
        return jsonify({
            'error': 'Invalid parameters',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error getting sensor activity: {e}")
        logger.debug(traceback.format_exc())
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500
