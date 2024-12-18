"""
Job submission and management endpoints
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

from core import logger, db, config
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
