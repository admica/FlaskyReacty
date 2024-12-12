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
    sensor_queues, sensor_threads, Thread, sensor_thread
)
from .job_utils import (
    process_job_submission, check_job_permissions, format_job_data,
    PCAP_PATH, IMG_PATH, EVENT_START_BEFORE, EVENT_END_AFTER
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
        logger.info(f"Processing job submission for user: {username}")

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Extract fields
        location = data.get('location')
        src_ip = data.get('src_ip', '').strip()
        dst_ip = data.get('dst_ip', '').strip()
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        description = data.get('description', '')
        tz = data.get('tz', '+00:00')
        event_time = data.get('event_time')

        logger.info(f"Job request - Location: {location}, Source IP: {src_ip}, Dest IP: {dst_ip}, "
                   f"Event Time: {event_time}, Start: {start_time}, End: {end_time}, TZ: {tz}")

        # Validate required fields
        errors = []
        if not location:
            errors.append("Location is required")
        if not src_ip and not dst_ip:
            errors.append("At least one IP address (source or destination) is required")
        if not event_time and (not start_time or not end_time):
            errors.append("Either event time or both start time and end time are required")

        if errors:
            logger.warning(f"Job validation failed: {errors}")
            return jsonify({"error": "Validation failed", "messages": errors}), 400

        # First verify location exists
        logger.debug(f"Verifying location exists: {location}")
        loc = db("SELECT site FROM locations WHERE site = %s", (location,))
        if not loc:
            logger.warning(f"Invalid location requested: {location}")
            return jsonify({"error": f"Invalid location: {location}"}), 400

        # Then get all sensors for location
        logger.debug(f"Getting sensors for location: {location}")
        sensors = db("""
            SELECT name, status, fqdn
            FROM sensors
            WHERE location = %s
        """, (location,))

        if not sensors:
            logger.warning(f"No sensors found for location: {location}")
            return jsonify({"error": f"No sensors found for location: {location}"}), 400

        # Check sensor states
        active_sensors = [s for s in sensors if s[1] != 'Offline']
        offline_sensors = [s[0] for s in sensors if s[1] == 'Offline']

        logger.info(f"Found {len(active_sensors)} active and {len(offline_sensors)} offline sensors")
        logger.debug(f"Active sensors: {[s[0] for s in active_sensors]}")
        if offline_sensors:
            logger.warning(f"Offline sensors: {offline_sensors}")

        if not active_sensors:
            logger.error(f"No active sensors available for location: {location}")
            return jsonify({"error": f"No active sensors found for location: {location}"}), 400

        # Process job submission with new time handling
        result = process_job_submission(
            username=username,
            sensor=active_sensors[0][0],  # Use first active sensor
            src_ip=src_ip,
            dst_ip=dst_ip,
            start_time=start_time,
            end_time=end_time,
            description=description,
            event_time=event_time,
            tz=tz
        )

        if result.get('error'):
            logger.error(f"Job submission failed: {result['error']}")
            return jsonify({"error": result['error']}), 400

        # Create job record
        job_data = result['data']
        job_id = db("""
            INSERT INTO jobs (
                location, description, source_ip, dest_ip,
                event_time, start_time, end_time, status,
                submitted_by
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, 'Submitted', %s
            ) RETURNING id
        """, (
            location, description, src_ip, dst_ip,
            job_data['event_time'], job_data['start_time'],
            job_data['end_time'], username
        ), fetch_one=True)[0]

        logger.info(f"Created job {job_id} for user {username}")
        return jsonify({"job_id": job_id}), 201

    except Exception as e:
        logger.error(f"Error submitting job: {e}")
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
    """Get details for a specific job including task summary"""
    try:
        username = get_jwt_identity()
        logger.debug(f"Getting job {job_id} details for user {username}")

        # Get job and task summary in one query
        job = db("""
            SELECT 
                j.*,
                COUNT(t.id) as total_tasks,
                SUM(CASE WHEN t.status = 'Complete' AND t.pcap_size IS NOT NULL THEN 1 ELSE 0 END) as tasks_with_data,
                SUM(CASE WHEN t.status = 'Complete' AND t.pcap_size IS NULL THEN 1 ELSE 0 END) as tasks_no_data,
                SUM(CASE WHEN t.status = 'Failed' THEN 1 ELSE 0 END) as tasks_failed,
                SUM(CASE WHEN t.status = 'Skipped' THEN 1 ELSE 0 END) as tasks_skipped,
                SUM(CASE WHEN t.status = 'Running' THEN 1 ELSE 0 END) as tasks_running,
                SUM(CASE WHEN t.status = 'Downloading' THEN 1 ELSE 0 END) as tasks_downloading,
                SUM(CASE WHEN t.status = 'Submitted' THEN 1 ELSE 0 END) as tasks_submitted,
                SUM(CASE WHEN t.status = 'Aborted' THEN 1 ELSE 0 END) as tasks_aborted,
                STRING_AGG(
                    CASE WHEN t.pcap_size IS NOT NULL 
                    THEN t.sensor || ':' || t.pcap_size 
                    ELSE NULL END,
                    ', '
                ) as sensor_data
            FROM jobs j
            LEFT JOIN tasks t ON j.id = t.job_id
            WHERE j.id = %s
            GROUP BY j.id
        """, (job_id,))

        if not job:
            logger.warning(f"Job {job_id} not found")
            return jsonify({"error": "Job not found"}), 404

        # Check permissions
        if job[0]['submitted_by'] != username and get_user_role(username) != 'admin':
            logger.warning(f"User {username} denied access to job {job_id}")
            return jsonify({"error": "Permission denied"}), 403

        # Format response
        job_data = {
            "id": job[0]['id'],
            "location": job[0]['location'],
            "description": job[0]['description'],
            "source_ip": str(job[0]['source_ip']) if job[0]['source_ip'] else None,
            "dest_ip": str(job[0]['dest_ip']) if job[0]['dest_ip'] else None,
            "event_time": job[0]['event_time'].isoformat() if job[0]['event_time'] else None,
            "start_time": job[0]['start_time'].isoformat() if job[0]['start_time'] else None,
            "end_time": job[0]['end_time'].isoformat() if job[0]['end_time'] else None,
            "status": job[0]['status'],
            "submitted_by": job[0]['submitted_by'],
            "aborted_by": job[0]['aborted_by'],
            "result_size": job[0]['result_size'],
            "result_path": job[0]['result_path'],
            "created_at": job[0]['created_at'].isoformat(),
            "last_modified": job[0]['last_modified'].isoformat(),
            "task_summary": {
                "total": job[0]['total_tasks'],
                "with_data": job[0]['tasks_with_data'],
                "no_data": job[0]['tasks_no_data'],
                "failed": job[0]['tasks_failed'],
                "skipped": job[0]['tasks_skipped'],
                "running": job[0]['tasks_running'],
                "downloading": job[0]['tasks_downloading'],
                "submitted": job[0]['tasks_submitted'],
                "aborted": job[0]['tasks_aborted']
            },
            "sensor_data": job[0]['sensor_data'].split(', ') if job[0]['sensor_data'] else []
        }

        logger.info(f"Retrieved job {job_id} with {job_data['task_summary']['total']} tasks")
        return jsonify(job_data), 200

    except Exception as e:
        logger.error(f"Error retrieving job details: {e}")
        logger.error(traceback.format_exc())
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
