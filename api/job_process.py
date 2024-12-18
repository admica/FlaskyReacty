"""
Job process management for location-based PCAP jobs
"""
from multiprocessing import Process, Queue
from typing import Dict, Optional
import threading
from datetime import datetime
import time
import json
import os

from core import logger, db, config
from simpleLogger import SimpleLogger
from api.task_thread import start_task_thread, TASK_STATUS

# Global dictionaries for job queues and processes
# These are now primarily managed through LocationManager
job_queues: Dict[str, Queue] = {}
job_procs: Dict[str, Process] = {}

def start_job_proc(location: str) -> Process:
    """Start a new job process for a location"""
    queue = Queue()
    job_queues[location] = queue
    proc = Process(target=job_proc, args=(location, queue))
    proc.start()
    return proc

def job_proc(location: str, queue: Queue) -> None:
    """Main job process function that handles jobs for a location

    Args:
        location: Location identifier (e.g. 'KSC')
        queue: Queue to receive jobs on
    """
    logger = SimpleLogger(f"job_proc_{location}")
    logger.info(f"Starting job processor for {location}")

    while True:
        try:
            # Wait for job from queue
            job = queue.get() # Block until a job arrives
            if job == 'KILL':
                logger.info(f"Shutting down job processor for {location}")
                return

            logger.info(f"Received job for location {location}: {job}")

            # Create job record
            job_id = create_job_record(job)
            if not job_id:
                logger.error("Failed to create job record")
                continue

            # Get sensors for location
            sensors = get_location_sensors(location)
            if not sensors:
                update_job_failed(job_id, "No sensors found for location")
                continue

            # Start task threads
            task_queues = {}  # sensor_name -> Queue
            task_threads = {} # sensor_name -> Thread

            for sensor in sensors:
                task_queue = Queue()
                task_queues[sensor['name']] = task_queue

                thread = start_task_thread(
                    sensor['name'],
                    sensor['fqdn'],
                    job_id,
                    job,
                    task_queue
                )
                task_threads[sensor['name']] = thread

            # Monitor tasks until completion
            monitor_tasks(job_id, task_queues, task_threads)

            # After tasks complete, clean up threads
            cleanup_tasks(task_threads)

            # Continue listening for next job
            continue

        except Exception as e:
            logger.error(f"Error in job processor: {e}")
            continue

def get_location_sensors(location: str) -> list:
    """Get list of active sensors for a location"""
    try:
        rows = db("""
            SELECT name, fqdn 
            FROM sensors 
            WHERE location = %s 
            AND status != 'Offline'
            ORDER BY name
        """, (location,))
        
        return [{'name': row[0], 'fqdn': row[1]} for row in rows]
    except Exception as e:
        logger.error(f"Error getting sensors for location {location}: {e}")
        return []

def create_job_record(job: dict) -> Optional[int]:
    """Create a new job record in the database"""
    try:
        result = db("""
            INSERT INTO jobs (
                location, submitted_by, src_ip, dst_ip,
                event_time, start_time, end_time, description,
                status
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, 'Submitted'
            ) RETURNING id
        """, (
            job['location'],
            job['submitted_by'],
            job['src_ip'],
            job['dst_ip'],
            job.get('event_time'),  # May be None
            job['start_time'],
            job['end_time'],
            job['description']
        ))
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error creating job record: {e}")
        return None

def update_job_failed(job_id: int, message: str):
    """Update job status to failed with message"""
    try:
        db("""
            UPDATE jobs 
            SET status = 'Failed',
                result_message = %s,
                end_time = NOW()
            WHERE id = %s
        """, (message, job_id))
    except Exception as e:
        logger.error(f"Error updating job {job_id} status: {e}")

def cleanup_tasks(task_threads: Dict[str, Process]) -> None:
    """Cleanup task threads"""
    for thread in task_threads.values():
        try:
            thread.join(timeout=5)
        except Exception as e:
            logger.error(f"Error cleaning up task thread: {e}")
