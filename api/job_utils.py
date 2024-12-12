"""
Utility functions and shared components for job management
"""
import os
import configparser
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any, Union
import json
from core import (
    logger, db, config, parse_and_convert_to_utc, generate_signed_url,
    STATUS, RESULTS
)
from api.auth import get_user_role
from api.sensor_threads import sensor_queues, sensor_threads, Thread, sensor_thread

# Constants for event time calculations
EVENT_START_BEFORE = 1  # minutes before event time
EVENT_END_AFTER = 4     # minutes after event time

# Shared paths configuration
try:
    PCAP_PATH = os.path.abspath(os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        config.get('DOWNLOADS', 'pcap_path')
    ))
    IMG_PATH = os.path.abspath(os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        config.get('DOWNLOADS', 'img_path')
    ))

    # Ensure directories exist
    os.makedirs(PCAP_PATH, exist_ok=True)
    os.makedirs(IMG_PATH, exist_ok=True)

except (configparser.Error, ValueError, OSError) as e:
    logger.error(f"Configuration error: {e}")
    raise SystemExit("Failed to load critical configuration values")

def process_job_submission(
    username: str,
    sensor: str,
    src_ip: str,
    dst_ip: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    description: str = "",
    event_time: Optional[str] = None,
    tz: str = '+00:00'
) -> Dict[str, Union[Tuple, None]]:
    """
    Process a new job submission with validation and time conversion

    Args:
        username: The username submitting the job
        sensor: Target sensor name
        src_ip: Source IP address
        dst_ip: Destination IP address
        start_time: Optional job start time
        end_time: Optional job end time
        description: Job description
        event_time: Optional event time
        tz: Timezone offset (default: '+00:00')

    Returns:
        Dict containing either processed values tuple or error message
    """
    logger.debug(
        f"Starting process_job_submission with args: username={username}, "
        f"sensor={sensor}, src_ip={src_ip}, dst_ip={dst_ip}, "
        f"start_time={start_time}, end_time={end_time}, description={description}, "
        f"event_time={event_time}, tz={tz}"
    )

    try:
        # Convert provided times to UTC
        utc_event_time = parse_and_convert_to_utc(event_time, tz) if event_time else None
        utc_start_time = parse_and_convert_to_utc(start_time, tz) if start_time else None
        utc_end_time = parse_and_convert_to_utc(end_time, tz) if end_time else None

        # Handle time calculations based on provided values
        if utc_event_time:
            # Calculate start_time if not provided
            if not utc_start_time:
                utc_start_time = utc_event_time - timedelta(minutes=EVENT_START_BEFORE)
            
            # Calculate end_time if not provided
            if not utc_end_time:
                utc_end_time = utc_event_time + timedelta(minutes=EVENT_END_AFTER)
        else:
            # If no event_time, both start and end times must be provided
            if not utc_start_time or not utc_end_time:
                raise ValueError("Both start_time and end_time must be provided when event_time is not specified")

        # Validate time values
        if utc_end_time <= utc_start_time:
            raise ValueError("End time must be after start time")

        # Prepare job data
        job_data = {
            'username': username,
            'description': description,
            'sensor': sensor,
            'src_ip': src_ip,
            'dst_ip': dst_ip,
            'event_time': utc_event_time,
            'start_time': utc_start_time,
            'end_time': utc_end_time
        }

        return {
            'values': tuple(job_data.values()),
            'error': None
        }

    except Exception as e:
        logger.error(f"Job submission processing error: {e}")
        return {
            'values': None,
            'error': f"Failed to submit job: {e}"
        }

def check_job_permissions(job_id: int, username: str) -> Tuple[bool, Optional[str], int]:
    """
    Check if user has permission to access/modify a job

    Args:
        job_id: The ID of the job to check
        username: The username requesting access

    Returns:
        Tuple of (has_permission, error_message, http_status_code)
    """
    job = db("SELECT status, submitted_by FROM jobs WHERE id = %s", (job_id,))

    if not job:
        return False, "Job not found", 404

    if job[0][1] != username:
        user_role = get_user_role(username)
        if user_role != 'admin':
            return False, "Permission denied", 403

    return True, None, 200

def format_job_data(row: Tuple) -> Dict[str, Any]:
    """
    Format raw job database row into JSON-friendly dictionary

    Args:
        row: Database row tuple containing job data

    Returns:
        Dictionary with formatted job data
    """
    return {
        'id': row[0],
        'username': row[1],
        'description': row[2],
        'sensor': row[3],
        'event_time': row[4].isoformat() if row[4] else None,
        'start_time': row[5].isoformat() if row[5] else None,
        'end_time': row[6].isoformat() if row[6] else None,
        'status': row[7],
        'started': row[8].isoformat() if row[8] else None,
        'completed': row[9].isoformat() if row[9] else None,
        'result': row[10],
        'filename': row[11],
        'analysis': row[12],
        'tz': row[13]
    }
