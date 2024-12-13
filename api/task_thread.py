"""
Task thread management for sensor-specific PCAP collection
"""
from threading import Thread
from queue import Queue
import subprocess
import os
import time
from typing import Dict, Optional

from core import logger, db, config
from simpleLogger import SimpleLogger

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
                'status': 'failed',
                'result': {'error': 'Failed to create task record'}
            })
            return
            
        # Update status to running
        update_task_status(task_id, 'running')
        status_queue.put({'status': 'running'})
        
        # Run PCAP collection
        success, result = run_pcap_collection(
            sensor_fqdn,
            job_params,
            task_id
        )
        
        if not success:
            update_task_status(task_id, 'failed', result)
            status_queue.put({
                'status': 'failed',
                'result': result
            })
            return
            
        # Download PCAP if collection successful
        if result.get('has_data'):
            success, download_result = download_pcap(
                sensor_fqdn,
                task_id,
                result.get('remote_path')
            )
            if not success:
                update_task_status(task_id, 'failed', download_result)
                status_queue.put({
                    'status': 'failed',
                    'result': download_result
                })
                return
                
            result.update(download_result)
            
        # Update final status
        update_task_status(task_id, 'completed', result)
        status_queue.put({
            'status': 'completed',
            'result': result,
            'has_data': result.get('has_data', False)
        })
        
    except Exception as e:
        logger.error(f"Error in task thread: {e}")
        status_queue.put({
            'status': 'failed',
            'result': {'error': str(e)}
        })

def create_task_record(job_id: int, sensor_name: str) -> Optional[int]:
    """Create task record in database"""
    try:
        task_id = db("""
            INSERT INTO tasks
            (job_id, sensor_name, status, created_at)
            VALUES (%s, %s, 'submitted', NOW())
            RETURNING id
        """, (job_id, sensor_name))[0]['id']
        return task_id
    except Exception as e:
        logger.error(f"Error creating task record: {e}")
        return None

def update_task_status(task_id: int, status: str, result: dict = None) -> None:
    """Update task status in database"""
    try:
        db("""
            UPDATE tasks
            SET status = %s,
                result = %s,
                modified_at = NOW()
            WHERE id = %s
        """, (
            status,
            json.dumps(result) if result else None,
            task_id
        ))
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
