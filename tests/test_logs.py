"""
Log endpoint testing
Tests the log-related endpoints for listing and retrieving log content
"""
from .base import BaseTest, TestResult
import urllib.parse
import json

class LogTest(BaseTest):
    """Test suite for log-related endpoints"""
    
    def __init__(self, base_url: str):
        super().__init__(base_url)
        self.user_token = None
        self.admin_token = None
        
        # Get test account credentials from config
        if not self.config.getboolean('TEST_MODE', 'allow_test_login', fallback=False):
            raise Exception("Test mode is not enabled (allow_test_login must be true)")
            
        test_users = self.config.items('TEST_USERS')
        for _, user_json in test_users:
            try:
                user_data = json.loads(user_json)
                if user_data.get('username') == 'test_user':
                    self.user_pass = user_data.get('password')
                elif user_data.get('username') == 'test_admin':
                    self.admin_pass = user_data.get('password')
            except json.JSONDecodeError:
                continue
                
        if not hasattr(self, 'admin_pass') or not hasattr(self, 'user_pass'):
            raise Exception("Could not find test accounts in TEST_USERS section")
    
    def setup(self):
        """Setup required for log tests - login as both regular user and admin"""
        # Login as regular user
        user_result = self.request(
            "POST",
            "/api/v1/login",
            data={
                "username": "test_user",
                "password": self.user_pass
            },
            auth=False
        )
        
        if not user_result['success']:
            raise Exception("Failed to login as regular user")
            
        self.user_token = user_result['response']['access_token']
        
        # Login as admin
        admin_result = self.request(
            "POST",
            "/api/v1/login",
            data={
                "username": "test_admin",
                "password": self.admin_pass
            },
            auth=False
        )
        
        if not admin_result['success']:
            raise Exception("Failed to login as admin")
            
        self.admin_token = admin_result['response']['access_token']
        
        self.add_result(TestResult(
            "Setup - Login both users",
            True,
            {"status": "logged in"}
        ))

    def test_01_list_logs_as_user(self):
        """Test getting list of available log files as regular user (should fail)"""
        result = self.request(
            "GET",
            "/api/v1/logs",
            auth=True,
            auth_token=self.user_token,
            expected_status=403  # Expect forbidden
        )
        
        self.add_result(TestResult(
            "List available logs as regular user",
            result['success'],
            result['response'],
            result.get('error')
        ))

    def test_02_list_logs_as_admin(self):
        """Test getting list of available log files as admin"""
        result = self.request(
            "GET",
            "/api/v1/logs",
            auth=True,
            auth_token=self.admin_token
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
            "List available logs as admin",
            success,
            result['response'],
            error or result.get('error')
        ))
        
        # Store first log file name for next test if available
        if success and data['files']:
            self.test_log_file = data['files'][0]['name']

    def test_03_get_log_content_as_user(self):
        """Test getting content of a log file as regular user (should fail)"""
        if not hasattr(self, 'test_log_file'):
            self.add_result(TestResult(
                "Get log content as regular user",
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
            auth_token=self.user_token,
            expected_status=403  # Expect forbidden
        )
        
        self.add_result(TestResult(
            "Get log content as regular user",
            result['success'],
            result['response'],
            result.get('error')
        ))

    def test_04_get_log_content_as_admin(self):
        """Test getting content of a log file as admin"""
        if not hasattr(self, 'test_log_file'):
            self.add_result(TestResult(
                "Get log content as admin",
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
            auth_token=self.admin_token
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
            "Get log content as admin",
            success,
            result['response'],
            error or result.get('error')
        ))

    def test_05_get_invalid_log_as_admin(self):
        """Test getting content of a non-existent log file as admin"""
        result = self.request(
            "GET",
            "/api/v1/logs/invalid_log_file.log/content",
            auth=True,
            auth_token=self.admin_token,
            expected_status=404
        )
        
        self.add_result(TestResult(
            "Get invalid log file as admin",
            result['success'],
            result['response'],
            result.get('error')
        ))

    def test_06_get_log_no_auth(self):
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
        # Logout regular user
        if self.user_token:
            result = self.request(
                "POST",
                "/api/v1/logout",
                auth=True,
                auth_token=self.user_token
            )
            self.add_result(TestResult(
                "Teardown - Logout regular user",
                result['success'],
                result['response'],
                result.get('error')
            ))
            
        # Logout admin user
        if self.admin_token:
            result = self.request(
                "POST",
                "/api/v1/logout",
                auth=True,
                auth_token=self.admin_token
            )
            self.add_result(TestResult(
                "Teardown - Logout admin user",
                result['success'],
                result['response'],
                result.get('error')
            )) 