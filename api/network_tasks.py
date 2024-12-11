"""
Periodic tasks for network data maintenance
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
            db("SELECT refresh_network_traffic_summary()")
            logger.info("Network traffic summary view refreshed successfully")
            return True
        except Exception as e:
            logger.error(f"Error refreshing network traffic summary: {e}")
            return False

    def cleanup_old_data(self):
        """Clean up old subnet mappings"""
        try:
            logger.info("Cleaning up old subnet mappings")
            db("SELECT cleanup_old_subnet_mappings()")
            logger.info("Old subnet mappings cleaned up successfully")
            return True
        except Exception as e:
            logger.error(f"Error cleaning up old subnet mappings: {e}")
            return False

    def run(self):
        """Run periodic maintenance tasks"""
        consecutive_errors = 0
        while not self.stop_event.is_set():
            try:
                # Refresh view first
                if not self.refresh_view():
                    consecutive_errors += 1
                else:
                    consecutive_errors = 0

                # Clean up old data
                if not self.cleanup_old_data():
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
maintenance_thread.start()
