"""
Test job fetching functionality
Tests the job listing and task retrieval endpoints
"""
from .base import BaseTest, TestResult

class JobFetchTest(BaseTest):
    """Test suite for job fetching endpoints"""
    
    def __init__(self, base_url: str):
        super().__init__(base_url)
        self.access_token = None
    
    def setup(self):
        """Setup required for job fetch tests - login first"""
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
            raise Exception("Failed to login for job fetch tests")
            
        self.access_token = result['response']['access_token']
    
    def test_01_get_all_jobs(self):
        """Test getting all jobs"""
        result = self.request(
            "GET",
            "/api/v1/jobs",
            auth=True,
            auth_token=self.access_token
        )
        
        success = False
        if result['success']:
            jobs = result['response'].get('jobs', [])
            # Find job ID 5
            job = next((j for j in jobs if j['id'] == 5), None)
            if job:
                # Verify exact job data
                expected_job = {
                    'id': 5,
                    'location': 'KSC',
                    'description': 'Test job submission - event time only',
                    'src_ip': '192.168.1.100',
                    'dst_ip': '192.168.1.200',
                    'status': 'Complete',
                    'submitted_by': 'test_admin',
                    'result_size': '1024',
                    'result_path': '/data/jobs/5.pcap',
                    'result_message': 'Successfully merged 1 PCAP files'
                }
                
                # Check all expected fields match
                matches = all(job[k] == v for k, v in expected_job.items())
                if matches:
                    success = True
                    self.job = job  # Store for next test
        
        self.add_result(TestResult(
            "Get all jobs",
            success,
            result['response'],
            "Job ID 5 not found or data mismatch" if not success else None
        ))
    
    def test_02_verify_task_data(self):
        """Test task data for job ID 5"""
        if not hasattr(self, 'job'):
            self.add_result(TestResult(
                "Verify task data",
                False,
                None,
                "Job data not available (previous test failed)"
            ))
            return
        
        success = False
        tasks = self.job.get('tasks', [])
        if tasks:
            task = tasks[0]  # Should only be one task
            # Verify exact task data
            expected_task = {
                'id': 5,
                'job_id': 5,
                'task_id': 1,
                'sensor': 'ksc1',
                'status': 'Complete',
                'pcap_size': '1024',
                'temp_path': '/data/tasks/5_1.pcap',
                'result_message': '{"has_data": true, "remote_path": "/tmp/pcap_5.pcap", "local_path": "/data/tasks/5_1.pcap", "file_size": 1024}'
            }
            
            # Check all expected fields match
            matches = all(task[k] == v for k, v in expected_task.items())
            if matches:
                success = True
        
        self.add_result(TestResult(
            "Verify task data",
            success,
            {'tasks': tasks},
            "Task data mismatch or not found" if not success else None
        ))
    
    def teardown(self):
        """Cleanup after job fetch tests"""
        if hasattr(self, 'access_token'):
            self.request(
                "POST",
                "/api/v1/logout",
                auth=True,
                auth_token=self.access_token
            ) 