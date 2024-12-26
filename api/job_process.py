"""
Job process management for location-based PCAP jobs
PATH: api/job_process.py
"""
from multiprocessing import Process, Queue
from typing import Dict, Optional
from threading import Thread
import threading
from datetime import datetime
import time
import json
import os
import shutil
from queue import Empty

from core import logger, db, config, JOBS_PATH, TASKS_PATH
from simpleLogger import SimpleLogger
from api.task_thread import start_task_thread, TASK_STATUS

# Global dictionaries for job queues and processes
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
    """Main job process function that handles jobs for a location"""
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
            task_counter = 1  # Sequential task ID counter

            for sensor in sensors:
                # Create task record with sequential ID
                task_filename = f"{TASKS_PATH}/{job_id}_{task_counter}.pcap"
                task_id = create_task_record(job_id, task_counter, sensor['name'])
                if not task_id:
                    logger.error(f"Failed to create task record for {sensor['name']}")
                    continue

                # Start task thread
                task_queue = Queue()
                thread = start_task_thread(
                    sensor_name=sensor['name'],
                    sensor_fqdn=sensor['fqdn'],
                    job_id=job_id,
                    job_params={
                        **job,
                        'output_path': task_filename
                    },
                    status_queue=task_queue
                )
                task_queues[sensor['name']] = task_queue
                task_threads[sensor['name']] = thread
                task_counter += 1

            # Monitor tasks until completion
            monitor_tasks(job_id, task_queues, task_threads)

            # After tasks complete, handle merging
            merge_task_results(job_id)

            # Clean up threads
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

def monitor_tasks(job_id: int, task_queues: Dict[str, Queue], task_threads: Dict[str, Thread]) -> None:
    """Monitor task threads until completion and update job status"""
    try:
        completed_tasks = set()
        last_update_time = {name: time.time() for name in task_threads.keys()}
        QUEUE_TIMEOUT = 1.0  # 1 second timeout per queue check
        TASK_TIMEOUT = 1800  # 30 minutes before considering a task dead

        while len(completed_tasks) < len(task_threads):
            current_time = time.time()

            # Check each task that hasn't completed
            for sensor_name, queue in task_queues.items():
                if sensor_name in completed_tasks:
                    continue

                thread = task_threads[sensor_name]

                # Get task record ID
                task_row = db("SELECT id FROM tasks WHERE job_id = %s AND sensor = %s", 
                            (job_id, sensor_name))
                if not task_row:
                    logger.error(f"No task record found for {sensor_name}")
                    continue

                task_id = task_row[0]

                # Check if thread died
                if not thread.is_alive():
                    logger.error(f"Task thread for {sensor_name} died unexpectedly")
                    if sensor_name not in completed_tasks:
                        update_task_status(task_id, TASK_STATUS['FAILED'], 
                                        {'message': 'Task thread died unexpectedly'})
                        completed_tasks.add(sensor_name)
                    continue

                # Check for task timeout
                if (current_time - last_update_time[sensor_name] > TASK_TIMEOUT and 
                    sensor_name not in completed_tasks):
                    logger.error(f"Task {sensor_name} timed out - no updates in {TASK_TIMEOUT} seconds")
                    update_task_status(task_id, TASK_STATUS['FAILED'],
                                    {'message': f'Task timed out after {TASK_TIMEOUT/60:.0f} minutes'})
                    completed_tasks.add(sensor_name)

                    # Kill the timed out thread
                    if thread.is_alive():
                        logger.warning(f"Killing timed out task thread for {sensor_name}")
                        thread._stop()
                    continue

                try:
                    # Check queue with timeout
                    status_update = queue.get(timeout=QUEUE_TIMEOUT)
                    last_update_time[sensor_name] = current_time

                    # Update task status in DB
                    update_task_status(task_id, status_update['status'], status_update.get('result'))

                    # If task is in final state
                    if status_update['status'] in [
                        TASK_STATUS['COMPLETE'], 
                        TASK_STATUS['FAILED'], 
                        TASK_STATUS['SKIPPED']
                    ]:
                        completed_tasks.add(sensor_name)

                except Empty:
                    # No update from this queue, continue to next
                    continue

            # Update job status based on task states
            update_job_status_from_tasks(job_id)

            # Small sleep between queue check cycles
            time.sleep(0.1)

        # All tasks have reported completion
        cleanup_tasks(task_threads)

    except Exception as e:
        logger.error(f"Error monitoring tasks: {e}")
        update_job_failed(job_id, f"Error monitoring tasks: {e}")

def create_task_record(job_id: int, task_id: int, sensor_name: str) -> Optional[int]:
    """Create task record in database"""
    try:
        result = db("""
            INSERT INTO tasks (
                job_id,
                task_id,
                sensor,
                status,
                pcap_size,
                temp_path,
                result_message,
                start_time,
                end_time,
                created_at
            ) VALUES (
                %s, %s, %s, %s::task_status, NULL, NULL, NULL, NULL, NULL, NOW()
            ) RETURNING id
        """, (job_id, task_id, sensor_name, TASK_STATUS['SUBMITTED']))
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error creating task record: {e}")
        return None

def update_task_status(task_id: int, status: str, result: dict = None) -> None:
    """Update task status in database"""
    try:
        if status == TASK_STATUS['RUNNING']:
            db("""
                UPDATE tasks 
                SET status = %s,
                    started_at = NOW()
                WHERE id = %s
            """, (status, task_id))

        elif status == TASK_STATUS['RETRIEVING']:
            # Use temp_path from result if provided
            temp_path = result.get('temp_path') if result else None
            db("""
                UPDATE tasks 
                SET status = %s,
                    temp_path = %s
                WHERE id = %s
            """, (status, temp_path, task_id))

        elif status in [TASK_STATUS['COMPLETE'], TASK_STATUS['FAILED'], TASK_STATUS['SKIPPED']]:
            db("""
                UPDATE tasks 
                SET status = %s,
                    completed_at = NOW(),
                    pcap_size = %s,
                    result_message = %s
                WHERE id = %s
            """, (
                status,
                result.get('file_size', '0') if status == TASK_STATUS['COMPLETE'] else None,
                json.dumps(result) if result else None,
                task_id
            ))
        else:
            db("""
                UPDATE tasks 
                SET status = %s,
                    result_message = %s
                WHERE id = %s
            """, (status, json.dumps(result) if result else None, task_id))

    except Exception as e:
        logger.error(f"Error updating task status: {e}")

def update_job_status_from_tasks(job_id: int) -> None:
    """Update job status based on current task states in DB"""
    try:
        # Get all task statuses for this job
        rows = db("""
            SELECT status, COUNT(*) 
            FROM tasks 
            WHERE job_id = %s 
            GROUP BY status
        """, (job_id,))

        status_counts = {row[0]: row[1] for row in rows}
        total_tasks = sum(status_counts.values())

        # Get current job status
        job_row = db("SELECT status FROM jobs WHERE id = %s", (job_id,))
        if not job_row:
            logger.error(f"No job record found for ID {job_id}")
            return

        current_status = job_row[0]

        # Don't update if job is in Merging state
        if current_status == 'Merging':
            return

        # Determine job status
        running_count = status_counts.get(TASK_STATUS['RUNNING'], 0)
        retrieving_count = status_counts.get(TASK_STATUS['RETRIEVING'], 0)
        if running_count > 0 or retrieving_count > 0:
            status = 'Running'
            active_tasks = []
            if running_count > 0:
                active_tasks.append(f"{running_count} running")
            if retrieving_count > 0:
                active_tasks.append(f"{retrieving_count} retrieving")
            message = f"{', '.join(active_tasks)}"
        elif status_counts.get(TASK_STATUS['COMPLETE'], 0) == total_tasks:
            status = 'Complete'
            message = 'All tasks completed successfully'
        elif status_counts.get(TASK_STATUS['COMPLETE'], 0) > 0:
            status = 'Partially Complete'
            message = f"{status_counts.get(TASK_STATUS['COMPLETE'], 0)}/{total_tasks} tasks completed"
        elif all(s in [TASK_STATUS['FAILED'], TASK_STATUS['SKIPPED']] for s in status_counts.keys()):
            status = 'Failed'
            message = 'No tasks completed successfully'
        else:
            status = 'Running'
            message = 'Tasks in progress'

        # Update job status
        db("""
            UPDATE jobs 
            SET status = %s,
                result_message = %s,
                updated_at = NOW(),
                started_at = CASE 
                    WHEN status = 'Submitted' AND %s = 'Running' THEN NOW()
                    ELSE started_at
                END,
                completed_at = CASE 
                    WHEN %s IN ('Complete', 'Failed', 'Partially Complete') THEN NOW()
                    ELSE NULL
                END
            WHERE id = %s
        """, (status, message, status, status, job_id))

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

def merge_task_results(job_id: int) -> None:
    """Merge task results for a job"""
    try:
        # Update job to merging state
        db("""
            UPDATE jobs 
            SET status = 'Merging',
                result_message = 'Merging task results',
                updated_at = NOW()
            WHERE id = %s
        """, (job_id,))

        # Get completed tasks with data
        tasks = db("""
            SELECT task_id, temp_path, pcap_size
            FROM tasks
            WHERE job_id = %s
            AND status = %s
            AND pcap_size IS NOT NULL
            ORDER BY task_id
        """, (job_id, TASK_STATUS['COMPLETE']))

        if not tasks:
            # No tasks with data
            db("""
                UPDATE jobs
                SET status = 'Complete',
                    result_message = 'No PCAP data available',
                    updated_at = NOW(),
                    completed_at = NOW()
                WHERE id = %s
            """, (job_id,))
            return

        # Set up final output path
        output_path = f"{JOBS_PATH}/{job_id}.pcap"

        if len(tasks) == 1:
            # Single file, just copy
            shutil.copy2(tasks[0][1], output_path)
            file_size = tasks[0][2]
        else:
            # Multiple files need merging
            # TODO: Implement actual PCAP merging
            # For now, just concatenate
            with open(output_path, 'wb') as outfile:
                total_size = 0
                for _, task_path, _ in tasks:
                    with open(task_path, 'rb') as infile:
                        shutil.copyfileobj(infile, outfile)
                        total_size += os.path.getsize(task_path)
            file_size = str(total_size)

        # Update job with final result
        db("""
            UPDATE jobs
            SET status = 'Complete',
                result_path = %s,
                result_size = %s,
                result_message = %s,
                updated_at = NOW(),
                completed_at = NOW()
            WHERE id = %s
        """, (
            output_path,
            file_size,
            f'Successfully merged {len(tasks)} PCAP files',
            job_id
        ))

    except Exception as e:
        logger.error(f"Error merging results for job {job_id}: {e}")
        db("""
            UPDATE jobs
            SET status = 'Failed',
                result_message = %s,
                updated_at = NOW(),
                completed_at = NOW()
            WHERE id = %s
        """, (f"Error merging results: {str(e)}", job_id))
