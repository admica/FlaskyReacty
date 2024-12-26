"""
Maintenance operations for the PCAP Server API
"""
from datetime import datetime, timezone
import threading
import time
import traceback

from core import logger, config
from api.auth import cleanup_old_sessions

def run_maintenance_operations():
    """Run periodic maintenance operations"""
    while True:
        try:
            # Run session cleanup every hour
            cleanup_old_sessions()
            
            # Sleep for an hour
            time.sleep(3600)
            
        except Exception as e:
            logger.error(f"Error in maintenance operations: {e}")
            logger.error(traceback.format_exc())
            # Sleep for a minute before retrying on error
            time.sleep(60)

def start_maintenance_thread():
    """Start the maintenance operations thread"""
    maintenance_thread = threading.Thread(
        target=run_maintenance_operations,
        name="maintenance_operations",
        daemon=True
    )
    maintenance_thread.start()
    logger.info("Started maintenance operations thread") 