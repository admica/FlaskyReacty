"""
Task management endpoints for the PCAP Server API
"""
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from typing import Optional, Tuple
from queue import Queue
from core import (
    logger, db, db_pool, rate_limit
)
from api.auth import get_user_role
from api.sensor_threads import (
    sensor_queues, sensor_threads, Thread, sensor_thread
)
from .job_utils import check_job_permissions

# Blueprint Registration
tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('/api/v2/tasks/<int:task_id>/retry', methods=['POST'])
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

@tasks_bp.route('/api/v2/tasks/<int:task_id>/skip', methods=['POST'])
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
