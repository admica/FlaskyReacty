"""
Job management endpoints and functionality for the PCAP Server API
"""
from flask import Blueprint, jsonify, request, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
import os
import configparser
from datetime import datetime, timezone, timedelta
import json
from queue import Queue

from core import (
    logger, db, rate_limit, STATUS, RESULTS,
    parse_and_convert_to_utc, generate_signed_url, config
)
from api.auth import activity_tracking, get_user_role
from api.sensor_threads import (
    sensor_queues, sensor_threads, Thread, sensor_thread,
    EVENT_START_BEFORE, EVENT_END_AFTER
)
from cache_utils import redis_client

jobs_bp = Blueprint('jobs', __name__)

# Get paths from config
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

def process_job_submission(username, sensor, src_ip, dst_ip, start_time, end_time, description, event_time=None, tz='+00:00'):
    """Process a new job submission"""
    logger.debug(f"Starting process_job_submission with args: username={username}, sensor={sensor}, src_ip={src_ip}, dst_ip={dst_ip}, start_time={start_time}, end_time={end_time}, description={description}, event_time={event_time}, tz={tz}")
    try:
        # Convert times to UTC for validation and epoch conversion
        utc_start_time = parse_and_convert_to_utc(start_time, tz)
        utc_end_time = parse_and_convert_to_utc(end_time, tz)
        utc_event_time = parse_and_convert_to_utc(event_time, tz) if event_time else None
        logger.debug(f"Converted times: start={utc_start_time}, end={utc_end_time}, event={utc_event_time}")

        # Handle event time logic
        if utc_event_time:
            if not utc_start_time: utc_start_time = utc_event_time - timedelta(minutes=EVENT_START_BEFORE)
            if not utc_end_time: utc_end_time = utc_event_time + timedelta(minutes=EVENT_END_AFTER)

        if not utc_start_time: raise ValueError("Invalid start time format")
        if not utc_end_time: raise ValueError("Invalid end time format")

        # Insert job into database
        job_data = {
            'username': username,
            'description': description,
            'sensor': sensor,
            'src_ip': src_ip,
            'dst_ip': dst_ip,
            'event_time': utc_event_time,
            'start_time': utc_start_time,
            'end_time': utc_end_time,
            'status': STATUS['Submitted'],
            'tz': tz
        }
        logger.debug(f"Created job_data dictionary: {job_data}")

        result = {
            'values': tuple(job_data.values()),
            'error': None
        }
        logger.debug(f"Returning from process_job_submission: type={type(result)}, value={result}")
        return result

    except Exception as e:
        logger.error(f"Job submission processing error: {e}")
        return {
            'values': None,
            'error': f"Failed to submit job: {e}"
        }

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
        conditions = ["1=1"] # Always true condition to start
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

        jobs = [{
            'id': row[0],
            'username': row[1],
            'description': row[2],
            'sensor': row[3],
            'src_ip': row[4],
            'dst_ip': row[5],
            'event_time': row[6].isoformat() if row[6] else None,
            'start_time': row[7].isoformat() if row[7] else None,
            'end_time': row[8].isoformat() if row[8] else None,
            'status': row[9],
            'started': row[10].isoformat() if row[10] else None,
            'completed': row[11].isoformat() if row[11] else None,
            'result': row[12],
            'filename': row[13],
            'analysis': row[14],
            'tz': row[15]
        } for row in rows]

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

        if not job:
            return jsonify({"error": "Job not found"}), 404

        job_data = {
            'id': job[0][0],
            'username': job[0][1],
            'description': job[0][2],
            'sensor': job[0][3],
            'event_time': job[0][4].isoformat() if job[0][4] else None,
            'start_time': job[0][5].isoformat() if job[0][5] else None,
            'end_time': job[0][6].isoformat() if job[0][6] else None,
            'status': job[0][7],
            'started': job[0][8].isoformat() if job[0][8] else None,
            'completed': job[0][9].isoformat() if job[0][9] else None,
            'result': job[0][10],
            'filename': job[0][11],
            'analysis': job[0][12],
            'tz': job[0][13]
        }

        return jsonify(job_data), 200

    except Exception as e:
        logger.error(f"Error retrieving job details: {e}")
        return jsonify({"error": "Failed to retrieve job details"}), 500

@jobs_bp.route('/api/v2/tasks/<int:task_id>/retry', methods=['POST'])
@jwt_required()
@rate_limit()
def retry_task(task_id):
    """Retry a failed or aborted task"""
    try:
        username = get_jwt_identity()

        # Get task and job details in transaction
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT t.sensor, t.status, t.retry_count,
                           j.id as job_id, j.submitted_by,
                           j.start_time, j.end_time,
                           j.source_ip, j.dest_ip, j.status as job_status
                    FROM tasks t
                    JOIN jobs j ON t.job_id = j.id
                    WHERE t.id = %s
                    FOR UPDATE
                """, (task_id,))
                task = cur.fetchone()

                if not task:
                    return jsonify({"error": "Task not found"}), 404

                # Check permissions
                if task[4] != username:  # submitted_by
                    user_role = get_user_role(username)
                    if user_role != 'admin':
                        return jsonify({"error": "Permission denied"}), 403

                # Check if task can be retried
                if task[1] not in ['Failed', 'Aborted']:
                    return jsonify({
                        "error": f"Cannot retry task in {task[1]} state"
                    }), 400

                # Check if job is in final state
                if task[9] not in ['Running', 'Submitted']:
                    return jsonify({
                        "error": f"Cannot retry task - job is in {task[9]} state"
                    }), 400

                sensor_name = task[0]
                job_id = task[3]
                start_time = task[5]
                end_time = task[6]
                src_ip = task[7] or ''
                dst_ip = task[8] or ''

                # Update task status
                cur.execute("""
                    UPDATE tasks
                    SET status = 'Submitted',
                        retry_count = retry_count + 1,
                        modified_by = %s,
                        last_modified = NOW(),
                        start_time = NULL,
                        end_time = NULL,
                        pcap_size = NULL,
                        temp_path = NULL,
                        result_message = NULL
                    WHERE id = %s
                """, (username, task_id))

                # Check if sensor thread is running
                if sensor_name not in sensor_queues:
                    sensor_queues[sensor_name] = Queue()
                    sensor_threads[sensor_name] = Thread(
                        target=sensor_thread,
                        args=(sensor_name,)
                    )
                    sensor_threads[sensor_name].start()
                    logger.info(f"Started new sensor thread for {sensor_name}")

                # Queue task
                sensor_queues[sensor_name].put((
                    task_id,
                    int(start_time.timestamp()),
                    int(end_time.timestamp()),
                    'pcap',
                    src_ip,
                    dst_ip
                ))

                conn.commit()
                logger.info(f"Task {task_id} requeued for sensor {sensor_name}")

                return jsonify({
                    "message": "Task retry initiated",
                    "task_id": task_id,
                    "job_id": job_id,
                    "sensor": sensor_name
                }), 200

        except Exception as e:
            conn.rollback()
            raise
        finally:
            db_pool.putconn(conn)

    except Exception as e:
        logger.error(f"Error retrying task: {e}")
        return jsonify({"error": "Failed to retry task"}), 500

@jobs_bp.route('/api/v2/tasks/<int:task_id>/skip', methods=['POST'])
@jwt_required()
@rate_limit()
def skip_task(task_id):
    """Skip a task that hasn't completed yet"""
    try:
        username = get_jwt_identity()

        # Get task details in transaction
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT t.status, j.submitted_by, j.status as job_status
                    FROM tasks t
                    JOIN jobs j ON t.job_id = j.id
                    WHERE t.id = %s
                    FOR UPDATE
                """, (task_id,))
                task = cur.fetchone()

                if not task:
                    return jsonify({"error": "Task not found"}), 404

                # Check permissions
                if task[1] != username:  # submitted_by
                    user_role = get_user_role(username)
                    if user_role != 'admin':
                        return jsonify({"error": "Permission denied"}), 403

                # Check if task can be skipped
                if task[0] not in ['Submitted', 'Running']:
                    return jsonify({
                        "error": f"Cannot skip task in {task[0]} state"
                    }), 400

                # Check if job is in a state that allows skipping
                if task[2] not in ['Running', 'Submitted']:
                    return jsonify({
                        "error": f"Cannot skip task - job is in {task[2]} state"
                    }), 400

                # Update task status
                cur.execute("""
                    UPDATE tasks
                    SET status = 'Skipped',
                        modified_by = %s,
                        last_modified = NOW(),
                        end_time = NOW(),
                        result_message = 'Task skipped by user'
                    WHERE id = %s
                """, (username, task_id))

                conn.commit()
                logger.info(f"Task {task_id} skipped by {username}")

                return jsonify({
                    "message": "Task skipped successfully",
                    "task_id": task_id
                }), 200

        except Exception as e:
            conn.rollback()
            raise
        finally:
            db_pool.putconn(conn)

    except Exception as e:
        logger.error(f"Error skipping task: {e}")
        return jsonify({"error": "Failed to skip task"}), 500

@jobs_bp.route('/api/v1/jobs/<int:job_id>/cancel', methods=['POST'])
@jwt_required()
@rate_limit()
def cancel_job(job_id):
    """Cancel a running job"""
    try:
        username = get_jwt_identity()

        # Get job info and verify permissions
        job = db("SELECT status, submitted_by FROM jobs WHERE id = %s", (job_id,))
        if not job: return jsonify({"error": "Job not found"}), 404

        # Check permissions
        if job[0][1] != username: # Users can delete only their own jobs unless they're admins
            user_role = get_user_role(username)
            if user_role != 'admin':
                return jsonify({"error": "Permission denied"}), 403

        # Check if job can be cancelled by checking current state
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
        user_role = get_user_role(current_user)

        # First get the job details
        job = db("""
            SELECT username, status, filename
            FROM jobs
            WHERE id = %s
        """, (job_id,))

        if not job:
            return jsonify({"error": "Job not found"}), 404

        username, status, filename = job[0]

        # Check permissions - allow if admin or job owner
        if user_role != 'admin' and username != current_user:
            return jsonify({"error": "Permission denied"}), 403

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

@jobs_bp.route('/api/v1/jobs/<int:job_id>/analysis', methods=['GET'])
@jwt_required()
@rate_limit()
def get_job_analysis(job_id):
    """Get analysis results for a job"""
    try:
        current_user = get_jwt_identity()

        # Check job existence and ownership
        job = db("""
            SELECT username, analysis, protocol_distribution,
                   conversation_matrix, bandwidth_usage,
                   packet_size_distribution
            FROM jobs
            WHERE id = %s AND username = %s
        """, (job_id, current_user))

        if not job:
            return jsonify({"error": "Job not found"}), 404

        username, analysis_status = job[0][0:2]
        analysis_data = job[0][2:]

        # Check analysis status
        if analysis_status != 'View':
            if analysis_status and analysis_status.isdigit():
                return jsonify({
                    "status": "in_progress",
                    "progress": int(analysis_status)
                }), 202
            else:
                return jsonify({
                    "status": "unavailable",
                    "message": "Analysis not available"
                }), 404

        # Generate signed URLs for images
        image_urls = {}
        for img_type in ['proto', 'matrix', 'usage', 'size']:
            img_path = os.path.join(IMG_PATH, f"{job_id}.{img_type}.png")
            if os.path.exists(img_path):
                image_urls[img_type] = generate_signed_url(
                    img_path,
                    'image/png'
                )

        # Format response
        response = {
            'protocol_distribution': {
                'data': json.loads(analysis_data[0]) if analysis_data[0] else None,
                'image_url': image_urls.get('proto')
            },
            'conversation_matrix': {
                'data': json.loads(analysis_data[1]) if analysis_data[1] else None,
                'image_url': image_urls.get('matrix')
            },
            'bandwidth_usage': {
                'data': json.loads(analysis_data[2]) if analysis_data[2] else None,
                'image_url': image_urls.get('usage')
            },
            'packet_size_distribution': {
                'data': json.loads(analysis_data[3]) if analysis_data[3] else None,
                'image_url': image_urls.get('size')
            }
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Analysis retrieval error: {e}")
        return jsonify({"error": "Failed to retrieve analysis"}), 500

@jobs_bp.route('/api/v1/subnet-location-counts', methods=['GET'])
@jwt_required()
@rate_limit()
def get_subnet_location_counts():
    """Get counts of subnet mappings between locations with optional filtering"""
    try:
        # Get location filters from query parameters
        src_location = request.args.get('src')
        dst_location = request.args.get('dst')

        # Build query conditions and parameters
        conditions = []
        params = []

        if src_location:
            conditions.append("LOWER(src_location) = LOWER(%s)")
            params.append(src_location)

        if dst_location:
            conditions.append("LOWER(dst_location) = LOWER(%s)")
            params.append(dst_location)

        # Build the query
        query = """
            SELECT src_location, dst_location, COUNT(*) as count
            FROM subnet_location_map
        """

        if conditions:
            query += f" WHERE {' AND '.join(conditions)}"

        query += """
            GROUP BY src_location, dst_location
            ORDER BY src_location, dst_location;
        """

        rows = db(query, params)
        if not rows:
            return jsonify([]), 200

        counts = [{
            'src_location': row[0],
            'dst_location': row[1],
            'count': row[2]
        } for row in rows]

        return jsonify(counts), 200

    except Exception as e:
        logger.error(f"Error fetching subnet location counts: {e}")
        return jsonify({"error": "Failed to fetch subnet location counts"}), 500
