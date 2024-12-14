"""
Task thread management for sensor-specific PCAP collection
"""
from threading import Thread
from queue import Queue
import subprocess
import os
import time
from typing import Dict, Optional
import json

from core import logger, db, config
from simpleLogger import SimpleLogger

# Task status values matching SQL enum
TASK_STATUS = {
    'SUBMITTED': 'Submitted',
    'RUNNING': 'Running',
    'RETRIEVING': 'Retrieving',
    'COMPLETE': 'Complete',
    'FAILED': 'Failed',
    'SKIPPED': 'Skipped',
    'ABORTED': 'Aborted'
}

def start_task_thread(
    sensor_name: str,
    sensor_fqdn: str,
    job_id: int,
    job_params: dict,
    status_queue: Queue
) -> Thread:
    """Start a new task thread for a sensor

    Args:
        sensor_name: Name of the sensor
        sensor_fqdn: FQDN of the sensor
        job_id: ID of the parent job
        job_params: Job parameters
        status_queue: Queue to report status updates
    """
    thread = Thread(
        target=task_thread,
        args=(sensor_name, sensor_fqdn, job_id, job_params, status_queue)
    )
    thread.start()
    return thread

def task_thread(
    sensor_name: str,
    sensor_fqdn: str,
    job_id: int,
    job_params: dict,
    status_queue: Queue
) -> None:
    """Main task thread function that handles PCAP collection for a sensor

    Args:
        sensor_name: Name of the sensor
        sensor_fqdn: FQDN of the sensor
        job_id: ID of the parent job
        job_params: Job parameters
        status_queue: Queue to report status updates
    """
    logger = SimpleLogger(f"task_thread_{sensor_name}")
    logger.info(f"Starting task for sensor {sensor_name}")

    try:
        # Create task record
        task_id = create_task_record(job_id, sensor_name)
        if not task_id:
            status_queue.put({
                'status': TASK_STATUS['FAILED'],
                'result': {'message': 'Failed to create task record'}
            })
            return

        # Update status to running
        update_task_status(task_id, TASK_STATUS['RUNNING'])
        status_queue.put({'status': TASK_STATUS['RUNNING']})

        # Run PCAP collection
        success, result = run_pcap_collection(
            sensor_fqdn,
            job_params,
            task_id
        )

        if not success:
            update_task_status(task_id, TASK_STATUS['FAILED'], result)
            status_queue.put({
                'status': TASK_STATUS['FAILED'],
                'result': result
            })
            return

        # Download PCAP if collection successful
        if result.get('has_data'):
            # Update to retrieving state
            update_task_status(task_id, TASK_STATUS['RETRIEVING'], {
                'temp_path': f'/tmp/task_{task_id}.pcap'
            })
            status_queue.put({'status': TASK_STATUS['RETRIEVING']})

            success, download_result = download_pcap(
                sensor_fqdn,
                task_id,
                result.get('remote_path')
            )
            if not success:
                update_task_status(task_id, TASK_STATUS['FAILED'], download_result)
                status_queue.put({
                    'status': TASK_STATUS['FAILED'],
                    'result': download_result
                })
                return

            result.update(download_result)

        # Update final status
        update_task_status(task_id, TASK_STATUS['COMPLETE'], {
            'file_size': result.get('file_size', '0'),
            'message': 'Task completed successfully'
        })
        status_queue.put({
            'status': TASK_STATUS['COMPLETE'],
            'result': result,
            'has_data': result.get('has_data', False)
        })

    except Exception as e:
        logger.error(f"Error in task thread: {e}")
        status_queue.put({
            'status': TASK_STATUS['FAILED'],
            'result': {'message': str(e)}
        })

def create_task_record(job_id: int, sensor_name: str) -> Optional[int]:
    """Create task record in database"""
    try:
        task_id = db("""
            INSERT INTO tasks (
                job_id,
                sensor,
                status,
                pcap_size,
                temp_path,
                result_message,
                start_time,
                end_time,
                created_at
            ) VALUES (
                %s, %s, %s::task_status, NULL, NULL, NULL, NULL, NULL, NOW()
            ) RETURNING id
        """, (job_id, sensor_name, TASK_STATUS['SUBMITTED']))[0]['id']
        return task_id
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
                    start_time = NOW()
                WHERE id = %s
            """, (TASK_STATUS['RUNNING'], task_id))
            
        elif status == TASK_STATUS['RETRIEVING']:
            db("""
                UPDATE tasks 
                SET status = %s,
                    temp_path = %s
                WHERE id = %s
            """, (TASK_STATUS['RETRIEVING'], result.get('temp_path'), task_id))
            
        elif status in [TASK_STATUS['COMPLETE'], TASK_STATUS['FAILED'], TASK_STATUS['SKIPPED']]:
            db("""
                UPDATE tasks 
                SET status = %s,
                    end_time = NOW(),
                    pcap_size = %s,
                    result_message = %s
                WHERE id = %s
            """, (
                status,
                result.get('file_size'),
                result.get('message', json.dumps(result)),
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

def run_pcap_collection(
    sensor_fqdn: str,
    job_params: dict,
    task_id: int
) -> tuple[bool, dict]:
    """Run PCAP collection on remote sensor

    Returns:
        Tuple of (success, result_dict)
    """
    try:
        # TODO: Implement SSH to sensor and run_job.py BEGIN
        # For now, return dummy success
        logger.info("DEBUG RUN JOB START")
        from time import sleep
        sleep(3)
        logger.info("DEBUG RUN JOB FINISH")
        # Implement SSH to sensor and run_job.py END

        return True, {
            'has_data': True,
            'remote_path': f'/tmp/pcap_{task_id}.pcap'
        }
    except Exception as e:
        return False, {'error': str(e)}

def download_pcap(
    sensor_fqdn: str,
    task_id: int,
    remote_path: str
) -> tuple[bool, dict]:
    """Download PCAP file from sensor

    Returns:
        Tuple of (success, result_dict)
    """
    try:
        # TODO: Implement SCP/SFTP download BEGIN
        # For now, return dummy success
        logger.info("[[[ DEBUG DOWNLOAD BEGIN ]]]")
        from time import sleep
        sleep(3)
        logger.info("[[[ DEBUG DOWNLOAD END ]]]")
        # Implement SCP/SFTP download END

        local_path = f'/tmp/task_{task_id}.pcap'
        return True, {
            'local_path': local_path,
            'file_size': 1024
        }
    except Exception as e:
        return False, {'error': str(e)}
