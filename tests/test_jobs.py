"""
Job endpoint testing
Tests the job submission and management endpoints
"""
from .base import BaseTest, TestResult
from datetime import datetime, timedelta

class JobTest(BaseTest):
    """Test suite for job endpoints"""
    
    def setup(self):
        """Setup required for job tests - login and get locations"""
        # First login to get access token
        result = self.request(
            "POST",
            "/api/v1/login",
            data={
                "username": self.auth_username,
                "password": self.auth_password
            },
            auth=False
        )
        
        if not result['success']:
            raise Exception("Failed to login for job tests")
            
        self.access_token = result['response']['access_token']
        
        # Get list of locations
        location_result = self.request(
            "GET",
            "/api/v1/network/locations",
            auth=True,
            auth_token=self.access_token
        )
        
        if not location_result['success']:
            raise Exception("Failed to get locations")
            
        locations = location_result['response'].get('locations', [])
        if not locations:
            raise Exception("No locations available for testing")
        
        # Store first location for testing
        self.test_location = locations[0]['site']
        
        self.add_result(TestResult(
            "Setup - Login and get location",
            True,
            {"location": self.test_location}
        ))

    def test_01_submit_job(self):
        """Test submitting a basic job"""
        # Calculate times relative to now
        now = datetime.utcnow()
        start_time = now - timedelta(minutes=20)
        end_time = now - timedelta(minutes=5)
        
        # Prepare job submission
        job_data = {
            "location": self.test_location,
            "params": {
                "description": "Test job submission",
                "src_ip": "192.168.99.10",
                "dst_ip": "192.168.99.20",
                "start_time": start_time.isoformat() + "Z",
                "end_time": end_time.isoformat() + "Z"
            }
        }
        
        # Submit job
        result = self.request(
            "POST",
            "/api/v1/jobs/submit",
            data=job_data,
            auth=True,
            auth_token=self.access_token
        )
        
        success = result['success']
        error = None
        
        if success:
            data = result['response']
            # Validate response structure
            if not isinstance(data, dict):
                success = False
                error = "Response is not a dictionary"
            elif not all(key in data for key in ['message', 'location', 'params']):
                success = False
                error = "Missing required fields in response"
            elif data['location'] != self.test_location:
                success = False
                error = f"Wrong location in response: {data['location']}"
        
        self.add_result(TestResult(
            "Submit basic job",
            success,
            result['response'],
            error or result.get('error')
        ))

    def teardown(self):
        """Cleanup after job tests"""
        if hasattr(self, 'access_token'):
            result = self.request(
                "POST",
                "/api/v1/logout",
                auth=True,
                auth_token=self.access_token
            )
            self.add_result(TestResult(
                "Teardown - Logout",
                result['success'],
                result['response'],
                result.get('error')
            )) 