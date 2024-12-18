"""
Job endpoint testing
Tests the job submission and management endpoints
"""
from .base import BaseTest, TestResult
from datetime import datetime, timedelta

class JobTest(BaseTest):
    """Test suite for job endpoints"""
    
    def setup(self):
        """Setup required for job tests - login first"""
        result = self.request(
            "POST",
            "/api/v1/login",
            data={
                "username": self.auth_username,
                "password": self.auth_password
            },
            auth=False
        )
        
        if result['success']:
            self.access_token = result['response']['access_token']
        else:
            raise Exception("Failed to login for job tests")
    
    def test_01_get_sensors(self):
        """Get list of sensors to find an online one for job submission"""
        result = self.request(
            "GET",
            "/api/v1/sensors",
            auth=True,
            auth_token=self.access_token
        )
        
        if result['success']:
            sensors = result['response']['sensors']
            # Find first online sensor
            self.online_sensor = next(
                (s for s in sensors if s['status'] == 'Online'),
                None
            )
        
        self.add_result(TestResult(
            "Get sensors for job submission",
            result['success'] and self.online_sensor is not None,
            result['response'],
            "No online sensors found" if result['success'] and not self.online_sensor else result.get('error')
        ))
    
    def test_02_submit_job(self):
        """Test submitting a basic job"""
        if not hasattr(self, 'online_sensor'):
            self.add_result(TestResult(
                "Submit job",
                False,
                None,
                "No online sensor available (previous test failed)"
            ))
            return
            
        # Calculate times relative to now
        now = datetime.utcnow()
        start_time = now - timedelta(minutes=20)
        end_time = now - timedelta(minutes=5)
        
        job_data = {
            "location": self.online_sensor['location'],
            "params": {
                "description": "Test job submission",
                "src_ip": "192.168.1.100",
                "dst_ip": "192.168.1.200",
                "start_time": start_time.isoformat() + "Z",
                "end_time": end_time.isoformat() + "Z"
            }
        }
        
        result = self.request(
            "POST",
            "/api/v1/jobs/submit",
            data=job_data,
            auth=True,
            auth_token=self.access_token
        )
        
        if result['success']:
            self.job_id = result['response'].get('job_id')
        
        self.add_result(TestResult(
            "Submit basic job",
            result['success'] and self.job_id is not None,
            result['response'],
            "No job_id in response" if result['success'] and not self.job_id else result.get('error')
        ))
    
    def test_03_get_job_status(self):
        """Test getting status of submitted job"""
        if not hasattr(self, 'job_id'):
            self.add_result(TestResult(
                "Get job status",
                False,
                None,
                "No job_id available (previous test failed)"
            ))
            return
            
        result = self.request(
            "GET",
            f"/api/v1/jobs/{self.job_id}/status",
            auth=True,
            auth_token=self.access_token
        )
        
        self.add_result(TestResult(
            "Get job status",
            result['success'],
            result['response'],
            result.get('error')
        ))
    
    def teardown(self):
        """Cleanup after job tests"""
        if hasattr(self, 'access_token'):
            self.request(
                "POST",
                "/api/v1/logout",
                auth=True,
                auth_token=self.access_token
            )