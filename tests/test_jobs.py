"""
Job endpoint testing
Tests the job submission and management endpoints
"""
from .base import BaseTest, TestResult
from datetime import datetime, timedelta

class JobTest(BaseTest):
    """Test suite for job endpoints"""
    
    def __init__(self, base_url: str):
        super().__init__(base_url)
        self.access_token = None
    
    def setup(self):
        """Setup required for job tests - login first"""
        result = self.request(
            "POST",
            "/api/v1/login",
            data={
                "username": self.auth_username,
                "password": self.auth_password
            },
            auth=False  # No auth token yet since we're logging in
        )
        
        if not result['success']:
            raise Exception("Failed to login for job tests")
            
        self.access_token = result['response']['access_token']
    
    def test_01_get_sensors(self):
        """Get list of sensors to find an online one for job submission"""
        result = self.request(
            "GET",
            "/api/v1/sensors",
            auth=True,
            auth_token=self.access_token
        )
        
        if result['success']:
            sensors = result['response'].get('sensors', [])
            # Find first online sensor
            self.online_sensor = next((s for s in sensors if s.get('status') == 'Online'), None)
        
        self.add_result(TestResult(
            "Get sensors for job submission",
            result['success'] and self.online_sensor is not None,
            result['response'],
            "No online sensors found" if result['success'] and not self.online_sensor else result.get('error')
        ))
    
    def test_02_submit_job_with_event_time(self):
        """Test submitting a job with event_time only"""
        if not hasattr(self, 'online_sensor'):
            self.add_result(TestResult(
                "Submit job with event time",
                False,
                None,
                "No online sensor available (previous test failed)"
            ))
            return
            
        # Calculate times relative to now
        now = datetime.utcnow()
        event_time = now - timedelta(minutes=10)
        
        job_data = {
            "location": self.online_sensor['location'],
            "params": {
                "description": "Test job submission - event time only",
                "src_ip": "192.168.1.100",
                "dst_ip": "192.168.1.200",
                "event_time": event_time.isoformat() + "Z"
            }
        }
        
        result = self.request(
            "POST",
            "/api/v1/jobs/submit",
            data=job_data,
            auth=True,
            auth_token=self.access_token,
            expected_status=201  # Created status code
        )
        
        # Store the job parameters for later tests
        if result['success']:
            self.job_params = result['response'].get('params', {})
            self.job_location = result['response'].get('location')
        
        self.add_result(TestResult(
            "Submit job with event time",
            result['success'],
            result['response'],
            result.get('error')
        ))
    
#    def test_03_submit_job_with_start_end(self):
#        """Test submitting a job with explicit start and end times"""
#        if not hasattr(self, 'online_sensor'):
#            self.add_result(TestResult(
#                "Submit job with start/end times",
#                False,
#                None,
#                "No online sensor available (previous test failed)"
#            ))
#            return
#            
#        # Calculate times relative to now
#        now = datetime.utcnow()
#        start_time = now - timedelta(minutes=15)
#        end_time = now - timedelta(minutes=5)
#        
#        job_data = {
#            "location": self.online_sensor['location'],
#            "params": {
#                "description": "Test job submission - explicit start/end",
#                "src_ip": "192.168.1.100",
#                "dst_ip": "192.168.1.200",
#                "start_time": start_time.isoformat() + "Z",
#                "end_time": end_time.isoformat() + "Z"
#            }
#        }
#        
#        result = self.request(
#            "POST",
#            "/api/v1/jobs/submit",
#            data=job_data,
#            auth=True,
#            auth_token=self.access_token,
#            expected_status=201  # Created status code
#        )
#        
#        # Store the job parameters for later tests
#        if result['success']:
#            self.job_params = result['response'].get('params', {})
#            self.job_location = result['response'].get('location')
#        
#        self.add_result(TestResult(
#            "Submit job with start/end times",
#            result['success'],
#            result['response'],
#            result.get('error')
#        ))
#    
#    def test_04_submit_job_with_all_times(self):
#        """Test submitting a job with event, start, and end times"""
#        if not hasattr(self, 'online_sensor'):
#            self.add_result(TestResult(
#                "Submit job with all times",
#                False,
#                None,
#                "No online sensor available (previous test failed)"
#            ))
#            return
#            
#        # Calculate times relative to now
#        now = datetime.utcnow()
#        event_time = now - timedelta(minutes=10)
#        start_time = now - timedelta(minutes=15)
#        end_time = now - timedelta(minutes=5)
#        
#        job_data = {
#            "location": self.online_sensor['location'],
#            "params": {
#                "description": "Test job submission - all times",
#                "src_ip": "192.168.1.100",
#                "dst_ip": "192.168.1.200",
#                "event_time": event_time.isoformat() + "Z",
#                "start_time": start_time.isoformat() + "Z",
#                "end_time": end_time.isoformat() + "Z"
#            }
#        }
#        
#        result = self.request(
#            "POST",
#            "/api/v1/jobs/submit",
#            data=job_data,
#            auth=True,
#            auth_token=self.access_token,
#            expected_status=201  # Created status code
#        )
#        
#        # Store the job parameters for later tests
#        if result['success']:
#            self.job_params = result['response'].get('params', {})
#            self.job_location = result['response'].get('location')
#        
#        self.add_result(TestResult(
#            "Submit job with all times",
#            result['success'],
#            result['response'],
#            result.get('error')
#        ))
    
    def test_05_get_job_status(self):
        """Test getting status of submitted job"""
        if not hasattr(self, 'job_params') or not hasattr(self, 'job_location'):
            self.add_result(TestResult(
                "Get job status",
                False,
                None,
                "No job parameters available (previous test failed)"
            ))
            return
            
        # Get all jobs for the location
        result = self.request(
            "GET",
            f"/api/v1/jobs/{self.job_location}",
            auth=True,
            auth_token=self.access_token
        )
        
        success = False
        if result['success']:
            # Find our job by matching parameters
            jobs = result['response'].get('jobs', [])
            for job in jobs:
                if (job.get('src_ip') == self.job_params.get('src_ip') and
                    job.get('dst_ip') == self.job_params.get('dst_ip') and
                    job.get('description') == self.job_params.get('description')):
                    success = True
                    break
        
        self.add_result(TestResult(
            "Get job status",
            success,
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
