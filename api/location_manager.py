"""
Location management for job processing
PATH: api/location_manager.py
"""
from multiprocessing import Process, Queue
from typing import Dict, Optional, Tuple
import threading
from core import logger, db
from api.job_process import start_job_proc, job_queues

class LocationManager:
    def __init__(self):
        self._job_procs: Dict[str, Process] = {}
        self._job_queues: Dict[str, Queue] = {}
        self._lock = threading.Lock() # To enforce singleton

    def get_location_queue(self, location: str) -> Tuple[Optional[Queue], str]:
        """
        Get or create job queue for a location.
        Returns (queue, error_message). If queue is None, error_message explains why.
        """
        with self._lock:
            # Check if we already have a running processor
            if location in self._job_queues:
                proc = self._job_procs[location]
                if proc.is_alive():
                    return self._job_queues[location], ""
                else:
                    # Clean up dead process
                    logger.warning(f"Found dead processor for {location}, cleaning up")
                    self._cleanup_location(location)

            # Verify location has active sensors
            try:
                sensors = db("""
                    SELECT name, fqdn 
                    FROM sensors 
                    WHERE location = %s 
                    AND status != 'Offline'
                """, (location,))

                if not sensors:
                    return None, f"No active sensors found for location {location}"

            except Exception as e:
                logger.error(f"Error checking sensors for {location}: {e}")
                return None, f"Database error checking sensors: {e}"

            # Create new processor
            try:
                logger.info(f"Starting job processor for location: {location}")
                proc = start_job_proc(location)
                self._job_procs[location] = proc

                # Queue is created in start_job_proc
                self._job_queues[location] = job_queues[location]

                return self._job_queues[location], ""

            except Exception as e:
                logger.error(f"Failed to start processor for {location}: {e}")
                self._cleanup_location(location)
                return None, f"Failed to start job processor: {e}"

    def _cleanup_location(self, location: str):
        """Clean up resources for a specific location"""
        try:
            logger.debug("START _cleanup_location")
            if location in self._job_procs:
                logger.debug("-- location is in _job_procs")
                proc = self._job_procs[location]
                if proc.is_alive():
                    logger.debug("-- proc is alive")
                    self._job_queues[location].put('KILL')
                    logger.debug("-- proc put KILL in queue")
                    proc.join(timeout=5)
                    logger.debug("-- proc after join")
                else:
                    logger.debug("-- prod NOT alive")
                del self._job_procs[location]
                logger.debug("-- proc after deleting _job_procs[location]")
            if location in self._job_queues:
                logger.debug("-- location is in _job_queues")
                del self._job_queues[location]
            else:
                logger.debug("-- location NOT in _job_queues")
        except Exception as e:
            logger.error(f"Error cleaning up location {location}: {e}")

        logger.debug("END _cleanup_location")


    def cleanup(self):
        """Cleanup all job processors"""
        with self._lock:
            locations = list(self._job_procs.keys())
            logger.debug(f"Cleanup locations: {locations}")
            for location in locations:
                self._cleanup_location(location)

# Global instance
location_manager = LocationManager() 
