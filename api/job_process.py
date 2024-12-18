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
from queue import Empty

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

def monitor_tasks(job_id: int, task_queues: Dict[str, Queue], task_threads: Dict[str, threading.Thread]) -> None:
    """Monitor task threads until completion and update job status"""
    try:
        completed_tasks = set()
        task_results = {}
        
        while len(completed_tasks) < len(task_threads):
            for sensor_name, queue in task_queues.items():
                if sensor_name in completed_tasks:
                    continue
                    
                try:
                    # Get status update if available
                    status = queue.get_nowait()
                    task_results[sensor_name] = status
                    
                    # If task is in final state
                    if status['status'] in [TASK_STATUS['COMPLETE'], TASK_STATUS['FAILED'], TASK_STATUS['SKIPPED']]:
                        completed_tasks.add(sensor_name)
                        
                        # Thread cleanup can happen here since we have its final status
                        if task_threads[sensor_name].is_alive():
                            task_threads[sensor_name].join(timeout=5)
                        
                except Empty:
                    continue
                
            # Update job status based on current state
            update_job_status(job_id, determine_job_status(task_results))
            time.sleep(0.1)
        
        # All tasks have reported completion
        # Final cleanup of any remaining threads
        cleanup_tasks(task_threads)
        
    except Exception as e:
        logger.error(f"Error monitoring tasks: {e}")
        update_job_failed(job_id, f"Error monitoring tasks: {e}")

def determine_job_status(task_results: Dict[str, dict]) -> tuple[str, str]:
    """Determine job status based on task results
    
    Returns:
        Tuple of (status, message)
    """
    if not task_results:
        return 'Failed', 'No task results available'
        
    complete_count = 0
    failed_count = 0
    messages = []
    
    for sensor_name, result in task_results.items():
        status = result['status']
        if status == TASK_STATUS['COMPLETE']:
            complete_count += 1
            has_data = result.get('result', {}).get('has_data', False)
            messages.append(f"{sensor_name}: Complete{'with data' if has_data else 'no data'}")
        elif status in [TASK_STATUS['FAILED'], TASK_STATUS['SKIPPED']]:
            failed_count += 1
            messages.append(f"{sensor_name}: {status}")
            
    total_tasks = len(task_results)
    
    if complete_count == total_tasks:
        return 'Complete', 'All tasks completed successfully'
    elif complete_count > 0:
        return 'Partially Complete', f"{complete_count}/{total_tasks} tasks completed"
    else:
        return 'Failed', 'No tasks completed successfully'

def update_job_status(job_id: int, status_info: tuple[str, str]) -> None:
    """Update job status and message"""
    try:
        status, message = status_info
        db("""
            UPDATE jobs 
            SET status = %s,
                result_message = %s,
                updated_at = NOW(),
                completed_at = CASE 
                    WHEN %s IN ('Complete', 'Failed', 'Partially Complete') THEN NOW()
                    ELSE NULL
                END
            WHERE id = %s
        """, (status, message, status, job_id))
    except Exception as e:
        logger.error(f"Error updating job {job_id} status: {e}")

def cleanup_tasks(task_threads: Dict[str, threading.Thread]) -> None:
    """Cleanup task threads"""
    for thread in task_threads.values():
        try:
            if thread.is_alive():
                thread.join(timeout=5)
        except Exception as e:
            logger.error(f"Error cleaning up task thread: {e}")
