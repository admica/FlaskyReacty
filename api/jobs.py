"""
Job submission and management endpoints
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

from core import logger, db, config, rate_limit
from api.auth import activity_tracking
from api.location_manager import location_manager

jobs_bp = Blueprint('jobs', __name__)

def validate_job_params(data: dict) -> tuple[Optional[dict], Optional[List[str]]]:
    """Validate job parameters and return processed job dict or error list"""
    try:
        # Required fields
        location = data.get('location')
        if not location: return None, ['missing:location']

        params = data.get('params', {})
        if not params: return None, ['missing:params']

        # Build job dictionary
        job = {
            'location': location,
            'submitted_by': get_jwt().get('sub', 'unknown'),
            'src_ip': params.get('src_ip'),
            'dst_ip': params.get('dst_ip'),
            'event_time': params.get('event_time'),
            'start_time': params.get('start_time'),
            'end_time': params.get('end_time'),
            'description': params.get('description'),
            'tz': params.get('tz', '+00:00')
        }

        # Validate required combinations
        errors = []

        if not (job['src_ip'] or job['dst_ip']):
            errors.append('must include src_ip, dst_ip, or both')

        # Handle event time calculations
        if job['event_time']:
            event_time = datetime.fromisoformat(job['event_time'].replace('Z', '+00:00'))

            if not job['start_time']:
                offset = config.getint('EVENT', 'start_before', fallback=1)
                job['start_time'] = (event_time - timedelta(minutes=offset)).isoformat()

            if not job['end_time']:
                offset = config.getint('EVENT', 'end_after', fallback=4)
                job['end_time'] = (event_time + timedelta(minutes=offset)).isoformat()

        # Final time validation
        if not job['start_time']:
            errors.append('missing:start_time')
        if not job['end_time']:
            errors.append('missing:end_time')

        if errors:
            return None, errors

        # Set default description if none provided
        if not job['description']:
            job['description'] = f"src:{job['src_ip']}->dst:{job['dst_ip']}"

        return job, None

    except Exception as e:
        logger.error(f"Error validating job params: {e}")
        return None, ['Invalid job parameters']

@jobs_bp.route('/api/v1/jobs/submit', methods=['POST'])
@jwt_required()
@activity_tracking()
def submit_job():
    """Submit a new PCAP search job for a location.

    Expected JSON body:
    {
        "location": "KSC",                        # Required
        "params": {                               # Required
            "start_time": "2024-03-20T00:10:00Z", # Required if no event_time
            "end_time": "2024-03-20T00:15:00Z",   # Required if no event_time
            "event_time": "2024-03-20T00:11:00Z", # Optional
            "src_ip": "192.168.1.1",              # Optional if dst_ip included
            "dst_ip": "10.0.0.1",                 # Optional if src_ip included
            "description": "Test search",          # Optional
            "tz": "+00:00"                        # Optional, default UTC
        }
    }
    """
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "No JSON data provided"}), 400

        # Validate and process parameters
        job, errors = validate_job_params(data)
        if errors: return jsonify({"errors": errors}), 400

        location = job['location']
        
        # Get or create job queue for location
        queue, error = location_manager.get_location_queue(location)

        if not queue:
            return jsonify({"error": error}), 400

        # Queue the job
        queue.put(job)

        return jsonify({
            "message": "Job submitted successfully",
            "location": location,
            "params": job
        }), 201

    except Exception as e:
        logger.error(f"Error submitting job: {e}")
        return jsonify({"error": str(e)}), 500

@jobs_bp.route('/api/v1/jobs/<int:job_id>/status', methods=['GET'])
@jwt_required()
@rate_limit()
def get_job_status(job_id):
    """Get status of a specific job"""
    try:
        # Get job details
        job = db("""
            SELECT j.id, j.location, j.submitted_by, j.src_ip, j.dst_ip,
                   j.event_time, j.start_time, j.end_time, j.description,
                   j.status, j.result_message,
                   array_agg(t.status) as task_statuses
            FROM jobs j
            LEFT JOIN tasks t ON t.job_id = j.id
            WHERE j.id = %s
            GROUP BY j.id
        """, (job_id,))

        if not job:
            return jsonify({"error": "Job not found"}), 404

        job = job[0]

        # Format response
        response = {
            'id': job[0],
            'location': job[1],
            'submitted_by': job[2],
            'src_ip': job[3],
            'dst_ip': job[4],
            'event_time': job[5].isoformat() if job[5] else None,
            'start_time': job[6].isoformat() if job[6] else None,
            'end_time': job[7].isoformat() if job[7] else None,
            'description': job[8],
            'status': job[9],
            'result_message': job[10],
            'task_statuses': job[11] if job[11] and job[11][0] is not None else []
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        return jsonify({"error": str(e)}), 500

@jobs_bp.route('/api/v1/jobs/<string:location>', methods=['GET'])
@jwt_required()
@rate_limit()
def get_jobs_by_location(location):
    """Get all jobs for a specific location"""
    try:
        # Get jobs for location
        jobs = db("""
            SELECT j.id, j.location, j.submitted_by, j.src_ip, j.dst_ip,
                   j.event_time, j.start_time, j.end_time, j.description,
                   j.status, j.result_message,
                   array_agg(t.status) as task_statuses
            FROM jobs j
            LEFT JOIN tasks t ON t.job_id = j.id
            WHERE j.location = %s
            GROUP BY j.id
            ORDER BY j.id DESC
        """, (location,))

        # Format response
        response = []
        for job in jobs:
            response.append({
                'id': job[0],
                'location': job[1],
                'submitted_by': job[2],
                'src_ip': job[3],
                'dst_ip': job[4],
                'event_time': job[5].isoformat() if job[5] else None,
                'start_time': job[6].isoformat() if job[6] else None,
                'end_time': job[7].isoformat() if job[7] else None,
                'description': job[8],
                'status': job[9],
                'result_message': job[10],
                'task_statuses': job[11] if job[11] and job[11][0] is not None else []
            })

        return jsonify({'jobs': response}), 200

    except Exception as e:
        logger.error(f"Error getting jobs for location {location}: {e}")
        return jsonify({"error": str(e)}), 500

@jobs_bp.route('/api/v1/jobs', methods=['GET'])
@jwt_required()
@rate_limit()
def get_all_jobs():
    """Get all jobs with their associated tasks"""
    try:
        # Get all jobs with tasks
        jobs = db("""
            SELECT 
                j.id, j.location, j.submitted_by, j.src_ip, j.dst_ip,
                j.event_time, j.start_time, j.end_time, j.description,
                j.status, j.result_message, j.result_size, j.result_path,
                j.created_at, j.started_at, j.completed_at,
                json_agg(json_build_object(
                    'id', t.id,
                    'job_id', t.job_id,
                    'task_id', t.task_id,
                    'sensor', t.sensor,
                    'status', t.status,
                    'pcap_size', t.pcap_size,
                    'temp_path', t.temp_path,
                    'result_message', t.result_message,
                    'start_time', t.start_time,
                    'end_time', t.end_time,
                    'created_at', t.created_at,
                    'started_at', t.started_at,
                    'completed_at', t.completed_at
                )) as tasks
            FROM jobs j
            LEFT JOIN tasks t ON t.job_id = j.id
            GROUP BY j.id
            ORDER BY j.id DESC
        """)

        # Format response
        response = []
        for job in jobs:
            response.append({
                'id': job[0],
                'location': job[1],
                'submitted_by': job[2],
                'src_ip': str(job[3]) if job[3] else None,
                'dst_ip': str(job[4]) if job[4] else None,
                'event_time': job[5].isoformat() if job[5] else None,
                'start_time': job[6].isoformat() if job[6] else None,
                'end_time': job[7].isoformat() if job[7] else None,
                'description': job[8],
                'status': job[9],
                'result_message': job[10],
                'result_size': job[11],
                'result_path': job[12],
                'created_at': job[13].isoformat() if job[13] else None,
                'started_at': job[14].isoformat() if job[14] else None,
                'completed_at': job[15].isoformat() if job[15] else None,
                'tasks': job[16] if job[16] and job[16][0] is not None else []
            })

        return jsonify({'jobs': response}), 200

    except Exception as e:
        logger.error(f"Error getting all jobs: {e}")
        return jsonify({"error": str(e)}), 500
