"""
Core job management endpoints for the PCAP Server API
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
import os
import traceback
from typing import Dict, List, Optional, Tuple
from datetime import timedelta
from core import (
    logger, db, db_pool, rate_limit, STATUS, RESULTS,
    parse_and_convert_to_utc
)
from api.auth import get_user_role, activity_tracking
from api.sensor_threads import (
    sensor_queues, sensor_threads, Thread, sensor_thread,
    EVENT_START_BEFORE, EVENT_END_AFTER
)
from .job_utils import (
    process_job_submission, check_job_permissions, format_job_data,
    PCAP_PATH, IMG_PATH
)

# Blueprint Registration
jobs_bp = Blueprint('jobs', __name__)

@jobs_bp.route('/api/v1/submit', methods=['POST'])
@jwt_required()
@rate_limit()
def submit_job():
    """Submit a new location-based PCAP job"""
    try:
        username = get_jwt_identity()
        logger.debug(f"Processing job submission for user: {username}")

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Extract required fields
        location = data.get('location')
        src_ip = data.get('src_ip', '').strip()
        dst_ip = data.get('dst_ip', '').strip()
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        description = data.get('description', '')
        tz = data.get('tz', '+00:00')
        event_time = data.get('event_time')

        # Validate required fields
        errors = []
        if not location:
            errors.append("Location is required")
        if not src_ip and not dst_ip:
            errors.append("At least one IP address (source or destination) is required")
        if not event_time and (not start_time or not end_time):
            errors.append("Either event time or both start time and end time are required")

        if errors:
            return jsonify({"error": "Validation failed", "messages": errors}), 400

        # Verify location exists and get distinct sensor names
        sensors = db("""
            SELECT DISTINCT name, status
            FROM sensors
            WHERE location = %s
        """, (location,))

        if not sensors:
            return jsonify({"error": f"No sensors found for location: {location}"}), 400

        # Check sensor states
        sensor_states = {sensor[0]: sensor[1] for sensor in sensors}
        offline_sensors = [name for name, status in sensor_states.items() if status == 'Offline']
        if offline_sensors:
            logger.warning(f"Some sensors are offline at location {location}: {offline_sensors}")

        # Process time parameters
        utc_start_time = parse_and_convert_to_utc(start_time, tz)
        utc_end_time = parse_and_convert_to_utc(end_time, tz)
        utc_event_time = parse_and_convert_to_utc(event_time, tz) if event_time else None

        # Handle event time logic
        if utc_event_time:
            utc_start_time = utc_event_time - timedelta(minutes=EVENT_START_BEFORE)
            utc_end_time = utc_event_time + timedelta(minutes=EVENT_END_AFTER)

        # Create the job in Submitted state
        job_id = db("""
            INSERT INTO jobs
            (location, description, source_ip, dest_ip, event_time,
             start_time, end_time, status, submitted_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Submitted', %s)
            RETURNING id
        """, (location, description, src_ip, dst_ip, utc_event_time,
              utc_start_time, utc_end_time, username))

        if not job_id:
            return jsonify({"error": "Failed to create job"}), 500

        job_id = job_id[0]

        # Create tasks for each sensor
        for sensor_name in sensor_states.keys():
            task_id = db("""
                INSERT INTO tasks
                (job_id, sensor, status)
                VALUES (%s, %s, 'Submitted')
                RETURNING id
            """, (job_id, sensor_name))

            if task_id:
                # Add task to sensor's queue if sensor is online
                if sensor_states[sensor_name] != 'Offline' and sensor_name in sensor_queues:
                    # Convert times to epochs for the run_job.py script
                    start_epoch = int(utc_start_time.timestamp())
                    end_epoch = int(utc_end_time.timestamp())

                    # Queue format: "<job_id>_<task_id>"
                    task_identifier = f"{job_id}_{task_id[0]}"
                    sensor_queues[sensor_name].put([
                        task_identifier,
                        start_epoch,
                        end_epoch,
                        'pcap',  # Default request type
                        src_ip or '',
                        dst_ip or ''
                    ])
                    logger.debug(f"Queued task {task_identifier} for sensor {sensor_name}")
                else:
                    logger.warning(f"Sensor {sensor_name} is offline or has no queue, task created but not queued")

        logger.info(f'{username} Job Submitted id={job_id}')
        return jsonify({
            "message": "Job submitted successfully",
            "job_id": job_id,
            "offline_sensors": offline_sensors if offline_sensors else None
        }), 201

    except Exception as e:
        logger.error(f'Error submitting job: {e}')
        logger.error(traceback.format_exc())
        return jsonify({"error": "Failed to submit job"}), 500

@jobs_bp.route('/api/v1/jobs', methods=['POST'])
@jwt_required()
@rate_limit()
def get_jobs():
    """Get jobs with JSON-based optional filtering"""
    try:
        # Get filter criteria from JSON body
        filters = request.get_json() or {}

        # Build query conditions and parameters
        conditions = ["1=1"]  # Always true condition to start
        params = []

        if filters.get('username'):
            conditions.append("username = %s")
            params.append(filters['username'])

        if filters.get('start_time'):
            conditions.append("start_time >= %s")
            params.append(filters['start_time'])

        if filters.get('end_time'):
            conditions.append("end_time <= %s")
            params.append(filters['end_time'])

        if filters.get('status'):
            conditions.append("status = %s")
            params.append(filters['status'])

        # Build and execute query
        query = f"""
            SELECT id, username, description, sensor, src_ip, dst_ip, event_time,
                   start_time, end_time, status, started, completed,
                   result, filename, analysis, tz
            FROM jobs
            WHERE {' AND '.join(conditions)}
            ORDER BY id DESC
            LIMIT 250
        """

        rows = db(query, params)
        if not rows:
            return jsonify([]), 200

        jobs = [format_job_data(row) for row in rows]
        return jsonify(jobs), 200

    except Exception as e:
        logger.error(f"Error fetching jobs: {e}")
        return jsonify({"error": "Failed to fetch jobs"}), 500

@jobs_bp.route('/api/v1/jobs/<int:job_id>', methods=['GET'])
@jwt_required()
@rate_limit()
def get_job(job_id):
    """Get details for a specific job"""
    try:
        current_user = get_jwt_identity()

        # Get job details
        job = db("""
            SELECT id, username, description, sensor, event_time,
                   start_time, end_time, status, started, completed,
                   result, filename, analysis, tz
            FROM jobs
            WHERE id = %s AND username = %s
        """, (job_id, current_user))

        if not job: return jsonify({"error": "Job not found"}), 404

        job_data = format_job_data(job[0])
        return jsonify(job_data), 200

    except Exception as e:
        logger.error(f"Error retrieving job details: {e}")
        return jsonify({"error": "Failed to retrieve job details"}), 500

@jobs_bp.route('/api/v1/jobs/<int:job_id>/cancel', methods=['POST'])
@jwt_required()
@rate_limit()
def cancel_job(job_id):
    """Cancel a running job"""
    try:
        username = get_jwt_identity()

        # Check permissions
        has_permission, error_msg, status_code = check_job_permissions(job_id, username)
        if not has_permission: return jsonify({"error": error_msg}), status_code

        # Get job info
        job = db("SELECT status FROM jobs WHERE id = %s", (job_id,))
        
        # Check if job can be cancelled
        if job[0][0] not in ['Submitted', 'Running']:
            return jsonify({"error": f"Cannot cancel job in {job[0][0]} state"}), 400

        # Start transaction for job and task updates
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                # Update job status
                cur.execute("""
                    UPDATE jobs
                    SET status = 'Aborted',
                        aborted_by = %s,
                        last_modified = NOW()
                    WHERE id = %s
                """, (username, job_id))

                # Update tasks that aren't in final state
                cur.execute("""
                    UPDATE tasks
                    SET status = 'Aborted',
                        modified_by = %s,
                        last_modified = NOW(),
                        end_time = NOW(),
                        result_message = 'Task aborted due to job cancellation'
                    WHERE job_id = %s
                    AND status NOT IN ('Complete', 'Failed', 'Skipped', 'Aborted')
                """, (username, job_id))

                # Get affected tasks for logging
                cur.execute("""
                    SELECT id, sensor
                    FROM tasks
                    WHERE job_id = %s
                """, (job_id,))
                tasks = cur.fetchall()

                conn.commit()

                # Log task abortion
                for task_id, sensor in tasks:
                    logger.info(f"Task {task_id} for sensor {sensor} aborted due to job {job_id} cancellation")

            return jsonify({
                "message": "Job cancelled successfully",
                "job_id": job_id,
                "tasks_affected": len(tasks)
            }), 200

        except Exception as e:
            conn.rollback()
            logger.error(f"Error in job cancellation transaction: {e}")
            return jsonify({"error": "Failed to cancel job"}), 500
        finally:
            db_pool.putconn(conn)

    except Exception as e:
        logger.error(f"Error cancelling job: {e}")
        return jsonify({"error": "Failed to cancel job"}), 500

@jobs_bp.route('/api/v1/jobs/<int:job_id>', methods=['DELETE'])
@jwt_required()
@rate_limit()
def delete_job(job_id):
    """Delete a completed job"""
    try:
        current_user = get_jwt_identity()
        
        # Check permissions
        has_permission, error_msg, status_code = check_job_permissions(job_id, current_user)
        if not has_permission:
            return jsonify({"error": error_msg}), status_code

        # Get job details
        job = db("""
            SELECT status, filename
            FROM jobs
            WHERE id = %s
        """, (job_id,))

        if not job:
            return jsonify({"error": "Job not found"}), 404

        status, filename = job[0]

        # Only allow deletion of jobs in terminal states
        if status not in ['Complete', 'Incomplete', 'Cancelled']:
            return jsonify({"error": "Job cannot be deleted in its current state"}), 400

        # Delete associated files
        try:
            # Delete PCAP file
            if filename:
                pcap_file = os.path.join(PCAP_PATH, filename)
                if os.path.exists(pcap_file):
                    os.remove(pcap_file)

            # Delete analysis images
            for suffix in ['proto', 'matrix', 'usage', 'size']:
                img_file = os.path.join(IMG_PATH, f"{job_id}.{suffix}.png")
                if os.path.exists(img_file):
                    os.remove(img_file)

            # Delete job from database
            db("DELETE FROM jobs WHERE id = %s", (job_id,))

            return jsonify({"message": "Job deleted successfully"}), 200

        except Exception as e:
            logger.error(f"Error deleting job files: {e}")
            return jsonify({"error": "Failed to delete job"}), 500

    except Exception as e:
        logger.error(f"Delete job error: {e}")
        return jsonify({"error": "Failed to delete job"}), 500
