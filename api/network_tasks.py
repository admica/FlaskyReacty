"""
Periodic tasks for network data maintenance
PATH: api/network_tasks.py
"""
import time
from datetime import datetime
from threading import Thread, Event
import configparser

from simpleLogger import SimpleLogger
from core import db

# Initialize logger
logger = SimpleLogger('network_tasks')

# Load config
config = configparser.ConfigParser()
config.read('/opt/pcapserver/config.ini')

class NetworkMaintenanceThread(Thread):
    def __init__(self):
        super().__init__()
        self.stop_event = Event()
        self.daemon = True
        self.name = "NetworkMaintenance"
        self.refresh_interval = 300  # 5 minutes
        self.error_wait = 60  # 1 minute

    def refresh_view(self):
        """Refresh the materialized view"""
        try:
            logger.info("Refreshing network traffic summary view")
            db("REFRESH MATERIALIZED VIEW network_traffic_summary")
            logger.info("Network traffic summary view refreshed successfully")
            return True
        except Exception as e:
            logger.error(f"Error refreshing network traffic summary: {e}")
            return False

    def cleanup_old_data(self):
        """Clean up old subnet mappings and update monthly summary"""
        try:
            logger.info("Running subnet mapping maintenance")
            # Manage partitions first
            db("SELECT manage_subnet_partitions()")
            # Then clean up old data and update monthly summary
            db("SELECT cleanup_subnet_mappings()")
            logger.info("Subnet mapping maintenance completed successfully")
            return True
        except Exception as e:
            logger.error(f"Error in subnet mapping maintenance: {e}")
            return False

    def run(self):
        """Run periodic maintenance tasks"""
        consecutive_errors = 0
        while not self.stop_event.is_set():
            try:
                # Clean up old data first
                if not self.cleanup_old_data():
                    consecutive_errors += 1
                else:
                    consecutive_errors = 0

                # Then refresh view
                if not self.refresh_view():
                    consecutive_errors += 1
                else:
                    consecutive_errors = 0

                # Adjust wait time based on errors
                if consecutive_errors > 0:
                    wait_time = min(self.error_wait * consecutive_errors, 300)  # Max 5 minutes
                    logger.warning(f"Waiting {wait_time}s after {consecutive_errors} consecutive errors")
                else:
                    wait_time = self.refresh_interval
                    logger.debug(f"Maintenance tasks completed successfully, waiting {wait_time}s")

                # Wait for next cycle or stop event
                self.stop_event.wait(wait_time)

            except Exception as e:
                logger.error(f"Error in network maintenance: {e}")
                consecutive_errors += 1
                self.stop_event.wait(self.error_wait)

    def stop(self):
        """Stop the maintenance thread"""
        logger.info("Stopping network maintenance thread")
        self.stop_event.set()

# Create and start the maintenance thread
maintenance_thread = NetworkMaintenanceThread()
