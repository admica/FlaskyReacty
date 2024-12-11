#!/usr/bin/env python3
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime, timezone
import sys
import os
from typing import List, Dict, Any, Tuple
import json
import configparser

def connect_db() -> psycopg2.extensions.connection:
    """Connect to the database using credentials from config.ini"""
    try:
        config = configparser.ConfigParser()
        config.read('config.ini')

        conn = psycopg2.connect(
            dbname=config['DB']['database'],
            user=config['DB']['username'],
            password=config['DB']['password'],
            host=config['DB']['hostname'],
            port=config['DB']['port']
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

def check_table_exists(cur, table_name: str) -> bool:
    """Check if a table or materialized view exists in the database"""
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
            AND c.relname = %s
            AND (c.relkind = 'r' OR c.relkind = 'm')
        );
    """, (table_name,))
    return cur.fetchone()[0]

def check_function_exists(cur, function_name: str) -> bool:
    """Check if a function exists in the database"""
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public'
            AND p.proname = %s
        );
    """, (function_name,))
    return cur.fetchone()[0]

def check_index_exists(cur, index_name: str) -> bool:
    """Check if an index exists in the database"""
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
            AND c.relname = %s
            AND c.relkind = 'i'
        );
    """, (index_name,))
    return cur.fetchone()[0]

def check_enums(cur) -> Dict[str, List[str]]:
    """Check if all required ENUMs exist and their values"""
    enum_queries = {
        'job_status': "SELECT unnest(enum_range(NULL::job_status))",
        'sensor_status': "SELECT unnest(enum_range(NULL::sensor_status))",
        'device_status': "SELECT unnest(enum_range(NULL::device_status))"
    }

    results = {}
    print("\n=== Checking ENUMs ===")
    for enum_name, query in enum_queries.items():
        try:
            cur.execute(query)
            results[enum_name] = [row[0] for row in cur.fetchall()]
            print(f"{enum_name}: {', '.join(results[enum_name])}")
        except Exception as e:
            print(f"Error checking {enum_name}: {e}")
    return results

def check_required_functions(cur) -> Dict[str, bool]:
    """Check if all required functions exist"""
    print("\n=== Checking Required Functions ===")
    functions = [
        'cleanup_old_subnet_mappings',
        'create_hourly_partition',
        'create_location_tables',
        'create_partition_trigger',
        'log_admin_changes',
        'log_sensor_status_change',
        'refresh_network_traffic_summary'
    ]

    results = {}
    for func in functions:
        exists = check_function_exists(cur, func)
        results[func] = exists
        print(f"{func}: {'✓' if exists else '✗'}")
    return results

def check_location_specific_tables(cur) -> Dict[str, List[Dict[str, Any]]]:
    """Check location-specific tables and their indexes"""
    try:
        print("\n=== Checking Location-Specific Tables ===")

        # Get all locations
        cur.execute("SELECT site FROM locations ORDER BY site")
        locations = [row[0] for row in cur.fetchall()]

        results = {}
        for loc in locations:
            loc_lower = loc.lower()
            src_table = f"loc_src_{loc_lower}"
            dst_table = f"loc_dst_{loc_lower}"

            src_exists = check_table_exists(cur, src_table)
            dst_exists = check_table_exists(cur, dst_table)

            # Check indexes if tables exist
            src_indexes = []
            dst_indexes = []
            if src_exists:
                cur.execute("""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = %s
                """, (src_table,))
                src_indexes = [dict(row) for row in cur.fetchall()]

            if dst_exists:
                cur.execute("""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = %s
                """, (dst_table,))
                dst_indexes = [dict(row) for row in cur.fetchall()]

            results[loc] = {
                'src_table': {
                    'exists': src_exists,
                    'indexes': src_indexes
                },
                'dst_table': {
                    'exists': dst_exists,
                    'indexes': dst_indexes
                }
            }

            # Print summary
            print(f"\nLocation: {loc}")
            print(f"  Source table ({src_table}): {'✓' if src_exists else '✗'}")
            if src_exists:
                print(f"    Indexes: {len(src_indexes)}")
            print(f"  Dest table ({dst_table}): {'✓' if dst_exists else '✗'}")
            if dst_exists:
                print(f"    Indexes: {len(dst_indexes)}")

        return results
    except Exception as e:
        print(f"Error checking location tables: {e}")
        return {}

def check_subnet_mapping_partitions(cur) -> Dict[str, Any]:
    """Check subnet_location_map partitions and data"""
    try:
        print("\n=== Checking Subnet Mappings ===")

        # Check partitions
        cur.execute("""
            SELECT tablename, pg_size_pretty(pg_total_relation_size(quote_ident(tablename)::text)) as size,
                   pg_size_pretty(pg_indexes_size(quote_ident(tablename)::text)) as index_size,
                   pg_stat_get_live_tuples(quote_ident(tablename)::regclass) as row_count
            FROM pg_tables
            WHERE tablename LIKE 'subnet_location_map_%'
            ORDER BY tablename
        """)
        partitions = [dict(row) for row in cur.fetchall()]
        print(f"\nFound {len(partitions)} subnet_location_map partitions:")
        for p in partitions:
            print(f"  {p['tablename']}:")
            print(f"    Size: {p['size']}")
            print(f"    Index Size: {p['index_size']}")
            print(f"    Rows: {p['row_count']}")

        # Check indexes
        cur.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'subnet_location_map'
        """)
        indexes = cur.fetchall()
        print("\nIndexes on subnet_location_map:")
        for idx_name, idx_def in indexes:
            print(f"  {idx_name}")

        # Check recent mappings
        cur.execute("""
            SELECT src_location, dst_location,
                   COUNT(*) as mapping_count,
                   MIN(to_timestamp(first_seen)) as earliest,
                   MAX(to_timestamp(last_seen)) as latest,
                   SUM(packet_count) as total_packets
            FROM subnet_location_map
            GROUP BY src_location, dst_location
            ORDER BY mapping_count DESC
            LIMIT 5
        """)
        mappings = [dict(row) for row in cur.fetchall()]
        if mappings:
            print("\nTop 5 location pairs by mapping count:")
            for m in mappings:
                print(f"  {m['src_location']} -> {m['dst_location']}:")
                print(f"    Mappings: {m['mapping_count']}")
                print(f"    Packets: {m['total_packets']}")
                print(f"    Time range: {m['earliest']} to {m['latest']}")

        return {
            'partitions': partitions,
            'recent_mappings': mappings
        }
    except Exception as e:
        print(f"Error checking subnet mappings: {e}")
        return {'partitions': [], 'recent_mappings': []}

def check_traffic_summary(cur) -> List[Dict[str, Any]]:
    """Check network_traffic_summary materialized view"""
    try:
        print("\n=== Checking Network Traffic Summary ===")

        # Check if materialized view exists
        exists = check_table_exists(cur, 'network_traffic_summary')
        print(f"Materialized view exists: {'✓' if exists else '✗'}")

        if exists:
            # Check when it was last refreshed
            cur.execute("""
                SELECT pg_size_pretty(pg_relation_size('network_traffic_summary')) as size,
                       pg_stat_get_last_autoanalyze_time('network_traffic_summary'::regclass) as last_analyzed,
                       pg_stat_get_live_tuples('network_traffic_summary'::regclass) as row_count
            """)
            stats = dict(cur.fetchone())
            print(f"\nView statistics:")
            print(f"  Size: {stats['size']}")
            print(f"  Last analyzed: {stats['last_analyzed']}")
            print(f"  Row count: {stats['row_count']}")

            # Get sample data
            cur.execute("""
                SELECT src_location, dst_location,
                       unique_subnets, total_packets,
                       to_timestamp(earliest_seen) as first_seen,
                       to_timestamp(latest_seen) as last_seen
                FROM network_traffic_summary
                ORDER BY total_packets DESC
                LIMIT 5
            """)
            summary = [dict(row) for row in cur.fetchall()]
            if summary:
                print("\nTop 5 traffic summaries by packet count:")
                for s in summary:
                    print(f"  {s['src_location']} -> {s['dst_location']}:")
                    print(f"    Packets: {s['total_packets']}")
                    print(f"    Unique subnets: {s['unique_subnets']}")
                    print(f"    Time range: {s['first_seen']} to {s['last_seen']}")
            return summary
    except Exception as e:
        print(f"Error checking traffic summary: {e}")
        return []

def check_jobs_and_history(cur) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Check jobs and job status history"""
    try:
        print("\n=== Checking Jobs and History ===")

        # Check recent jobs
        cur.execute("""
            SELECT id, username, sensor, status,
                   submitted_at, completed_at,
                   start_time, end_time
            FROM jobs
            ORDER BY submitted_at DESC
            LIMIT 5
        """)
        jobs = [dict(row) for row in cur.fetchall()]
        print(f"\nFound {len(jobs)} recent jobs:")
        for j in jobs:
            print(f"  Job {j['id']} by {j['username']}: {j['status']}")

        # Check job status history
        cur.execute("""
            SELECT job_id, status, timestamp
            FROM job_status_history
            ORDER BY timestamp DESC
            LIMIT 5
        """)
        history = [dict(row) for row in cur.fetchall()]
        print(f"\nRecent job status changes:")
        for h in history:
            print(f"  Job {h['job_id']}: {h['status']} at {h['timestamp']}")

        return jobs, history
    except Exception as e:
        print(f"Error checking jobs: {e}")
        return [], []

def check_health_summary(cur) -> List[Dict[str, Any]]:
    """Check sensor_health_summary data"""
    try:
        print("\n=== Checking Health Summary ===")
        cur.execute("""
            SELECT timestamp,
                   sensors_online, sensors_offline, sensors_degraded,
                   devices_online, devices_offline, devices_degraded,
                   avg_pcap_minutes, avg_disk_usage_pct
            FROM sensor_health_summary
            ORDER BY timestamp DESC
            LIMIT 5
        """)
        health = [dict(row) for row in cur.fetchall()]
        print("\nMost recent health summaries:")
        for h in health:
            total_sensors = h['sensors_online'] + h['sensors_offline'] + h['sensors_degraded']
            total_devices = h['devices_online'] + h['devices_offline'] + h['devices_degraded']
            print(f"  {h['timestamp']}:")
            print(f"    Sensors: {h['sensors_online']}/{total_sensors} online")
            print(f"    Devices: {h['devices_online']}/{total_devices} online")
            print(f"    Avg PCAP minutes: {h['avg_pcap_minutes']}")
            print(f"    Avg Disk Usage: {h['avg_disk_usage_pct']}%")
        return health
    except Exception as e:
        print(f"Error checking health summary: {e}")
        return []

def main():
    """Run all database checks"""
    conn = connect_db()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            print("Running comprehensive database checks...")

            # Run all checks
            results = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'enums': check_enums(cur),
                'functions': check_required_functions(cur),
                'location_tables': check_location_specific_tables(cur),
                'subnet_mappings': check_subnet_mapping_partitions(cur),
                'traffic_summary': check_traffic_summary(cur),
                'jobs': {
                    'recent_jobs': check_jobs_and_history(cur)[0],
                    'status_history': check_jobs_and_history(cur)[1]
                },
                'health_summary': check_health_summary(cur)
            }

            # Save results to JSON file
            with open('db_test_results.json', 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print("\nDetailed results saved to db_test_results.json")

    except Exception as e:
        print(f"Error during database checks: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()