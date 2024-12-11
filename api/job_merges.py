"""
Job merge and location mapping endpoints for the PCAP Server API
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from typing import List, Dict, Any

from core import (
    logger, db, rate_limit
)
from api.auth import get_user_role
import os
from core import generate_signed_url
from .job_utils import PCAP_PATH

# Blueprint Registration
merges_bp = Blueprint('merges', __name__)

@merges_bp.route('/api/v1/subnet-location-counts', methods=['GET'])
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

@merges_bp.route('/api/v1/jobs/merge', methods=['POST'])
@jwt_required()
@rate_limit()
def merge_jobs():
    """Merge multiple completed jobs into a single PCAP file"""
    try:
        username = get_jwt_identity()
        data = request.get_json()

        if not data or 'job_ids' not in data:
            return jsonify({"error": "No job IDs provided"}), 400

        job_ids = data.get('job_ids', [])
        if not isinstance(job_ids, list) or not job_ids:
            return jsonify({"error": "Invalid job IDs format"}), 400

        # Verify jobs exist and user has permission
        jobs = db("""
            SELECT id, username, status, filename
            FROM jobs
            WHERE id = ANY(%s)
        """, (job_ids,))

        if not jobs:
            return jsonify({"error": "No valid jobs found"}), 404

        # Check permissions and job states
        user_role = get_user_role(username)
        incomplete_jobs = []
        unauthorized_jobs = []

        for job in jobs:
            if job[1] != username and user_role != 'admin':
                unauthorized_jobs.append(job[0])
            if job[2] != 'Complete':
                incomplete_jobs.append(job[0])

        if unauthorized_jobs:
            return jsonify({
                "error": "Permission denied",
                "unauthorized_jobs": unauthorized_jobs
            }), 403

        if incomplete_jobs:
            return jsonify({
                "error": "All jobs must be complete to merge",
                "incomplete_jobs": incomplete_jobs
            }), 400

        # Create merge job
        merge_job_id = db("""
            INSERT INTO merge_jobs
            (job_ids, status, requested_by)
            VALUES (%s, 'Pending', %s)
            RETURNING id
        """, (job_ids, username))

        if not merge_job_id:
            return jsonify({"error": "Failed to create merge job"}), 500

        # Queue merge job for processing
        # Note: Implementation depends on your merge processing system
        
        return jsonify({
            "message": "Merge job created successfully",
            "merge_job_id": merge_job_id[0]
        }), 201

    except Exception as e:
        logger.error(f"Error creating merge job: {e}")
        return jsonify({"error": "Failed to create merge job"}), 500

@merges_bp.route('/api/v1/jobs/merge/<int:merge_job_id>', methods=['GET'])
@jwt_required()
@rate_limit()
def get_merge_status(merge_job_id: int):
    """Get status of a merge job"""
    try:
        username = get_jwt_identity()
        
        # Get merge job details
        merge_job = db("""
            SELECT status, requested_by, result_file, error_message
            FROM merge_jobs
            WHERE id = %s
        """, (merge_job_id,))

        if not merge_job:
            return jsonify({"error": "Merge job not found"}), 404

        # Check permissions
        if merge_job[0][1] != username:
            user_role = get_user_role(username)
            if user_role != 'admin':
                return jsonify({"error": "Permission denied"}), 403

        status, requested_by, result_file, error_message = merge_job[0]

        response = {
            "status": status,
            "requested_by": requested_by
        }

        if status == 'Complete' and result_file:
            response["download_url"] = generate_signed_url(
                os.path.join(PCAP_PATH, result_file),
                'application/vnd.tcpdump.pcap',
                filename=result_file
            )
        elif status == 'Failed' and error_message:
            response["error_message"] = error_message

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error fetching merge job status: {e}")
        return jsonify({"error": "Failed to fetch merge job status"}), 500
