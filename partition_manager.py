import time
import logging
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_values
from simpleLogger import SimpleLogger

# Initialize logger
logger = SimpleLogger('partition_manager')

def manage_time_partitions(cur, retention_hours=24):
    """Manage subnet location map time-based partitions"""
    try:
        current_time = int(time.time())
        hour_start = current_time - (current_time % 3600)

        # Create future partitions (3 hour buffer)
        for hour_offset in range(-retention_hours, 4):
            partition_time = hour_start + (hour_offset * 3600)
            cur.execute("""
                SELECT create_hourly_partition(%s)
            """, (partition_time,))

        # Cleanup old partitions (uses internal 24-hour cutoff)
        cur.execute("SELECT cleanup_old_subnet_mappings()")

    except Exception as e:
        logger.error(f"Error managing partitions: {e}")
        raise

def migrate_data_to_partitioned_table(cur, batch_size=10000):
    """Migrate data from old table to new partitioned table in batches"""
    try:
        # Get total count
        cur.execute("SELECT COUNT(*) FROM subnet_location_map")
        total_rows = cur.fetchone()[0]

        # Get minimum last_seen value
        cur.execute("SELECT MIN(last_seen) FROM subnet_location_map")
        min_last_seen = cur.fetchone()[0] or int(time.time())

        # Process in batches based on last_seen
        current_last_seen = min_last_seen
        processed_rows = 0

        while processed_rows < total_rows:
            # Ensure partitions exist for this time range
            cur.execute("SELECT create_hourly_partition(%s)",
                       (current_last_seen - (current_last_seen % 3600),))

            # Copy batch of data
            cur.execute("""
                INSERT INTO subnet_location_map_new
                SELECT * FROM subnet_location_map
                WHERE last_seen >= %s
                ORDER BY last_seen
                LIMIT %s
            """, (current_last_seen, batch_size))

            rows_inserted = cur.rowcount
            if rows_inserted == 0:
                break

            processed_rows += rows_inserted

            # Get the last last_seen value from this batch
            cur.execute("""
                SELECT MAX(last_seen)
                FROM subnet_location_map
                WHERE last_seen >= %s
                ORDER BY last_seen
                LIMIT %s
            """, (current_last_seen, batch_size))

            current_last_seen = cur.fetchone()[0] + 1

            logger.info(f"Migrated {processed_rows}/{total_rows} rows")

        return processed_rows

    except Exception as e:
        logger.error(f"Error migrating data: {e}")
        raise

def verify_migration(cur):
    """Verify the data migration was successful"""
    try:
        # Compare row counts
        cur.execute("SELECT COUNT(*) FROM subnet_location_map")
        old_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM subnet_location_map_new")
        new_count = cur.fetchone()[0]

        if old_count != new_count:
            logger.error(f"Row count mismatch: old={old_count}, new={new_count}")
            return False

        # Compare random samples
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT src_subnet, dst_subnet, src_location, dst_location,
                       first_seen, last_seen, packet_count
                FROM subnet_location_map
                EXCEPT
                SELECT src_subnet, dst_subnet, src_location, dst_location,
                       first_seen, last_seen, packet_count
                FROM subnet_location_map_new
            ) diff
        """)

        diff_count = cur.fetchone()[0]
        if diff_count > 0:
            logger.error(f"Found {diff_count} differing rows")
            return False

        return True

    except Exception as e:
        logger.error(f"Error verifying migration: {e}")
        raise