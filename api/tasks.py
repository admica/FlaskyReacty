"""
Task management endpoints for the PCAP Server API
"""
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from core import logger, db, db_pool, rate_limit
from api.auth import get_user_role
from api.sensor_threads import (
    sensor_queues, sensor_threads, sensor_thread, Thread
)
import os
from queue import Queue
from threading import Thread

# Blueprint Registration
tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('/api/v1/tasks/<int:task_id>', methods=['GET'])
@jwt_required()
@rate_limit()
def get_task(task_id):
    """Get detailed task information"""
    try:
        username = get_jwt_identity()
        logger.debug(f"Getting task {task_id} details for user {username}")

        # Get task with job and sensor details
        task = db("""
            SELECT
                t.*,
                j.submitted_by,
                j.status as job_status,
                j.location,
                j.source_ip,
                j.dest_ip,
                j.start_time as job_start,
                j.end_time as job_end,
                s.fqdn,
                s.status as sensor_status,
                (
                    SELECT json_build_object(
                        'total', COUNT(*),
                        'complete', COUNT(*) FILTER (WHERE status = 'Complete'),
                        'failed', COUNT(*) FILTER (WHERE status = 'Failed'),
                        'skipped', COUNT(*) FILTER (WHERE status = 'Skipped'),
                        'running', COUNT(*) FILTER (WHERE status = 'Running'),
                        'downloading', COUNT(*) FILTER (WHERE status = 'Downloading'),
                        'submitted', COUNT(*) FILTER (WHERE status = 'Submitted'),
                        'aborted', COUNT(*) FILTER (WHERE status = 'Aborted')
                    )
                    FROM tasks
                    WHERE job_id = t.job_id
                ) as job_task_summary,
                CASE
                    WHEN t.status = 'Complete' THEN
                        CASE
                            WHEN t.pcap_size IS NOT NULL THEN 'Complete with data'
                            ELSE 'Complete with no data'
                        END
                    WHEN t.status = 'Failed' THEN
                        COALESCE(t.result_message, 'Task failed')
                    WHEN t.status = 'Running' THEN
                        'Task running on sensor'
                    WHEN t.status = 'Downloading' THEN
                        CASE
                            WHEN t.temp_path IS NOT NULL THEN 'Downloading to ' || t.temp_path
                            ELSE 'Download starting'
                        END
                    WHEN t.status = 'Submitted' THEN
                        'Waiting for sensor thread'
                    WHEN t.status = 'Skipped' THEN
                        COALESCE(t.result_message, 'Task skipped')
                    WHEN t.status = 'Aborted' THEN
                        COALESCE(t.result_message, 'Task aborted')
                END as status_detail,
                CASE WHEN t.status IN ('Complete', 'Failed', 'Skipped', 'Aborted')
                     THEN true ELSE false
                END as is_finished,
                CASE WHEN t.status IN ('Submitted', 'Running', 'Downloading')
                     THEN true ELSE false
                END as can_be_skipped,
                CASE WHEN t.status IN ('Failed', 'Aborted') AND j.status != 'Aborted'
                     THEN true ELSE false
                END as can_be_retried
            FROM tasks t
            JOIN jobs j ON t.job_id = j.id
            JOIN sensors s ON t.sensor = s.name
            WHERE t.id = %s
        """, (task_id,))

        if not task:
            logger.warning(f"Task {task_id} not found")
            return jsonify({"error": "Task not found"}), 404

        # Check permissions
        if task[0]['submitted_by'] != username and get_user_role(username) != 'admin':
            logger.warning(f"User {username} denied access to task {task_id}")
            return jsonify({"error": "Permission denied"}), 403

        logger.info(f"Retrieved task {task_id} in state {task[0]['status']} "
                   f"for job {task[0]['job_id']} ({task[0]['job_status']})")

        return jsonify({
            "task": task[0],
            "state_info": {
                "current_state": task[0]['status'],
                "status_detail": task[0]['status_detail'],
                "is_finished": task[0]['is_finished'],
                "can_be_skipped": task[0]['can_be_skipped'],
                "can_be_retried": task[0]['can_be_retried'],
                "retry_count": task[0]['retry_count']
            }
        }), 200

    except Exception as e:
        logger.error(f"Error retrieving task: {e}")
        return jsonify({"error": "Failed to retrieve task"}), 500

@tasks_bp.route('/api/v1/tasks/<int:task_id>/retry', methods=['POST'])
@jwt_required()
@rate_limit()
def retry_task(task_id):
    """Retry a failed or aborted task"""
    try:
        username = get_jwt_identity()
        logger.info(f"User {username} requesting retry of task {task_id}")

        # Get task details
        task = db("""
            SELECT t.*, j.submitted_by, j.status as job_status,
                   j.start_time, j.end_time, j.source_ip, j.dest_ip,
                   s.status as sensor_status
            FROM tasks t
            JOIN jobs j ON t.job_id = j.id
            JOIN sensors s ON t.sensor = s.name
            WHERE t.id = %s
        """, (task_id,))

        if not task:
            logger.warning(f"Task {task_id} not found")
            return jsonify({"error": "Task not found"}), 404

        # Check permissions
        if task[0]['submitted_by'] != username and get_user_role(username) != 'admin':
            logger.warning(f"User {username} denied retry permission for task {task_id}")
            return jsonify({"error": "Permission denied"}), 403

        # Validate task can be retried
        if task[0]['status'] not in ['Failed', 'Aborted']:
            logger.warning(f"Cannot retry task {task_id} in {task[0]['status']} state")
            return jsonify({"error": f"Cannot retry task in {task[0]['status']} state"}), 400

        if task[0]['job_status'] == 'Aborted':
            logger.warning(f"Cannot retry task {task_id} - job is aborted")
            return jsonify({"error": "Cannot retry task - job is aborted"}), 400

        if task[0]['job_status'] not in ['Running', 'Failed', 'Partial Complete']:
            logger.warning(f"Cannot retry task {task_id} - job is in {task[0]['job_status']} state")
            return jsonify({"error": f"Cannot retry task - job is in {task[0]['job_status']} state"}), 400

        if task[0]['sensor_status'] == 'Offline':
            logger.warning(f"Cannot retry task {task_id} - sensor is offline")
            return jsonify({"error": "Cannot retry task when sensor is offline"}), 400

        # Update task in transaction
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                # Get current task state for cleanup
                cur.execute("""
                    SELECT temp_path
                    FROM tasks
                    WHERE id = %s
                """, (task_id,))
                current = cur.fetchone()

                # Clean up any existing temp file
                if current and current[0]:
                    try:
                        os.remove(current[0])
                        logger.info(f"Cleaned up temp file {current[0]} before retry")
                    except Exception as e:
                        logger.warning(f"Failed to clean up temp file {current[0]}: {e}")

                # Reset task status and clear results
                cur.execute("""
                    UPDATE tasks
                    SET status = 'Submitted',
                        retry_count = retry_count + 1,
                        modified_by = %s,
                        start_time = NULL,
                        end_time = NULL,
                        pcap_size = NULL,
                        temp_path = NULL,
                        result_message = NULL
                    WHERE id = %s
                    RETURNING job_id, sensor
                """, (username, task_id))

                job_id, sensor = cur.fetchone()

                # Update job status if needed
                cur.execute("""
                    UPDATE jobs
                    SET status = 'Running',
                        last_modified = CURRENT_TIMESTAMP
                    WHERE id = %s
                    AND status IN ('Failed', 'Partial Complete')
                """, (job_id,))

                conn.commit()

                # Check/create sensor thread if needed
                if sensor not in sensor_queues:
                    logger.info(f"Creating new sensor queue for {sensor}")
                    sensor_queues[sensor] = Queue()

                if sensor not in sensor_threads or not sensor_threads[sensor].is_alive():
                    logger.info(f"Starting new sensor thread for {sensor}")
                    sensor_threads[sensor] = Thread(
                        target=sensor_thread,
                        args=(sensor,),
                        daemon=True
                    )
                    sensor_threads[sensor].start()

                # Requeue task
                # Convert times to epochs
                start_epoch = int(task[0]['start_time'].timestamp())
                end_epoch = int(task[0]['end_time'].timestamp())

                # Queue format: "<job_id>_<task_id>"
                task_identifier = f"{job_id}_{task_id}"
                sensor_queues[sensor].put([
                    task_identifier,
                    start_epoch,
                    end_epoch,
                    'pcap',  # Default request type
                    str(task[0]['source_ip']) if task[0]['source_ip'] else '',
                    str(task[0]['dest_ip']) if task[0]['dest_ip'] else ''
                ])
                logger.info(f"Requeued task {task_id} for sensor {sensor}")

                return jsonify({
                    "message": "Task retry initiated",
                    "task_id": task_id,
                    "job_id": job_id,
                    "retry_count": task[0]['retry_count'] + 1,
                    "sensor_thread": "created" if sensor not in sensor_threads else "existing"
                }), 200

        except Exception as e:
            conn.rollback()
            logger.error(f"Database error during task retry: {e}")
            return jsonify({"error": "Failed to retry task"}), 500
        finally:
            db_pool.putconn(conn)

    except Exception as e:
        logger.error(f"Error retrying task: {e}")
        return jsonify({"error": "Failed to retry task"}), 500

@tasks_bp.route('/api/v1/tasks/<int:task_id>/skip', methods=['POST'])
@jwt_required()
@rate_limit()
def skip_task(task_id):
    """Mark a task as skipped"""
    try:
        username = get_jwt_identity()
        logger.info(f"User {username} requesting to skip task {task_id}")

        # Get task details
        task = db("""
            SELECT t.*, j.submitted_by, j.status as job_status
            FROM tasks t
            JOIN jobs j ON t.job_id = j.id
            WHERE t.id = %s
        """, (task_id,))

        if not task:
            logger.warning(f"Task {task_id} not found")
            return jsonify({"error": "Task not found"}), 404

        # Check permissions
        if task[0]['submitted_by'] != username and get_user_role(username) != 'admin':
            logger.warning(f"User {username} denied skip permission for task {task_id}")
            return jsonify({"error": "Permission denied"}), 403

        # Validate task can be skipped
        if task[0]['status'] not in ['Submitted', 'Running', 'Downloading']:
            logger.warning(f"Cannot skip task {task_id} in {task[0]['status']} state")
            return jsonify({"error": f"Cannot skip task in {task[0]['status']} state"}), 400

        if task[0]['job_status'] == 'Aborted':
            logger.warning(f"Cannot skip task {task_id} - job is aborted")
            return jsonify({"error": "Cannot skip task - job is aborted"}), 400

        # Update task and check job status
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                # Update task
                cur.execute("""
                    UPDATE tasks
                    SET status = 'Skipped',
                        modified_by = %s,
                        end_time = CURRENT_TIMESTAMP,
                        result_message = CASE
                            WHEN status = 'Downloading'
                            THEN 'Task skipped during download'
                            ELSE 'Task skipped by user'
                        END,
                        temp_path = NULL
                    WHERE id = %s
                    RETURNING job_id, status, temp_path
                """, (username, task_id))

                job_id, old_status, temp_path = cur.fetchone()

                # Clean up temp file if task was downloading
                if old_status == 'Downloading' and temp_path:
                    try:
                        os.remove(temp_path)
                        logger.info(f"Cleaned up temp file {temp_path} for skipped task {task_id}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up temp file {temp_path}: {e}")

                # Check if all tasks are finished
                cur.execute("""
                    SELECT
                        bool_and(status IN ('Complete', 'Failed', 'Skipped', 'Aborted')) as all_finished,
                        bool_or(status = 'Complete') as has_completed,
                        bool_or(status IN ('Failed', 'Skipped')) as has_failed_or_skipped,
                        COUNT(*) as total_tasks,
                        COUNT(CASE WHEN status IN ('Failed', 'Skipped') THEN 1 END) as failed_skipped_count,
                        bool_and(status IN ('Failed', 'Skipped')) as all_failed_or_skipped
                    FROM tasks
                    WHERE job_id = %s
                """, (job_id,))

                result = cur.fetchone()
                all_finished = result[0]
                has_completed = result[1]
                has_failed_or_skipped = result[2]
                total_tasks = result[3]
                failed_skipped_count = result[4]
                all_failed_or_skipped = result[5]

                logger.info(f"Job {job_id} status check: all_finished={all_finished}, "
                          f"has_completed={has_completed}, has_failed_or_skipped={has_failed_or_skipped}, "
                          f"total={total_tasks}, failed_skipped={failed_skipped_count}, "
                          f"all_failed_or_skipped={all_failed_or_skipped}")

                # Update job status if all tasks are finished
                if all_finished:
                    if all_failed_or_skipped:
                        new_status = 'Failed'  # All tasks failed or skipped
                    elif has_failed_or_skipped:
                        new_status = 'Partial Complete'  # Mix of complete and failed/skipped
                    else:
                        new_status = 'Complete'  # All tasks completed

                    cur.execute("""
                        UPDATE jobs
                        SET status = %s,
                            last_modified = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (new_status, job_id))

                    logger.info(f"Updated job {job_id} status to {new_status}")

                conn.commit()
                return jsonify({
                    "message": "Task skipped successfully",
                    "task_id": task_id,
                    "job_id": job_id,
                    "job_status": new_status if all_finished else task[0]['job_status']
                }), 200

        except Exception as e:
            conn.rollback()
            logger.error(f"Database error during task skip: {e}")
            return jsonify({"error": "Failed to skip task"}), 500
        finally:
            db_pool.putconn(conn)

    except Exception as e:
        logger.error(f"Error skipping task: {e}")
        return jsonify({"error": "Failed to skip task"}), 500

@tasks_bp.route('/api/v1/tasks/location/<location>', methods=['GET'])
@jwt_required()
@rate_limit()
def get_location_tasks(location):
    """Get all active tasks for a location"""
    try:
        username = get_jwt_identity()
        logger.debug(f"Getting active tasks for location {location}")

        # Verify location exists and user has access
        loc = db("""
            SELECT l.site, j.submitted_by
            FROM locations l
            LEFT JOIN jobs j ON l.site = j.location AND j.submitted_by = %s
            WHERE l.site = %s
        """, (username, location))

        if not loc:
            logger.warning(f"Location not found: {location}")
            return jsonify({"error": "Location not found"}), 404

        # Check if user has access to this location
        if not any(row[1] == username for row in loc) and get_user_role(username) != 'admin':
            logger.warning(f"User {username} denied access to location {location}")
            return jsonify({"error": "Permission denied"}), 403

        # Get active tasks for location
        tasks = db("""
            SELECT
                t.*,
                j.submitted_by,
                j.source_ip,
                j.dest_ip,
                j.start_time as job_start,
                j.end_time as job_end,
                s.fqdn,
                s.status as sensor_status
            FROM tasks t
            JOIN jobs j ON t.job_id = j.id
            JOIN sensors s ON t.sensor = s.name
            WHERE j.location = %s
            AND t.status IN ('Submitted', 'Running', 'Downloading')
            ORDER BY t.created_at ASC
        """, (location,))

        # Filter by permissions for non-admin users
        if get_user_role(username) != 'admin':
            tasks = [t for t in tasks if t['submitted_by'] == username]

        # Group tasks by status
        task_summary = {
            'total': len(tasks),
            'by_status': {
                'Submitted': len([t for t in tasks if t['status'] == 'Submitted']),
                'Running': len([t for t in tasks if t['status'] == 'Running']),
                'Downloading': len([t for t in tasks if t['status'] == 'Downloading'])
            },
            'by_sensor': {}
        }

        # Count tasks per sensor
        for task in tasks:
            sensor = task['sensor']
            if sensor not in task_summary['by_sensor']:
                task_summary['by_sensor'][sensor] = {
                    'total': 0,
                    'status': task['sensor_status']
                }
            task_summary['by_sensor'][sensor]['total'] += 1

        logger.info(f"Found {len(tasks)} active tasks for location {location}")
        return jsonify({
            "location": location,
            "tasks": tasks,
            "summary": task_summary
        }), 200

    except Exception as e:
        logger.error(f"Error retrieving location tasks: {e}")
        return jsonify({"error": "Failed to retrieve location tasks"}), 500