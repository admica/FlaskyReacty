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
        job_params: Job parameters including output_path
        status_queue: Queue to report status updates
    """
    logger = SimpleLogger(f"task_thread_{sensor_name}")
    logger.info(f"Starting task for sensor {sensor_name}")

    try:
        # Report initial running status
        status_queue.put({
            'sensor': sensor_name,
            'status': TASK_STATUS['RUNNING'],
            'result': None
        })

        # Run PCAP collection
        success, result = run_pcap_collection(
            sensor_fqdn,
            job_params,
            job_id
        )

        if not success:
            status_queue.put({
                'sensor': sensor_name,
                'status': TASK_STATUS['FAILED'],
                'result': result
            })
            return

        # Download PCAP if collection successful
        if result.get('has_data'):
            # Update to retrieving state
            status_queue.put({
                'sensor': sensor_name,
                'status': TASK_STATUS['RETRIEVING'],
                'result': {'temp_path': job_params['output_path']}
            })

            success, download_result = download_pcap(
                sensor_fqdn,
                job_params['output_path'],
                result.get('remote_path')
            )
            if not success:
                status_queue.put({
                    'sensor': sensor_name,
                    'status': TASK_STATUS['FAILED'],
                    'result': download_result
                })
                return

            result.update(download_result)

        # Send final success status
        status_queue.put({
            'sensor': sensor_name,
            'status': TASK_STATUS['COMPLETE'],
            'result': result,
            'has_data': result.get('has_data', False)
        })

    except Exception as e:
        logger.error(f"Error in task thread: {e}")
        status_queue.put({
            'sensor': sensor_name,
            'status': TASK_STATUS['FAILED'],
            'result': {'message': str(e)}
        })

def run_pcap_collection(
    sensor_fqdn: str,
    job_params: dict,
    job_id: int
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
            'remote_path': f'/tmp/pcap_{job_id}.pcap'
        }
    except Exception as e:
        return False, {'error': str(e)}

def download_pcap(
    sensor_fqdn: str,
    output_path: str,
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

        return True, {
            'local_path': output_path,
            'file_size': 1024
        }
    except Exception as e:
        return False, {'error': str(e)}
