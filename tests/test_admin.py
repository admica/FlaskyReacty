"""
Test suite for admin user management endpoints
"""
from tests.base import BaseTest, TestResult
import json

class AdminUserTest(BaseTest):
    """Test suite for admin user management"""
    
    def __init__(self, base_url: str):
        super().__init__(base_url)
        self.access_token = None
        self.admin_to_add = "testadmin123"  # The admin user we'll try to add
        
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
    
    def test_01_add_admin_as_regular_user(self):
        """Test adding admin user without admin privileges"""
        # Login as test user
        login_response = self.request(
            "POST",
            "/api/v1/login",
            data={
                "username": "test_user",
                "password": self.user_pass
            },
            auth=False
        )
        
        if not login_response['success']:
            self.add_result(TestResult(
                "Login as regular user",
                False,
                None,
                "Failed to login as regular user"
            ))
            return
            
        self.access_token = login_response['response']['access_token']
        
        # Try to add admin user - should fail with 403
        add_response = self.request(
            "POST",
            "/api/v1/admin/users",
            data={"username": self.admin_to_add},
            auth=True,
            auth_token=self.access_token,
            expected_status=403
        )
        
        self.add_result(TestResult(
            "Add admin user without privileges",
            add_response['success'],
            add_response['response'],
            add_response.get('error')
        ))
        
        # Logout
        self.request(
            "POST",
            "/api/v1/logout",
            auth=True,
            auth_token=self.access_token
        )
        self.access_token = None
    
    def test_02_add_admin_as_admin(self):
        """Test adding admin user with admin privileges"""
        # Login as test admin
        login_response = self.request(
            "POST",
            "/api/v1/login",
            data={
                "username": "test_admin",
                "password": self.admin_pass
            },
            auth=False
        )
        
        if not login_response['success']:
            self.add_result(TestResult(
                "Login as admin",
                False,
                None,
                "Failed to login as admin"
            ))
            return
            
        self.access_token = login_response['response']['access_token']
        
        # Add admin user - should succeed with 201 Created
        add_response = self.request(
            "POST",
            "/api/v1/admin/users",
            data={"username": self.admin_to_add},
            auth=True,
            auth_token=self.access_token,
            expected_status=201
        )
        
        self.add_result(TestResult(
            "Add admin user with admin privileges",
            add_response['success'],
            add_response['response'],
            add_response.get('error')
        ))
    
    def test_03_get_admin_user(self):
        """Test getting admin user details"""
        if not self.access_token:
            self.add_result(TestResult(
                "Get admin user details",
                False,
                None,
                "No access token available (previous test failed)"
            ))
            return
            
        # Get admin user details
        get_response = self.request(
            "GET",
            f"/api/v1/admin/users/{self.admin_to_add}",
            auth=True,
            auth_token=self.access_token
        )
        
        # Include full response details in error for debugging
        success = get_response['success']
        error = None if success else f"Status: {get_response.get('status_code')}, Response: {get_response.get('response')}, Error: {get_response.get('error')}"
        
        self.add_result(TestResult(
            "Get admin user details",
            success,
            get_response.get('response'),
            error
        ))
    
    def test_04_remove_admin_user(self):
        """Test removing admin user"""
        if not self.access_token:
            self.add_result(TestResult(
                "Remove admin user",
                False,
                None,
                "No access token available (previous test failed)"
            ))
            return
            
        # Remove admin user
        remove_response = self.request(
            "DELETE",
            f"/api/v1/admin/users/{self.admin_to_add}",
            auth=True,
            auth_token=self.access_token
        )
        
        self.add_result(TestResult(
            "Remove admin user",
            remove_response['success'],
            remove_response.get('response'),
            remove_response.get('error')
        ))
        
        # Verify user was removed - should get 404
        verify_response = self.request(
            "GET",
            f"/api/v1/admin/users/{self.admin_to_add}",
            auth=True,
            auth_token=self.access_token,
            expected_status=404
        )
        
        # Include full response details in error for debugging
        success = verify_response['success']
        error = None if success else f"Status: {verify_response.get('status_code')}, Response: {verify_response.get('response')}, Error: {verify_response.get('error')}"
        
        self.add_result(TestResult(
            "Verify admin user was removed",
            success,
            verify_response.get('response'),
            error
        ))
    
    def teardown(self):
        """Cleanup - logout if needed"""
        if self.access_token:
            self.request(
                "POST",
                "/api/v1/logout",
                auth=True,
                auth_token=self.access_token
            )
