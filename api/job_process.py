"""
Job process management for location-based PCAP job
"""
from multiprocessing import Process, Queue
from typing import Dict
from datetime import datetime
import time
import json
import os

from core import logger, db, config
from simpleLogger import SimpleLogger

# Global process tracking
job_procs: Dict[str, Process] = {}  # location -> Process
job_queues: Dict[str, Queue] = {}   # location -> Queue

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
            job = queue.get()
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
            
            # Monitor tasks
            monitor_tasks(job_id, task_queues, task_threads)
            
        except Exception as e:
            logger.error(f"Error in job processor: {e}")
            continue

def create_job_record(job: dict) -> int:
    """Create job record in database"""
    try:
        job_id = db("""
            INSERT INTO jobs
            (location, params, status, created_at, created_by)
            VALUES (%s, %s, 'submitted', NOW(), %s)
            RETURNING id
        """, (
            job['location'],
            json.dumps(job),
            job['submitted_by']
        ))[0]['id']
        return job_id
    except Exception as e:
        logger.error(f"Error creating job record: {e}")
        return None

def get_location_sensors(location: str) -> list:
    """Get list of active sensors for location"""
    try:
        sensors = db("""
            SELECT name, fqdn
            FROM sensors
            WHERE location = %s
            AND status != 'Offline'
        """, (location,))
        return sensors
    except Exception as e:
        logger.error(f"Error getting sensors: {e}")
        return []

def update_job_failed(job_id: int, reason: str) -> None:
    """Update job as failed with reason"""
    try:
        db("""
            UPDATE jobs
            SET status = 'failed',
                result = %s,
                completed_at = NOW()
            WHERE id = %s
        """, (json.dumps({"error": reason}), job_id))
    except Exception as e:
        logger.error(f"Error updating job failure: {e}")

def monitor_tasks(job_id: int, task_queues: Dict[str, Queue], task_threads: Dict[str, Process]) -> None:
    """Monitor task threads and handle completion"""
    logger = SimpleLogger(f"job_monitor_{job_id}")
    start_time = time.time()
    
    while (time.time() - start_time) < config.getint('REQUESTS', 'max_secs', fallback=900):
        all_complete = True
        has_data = False
        
        # Check each task queue for updates
        for sensor_name, queue in task_queues.items():
            try:
                update = queue.get(timeout=1)
                if update:
                    handle_task_update(job_id, sensor_name, update)
                    
                    if update.get('status') not in ['completed', 'failed', 'skipped']:
                        all_complete = False
                    if update.get('has_data'):
                        has_data = True
            except Exception:
                all_complete = False
                continue
        
        if all_complete:
            handle_job_completion(job_id, has_data)
            break
            
    # Cleanup
    cleanup_tasks(task_threads)

def handle_task_update(job_id: int, sensor_name: str, update: dict) -> None:
    """Handle status update from task thread"""
    try:
        db("""
            UPDATE tasks
            SET status = %s,
                result = %s,
                modified_at = NOW()
            WHERE job_id = %s
            AND sensor_name = %s
        """, (
            update['status'],
            json.dumps(update.get('result', {})),
            job_id,
            sensor_name
        ))
    except Exception as e:
        logger.error(f"Error updating task status: {e}")

def handle_job_completion(job_id: int, has_data: bool) -> None:
    """Handle job completion and PCAP merging if needed"""
    try:
        if not has_data:
            db("""
                UPDATE jobs
                SET status = 'completed',
                    result = %s,
                    completed_at = NOW()
                WHERE id = %s
            """, (
                json.dumps({"message": "No PCAP data found"}),
                job_id
            ))
            return
            
        # TODO: Implement PCAP merging BEGIN
        logger.info("Mercap merging placeholder start")
        from time import sleep
        sleep(3)
        logger.info("Mercap merging placeholder finish")
        # END Implement PCAP merging END

    except Exception as e:
        logger.error(f"Error handling job completion: {e}")

def cleanup_tasks(task_threads: Dict[str, Process]) -> None:
    """Cleanup task threads"""
    for thread in task_threads.values():
        try:
            thread.join(timeout=5)
        except Exception as e:
            logger.error(f"Error cleaning up task thread: {e}") 
