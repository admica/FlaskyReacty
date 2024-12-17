"""
Log endpoint testing
Tests the log-related endpoints for listing and retrieving log content
"""
from .base import BaseTest, TestResult
import urllib.parse

class LogTest(BaseTest):
    """Test suite for log-related endpoints"""
    
    def setup(self):
        """Setup required for log tests - login to get access token"""
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
            raise Exception("Failed to login for log tests")
            
        self.access_token = result['response']['access_token']
        
        self.add_result(TestResult(
            "Setup - Login",
            True,
            {"status": "logged in"}
        ))

    def test_01_list_logs(self):
        """Test getting list of available log files"""
        result = self.request(
            "GET",
            "/api/v1/logs",
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
            elif 'files' not in data:
                success = False
                error = "Missing 'files' field in response"
            elif not isinstance(data['files'], list):
                success = False
                error = "'files' field is not a list"
            elif 'timestamp' not in data:
                success = False
                error = "Missing 'timestamp' field in response"
            elif data['files']:
                # Validate first log entry structure if we have any
                first_log = data['files'][0]
                required_fields = {
                    'name': str,
                    'size': (int, str),  # Size could be int bytes or str formatted
                    'modified': str
                }
                
                for field, field_type in required_fields.items():
                    if field not in first_log:
                        success = False
                        error = f"Missing field '{field}' in log entry"
                        break
                    if not isinstance(first_log[field], field_type):
                        success = False
                        error = f"Field '{field}' has wrong type"
                        break
        
        self.add_result(TestResult(
            "List available logs",
            success,
            result['response'],
            error or result.get('error')
        ))
        
        # Store first log file name for next test if available
        if success and data['files']:
            self.test_log_file = data['files'][0]['name']

    def test_02_get_log_content(self):
        """Test getting content of a specific log file"""
        if not hasattr(self, 'test_log_file'):
            self.add_result(TestResult(
                "Get log content",
                False,
                None,
                "No log file available from previous test"
            ))
            return
            
        # URL encode the log file name
        encoded_path = urllib.parse.quote(self.test_log_file)
        
        result = self.request(
            "GET",
            f"/api/v1/logs/{encoded_path}/content",
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
            elif 'content' not in data:
                success = False
                error = "Missing 'content' field in response"
            elif not isinstance(data['content'], list):  # Content is returned as list of lines
                success = False
                error = "'content' field is not a list"
            elif 'timestamp' not in data:
                success = False
                error = "Missing 'timestamp' field in response"
        
        self.add_result(TestResult(
            f"Get content of log file: {self.test_log_file}",
            success,
            result['response'],
            error or result.get('error')
        ))

    def test_03_get_invalid_log(self):
        """Test getting content of a non-existent log file"""
        result = self.request(
            "GET",
            "/api/v1/logs/invalid_log_file.log/content",
            auth=True,
            auth_token=self.access_token,
            expected_status=404
        )
        
        self.add_result(TestResult(
            "Get invalid log file",
            result['success'],
            result['response'],
            result.get('error')
        ))

    def test_04_get_log_no_auth(self):
        """Test accessing logs without authentication"""
        result = self.request(
            "GET",
            "/api/v1/logs",
            auth=False,
            expected_status=401
        )
        
        self.add_result(TestResult(
            "Access logs without auth",
            result['success'],
            result['response'],
            result.get('error')
        ))

    def teardown(self):
        """Cleanup after log tests"""
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