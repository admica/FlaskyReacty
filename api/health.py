"""
Health check and version endpoints for the PCAP Server API
"""
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

# Import shared resources
from simpleLogger import SimpleLogger
from cache_utils import redis_client
from core import VERSION, BUILD_DATE, db, rate_limit

# Initialize logger
logger = SimpleLogger('health')

# Create blueprint
health_bp = Blueprint('health', __name__)

@health_bp.route('/api/v1/health', methods=['GET'])
@rate_limit()
def health_check():
    """Get API health status"""
    try:
        # Check database connection
        db("SELECT 1")

        # Check Redis connection
        redis_client.ping()

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'components': {
                'database': 'operational',
                'redis': 'operational'
            }
        }), 200

    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': str(e)
        }), 500

@health_bp.route('/api/v1/version', methods=['GET'])
@rate_limit()
def get_version():
    """Get API version information"""
    try:
        return jsonify({
            'version': VERSION,
            'build_date': BUILD_DATE if 'BUILD_DATE' in globals() else 'development'
        }), 200
    except Exception as e:
        logger.error(f"Version check error: {e}")
        return jsonify({'error': 'Version information unavailable'}), 500

@health_bp.route('/api/v1/health/summary', methods=['GET'])
@jwt_required()
@rate_limit()
def get_health_summary():
    """Get sensor health summary data with optional timestamp filtering"""
    try:
        # Get timestamp range from query parameters
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')

        # Build query based on parameters
        query = """
            SELECT timestamp,
                   duration_seconds,
                   sensors_checked,
                   sensors_online,
                   sensors_offline,
                   sensors_degraded,
                   devices_total,
                   devices_online,
                   devices_offline,
                   devices_degraded,
                   avg_pcap_minutes,
                   avg_disk_usage_pct,
                   errors,
                   performance_metrics
            FROM sensor_health_summary
        """
        params = []

        # Add timestamp filtering if provided
        if start_time or end_time:
            conditions = []
            if start_time:
                conditions.append("timestamp >= %s")
                params.append(start_time)
            if end_time:
                conditions.append("timestamp <= %s")
                params.append(end_time)
            query += " WHERE " + " AND ".join(conditions)

        # Order by timestamp descending
        query += " ORDER BY timestamp DESC"

        # Execute query
        results = db(query, params) if params else db(query)

        # Get location-specific stats
        location_stats = db("""
            SELECT 
                s.location,
                COUNT(*) FILTER (WHERE s.status = 'Online') as sensors_online,
                COUNT(*) FILTER (WHERE s.status = 'Offline') as sensors_offline,
                COUNT(*) FILTER (WHERE s.status = 'Degraded') as sensors_degraded,
                COUNT(d.*) FILTER (WHERE d.status = 'Online') as devices_online,
                COUNT(d.*) FILTER (WHERE d.status = 'Offline') as devices_offline,
                COUNT(d.*) FILTER (WHERE d.status = 'Degraded') as devices_degraded,
                SUM(CASE WHEN s.pcap_avail IS NOT NULL THEN s.pcap_avail ELSE 0 END)::integer as pcap_minutes,
                ROUND(AVG(CASE 
                    WHEN s.usedspace LIKE '%%\%%' 
                    THEN CAST(TRIM(TRAILING '%%' FROM s.usedspace) AS INTEGER)
                    ELSE 0 
                END))::integer as disk_usage
            FROM sensors s
            LEFT JOIN devices d ON d.sensor = s.name
            WHERE s.location IS NOT NULL
            GROUP BY s.location
        """)

        # Format results
        summaries = []
        for row in results:
            # Get location stats for this summary
            location_data = {}
            for loc in location_stats:
                location_data[loc[0]] = {
                    'sensors_online': loc[1],
                    'sensors_offline': loc[2],
                    'sensors_degraded': loc[3],
                    'devices_online': loc[4],
                    'devices_offline': loc[5],
                    'devices_degraded': loc[6],
                    'pcap_minutes': loc[7],
                    'disk_usage': loc[8]
                }

            # Create performance metrics with location stats
            performance_metrics = row[13] if row[13] else {}
            performance_metrics['location_stats'] = location_data

            summary = {
                'timestamp': row[0].isoformat(),
                'duration_seconds': row[1],
                'sensors': {
                    'total': row[2],
                    'online': row[3],
                    'offline': row[4],
                    'degraded': row[5]
                },
                'devices': {
                    'total': row[6],
                    'online': row[7],
                    'offline': row[8],
                    'degraded': row[9]
                },
                'metrics': {
                    'avg_pcap_minutes': row[10],
                    'avg_disk_usage_pct': row[11]
                },
                'errors': row[12] if row[12] else [],
                'performance_metrics': performance_metrics
            }
            summaries.append(summary)

        return jsonify({
            'count': len(summaries),
            'summaries': summaries
        }), 200

    except Exception as e:
        logger.error(f"Error fetching health summary: {e}")
        return jsonify({
            'error': 'Failed to fetch health summary',
            'details': str(e)
        }), 500
