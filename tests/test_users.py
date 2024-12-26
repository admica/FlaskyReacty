"""
User session endpoint testing
Tests the user session-related endpoints for listing active sessions
"""
from .base import BaseTest, TestResult
import json

class UserTest(BaseTest):
    """Test suite for user session-related endpoints"""
    
    def __init__(self, base_url: str):
        super().__init__(base_url)
        self.user_token = None
        
        # Get test account credentials from config
        if not self.config.getboolean('TEST_MODE', 'allow_test_login', fallback=False):
            raise Exception("Test mode is not enabled (allow_test_login must be true)")
            
        test_users = self.config.items('TEST_USERS')
        for _, user_json in test_users:
            try:
                user_data = json.loads(user_json)
                if user_data.get('username') == 'test_user':
                    self.user_pass = user_data.get('password')
                    break
            except json.JSONDecodeError:
                continue
                
        if not hasattr(self, 'user_pass'):
            raise Exception("Could not find test_user account in TEST_USERS section")
    
    def setup(self):
        """Setup required for user tests - login as regular user"""
        result = self.request(
            "POST",
            "/api/v1/login",
            data={
                "username": "test_user",
                "password": self.user_pass
            },
            auth=False
        )
        
        if not result['success']:
            raise Exception("Failed to login as regular user")
            
        self.user_token = result['response']['access_token']
        
        self.add_result(TestResult(
            "Setup - Login user",
            True,
            {"status": "logged in"}
        ))

    def test_01_list_sessions(self):
        """Test getting list of active user sessions"""
        result = self.request(
            "GET",
            "/api/v1/users/sessions",
            auth=True,
            auth_token=self.user_token
        )
        
        success = result['success']
        error = None
        
        if success:
            data = result['response']
            # Validate response structure
            if not isinstance(data, dict):
                success = False
                error = "Response is not a dictionary"
            elif 'sessions' not in data:
                success = False
                error = "Missing 'sessions' field in response"
            elif not isinstance(data['sessions'], list):
                success = False
                error = "'sessions' field is not a list"
            elif data['sessions']:
                # Validate first session entry structure
                first_session = data['sessions'][0]
                required_fields = {
                    'username': str,
                    'created_at': str,
                    'expires_at': str,
                    'is_current': bool
                }
                
                for field, field_type in required_fields.items():
                    if field not in first_session:
                        success = False
                        error = f"Missing field '{field}' in session entry"
                        break
                    if not isinstance(first_session[field], field_type):
                        success = False
                        error = f"Field '{field}' has wrong type"
                        break

        self.add_result(TestResult(
            "List active sessions",
            success,
            result['response'],
            error or result.get('error')
        ))

    def test_02_list_sessions_no_auth(self):
        """Test accessing sessions without authentication"""
        result = self.request(
            "GET",
            "/api/v1/users/sessions",
            auth=False,
            expected_status=401
        )
        
        self.add_result(TestResult(
            "Access sessions without auth",
            result['success'],
            result['response'],
            result.get('error')
        ))

    def teardown(self):
        """Cleanup after user tests"""
        if self.user_token:
            result = self.request(
                "POST",
                "/api/v1/logout",
                auth=True,
                auth_token=self.user_token
            )
            self.add_result(TestResult(
                "Teardown - Logout user",
                result['success'],
                result['response'],
                result.get('error')
            )) 