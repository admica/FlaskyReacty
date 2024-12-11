"""
Download and analysis endpoints for the PCAP Server API
"""
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import os
import json
from typing import Dict, Any, Optional
import traceback
from core import (
    logger, db, rate_limit, generate_signed_url
)
from .job_utils import (
    check_job_permissions, PCAP_PATH, IMG_PATH
)

# Blueprint Registration
downloads_bp = Blueprint('downloads', __name__)

@downloads_bp.route('/api/v1/jobs/<int:job_id>/analysis', methods=['GET'])
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

@downloads_bp.route('/api/v1/jobs/<int:job_id>/download', methods=['GET'])
@jwt_required()
@rate_limit()
def download_pcap(job_id: int):
    """Generate download URL for PCAP file"""
    try:
        username = get_jwt_identity()
        
        # Check permissions
        has_permission, error_msg, status_code = check_job_permissions(job_id, username)
        if not has_permission:
            return jsonify({"error": error_msg}), status_code

        # Get job details
        job = db("""
            SELECT filename, status
            FROM jobs
            WHERE id = %s
        """, (job_id,))

        if not job or not job[0][0]:
            return jsonify({"error": "No PCAP file available for download"}), 404

        filename, status = job[0]

        # Check if job is completed
        if status != 'Complete':
            return jsonify({"error": f"Cannot download PCAP for job in {status} state"}), 400

        # Generate signed URL for download
        pcap_path = os.path.join(PCAP_PATH, filename)
        if not os.path.exists(pcap_path):
            logger.error(f"PCAP file missing for job {job_id}: {pcap_path}")
            return jsonify({"error": "PCAP file not found"}), 404

        download_url = generate_signed_url(
            pcap_path,
            'application/vnd.tcpdump.pcap',
            filename=filename
        )

        return jsonify({
            "url": download_url,
            "filename": filename
        }), 200

    except Exception as e:
        logger.error(f"Error generating download URL: {e}")
        return jsonify({"error": "Failed to generate download URL"}), 500
