"""
Test suite for admin user management and audit log functionality
"""
from tests.base import BaseTest, TestResult
import json

class AdminTest(BaseTest):
    """Test suite for admin user management and audit logging"""
    
    def __init__(self, base_url: str):
        super().__init__(base_url)
        self.admin_token = None
        self.user_token = None
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
    
    def setup(self):
        """Setup test environment - login as both admin and regular user"""
        # Login as test user
        user_login = self.request(
            "POST",
            "/api/v1/login",
            data={
                "username": "test_user",
                "password": self.user_pass
            },
            auth=False
        )
        
        if not user_login['success']:
            self.add_result(TestResult(
                "Login as regular user",
                False,
                None,
                "Failed to login as regular user"
            ))
            return False
            
        self.user_token = user_login['response']['access_token']
        
        # Login as test admin
        admin_login = self.request(
            "POST",
            "/api/v1/login",
            data={
                "username": "test_admin",
                "password": self.admin_pass
            },
            auth=False
        )
        
        if not admin_login['success']:
            self.add_result(TestResult(
                "Login as admin",
                False,
                None,
                "Failed to login as admin"
            ))
            return False
            
        self.admin_token = admin_login['response']['access_token']
        return True
    
    def test_01_add_admin_as_regular_user(self):
        """Test adding admin user without admin privileges"""
        response = self.request(
            "POST",
            "/api/v1/admin/users",
            data={"username": self.admin_to_add},
            auth=True,
            auth_token=self.user_token,
            expected_status=403
        )
        
        self.add_result(TestResult(
            "Add admin user without privileges",
            response['success'],
            response['response'],
            response.get('error')
        ))
    
    def test_02_add_admin_as_admin(self):
        """Test adding admin user with admin privileges"""
        response = self.request(
            "POST",
            "/api/v1/admin/users",
            data={"username": self.admin_to_add},
            auth=True,
            auth_token=self.admin_token,
            expected_status=201
        )
        
        self.add_result(TestResult(
            "Add admin user with admin privileges",
            response['success'],
            response['response'],
            response.get('error')
        ))
        
        # Verify audit log entry for add action
        audit_response = self.request(
            "GET",
            f"/api/v1/admin/audit?username={self.admin_to_add}&action=ADD&limit=1",
            auth=True,
            auth_token=self.admin_token
        )
        
        success = audit_response['success']
        error = None
        if success:
            data = audit_response['response']
            if not data.get('audit_logs'):
                success = False
                error = "No audit log entry found"
            else:
                log = data['audit_logs'][0]
                if (log.get('action') != 'ADD' or 
                    log.get('username') != self.admin_to_add or
                    log.get('changed_by') != 'test_admin'):
                    success = False
                    error = f"Invalid log entry: {log}"
        
        self.add_result(TestResult(
            "Verify audit log for add action",
            success,
            audit_response.get('response'),
            error or audit_response.get('error')
        ))
    
    def test_03_get_admin_user(self):
        """Test getting admin user details"""
        response = self.request(
            "GET",
            f"/api/v1/admin/users/{self.admin_to_add}",
            auth=True,
            auth_token=self.admin_token
        )
        
        success = response['success']
        error = None
        if success:
            data = response['response']
            if not isinstance(data, dict):
                success = False
                error = "Invalid response format"
            elif not all(key in data for key in ['username', 'type', 'created_at', 'added_by']):
                success = False
                error = "Missing required fields in response"
            elif data['username'] != self.admin_to_add:
                success = False
                error = "Incorrect username in response"
        
        self.add_result(TestResult(
            "Get admin user details",
            success,
            response.get('response'),
            error or response.get('error')
        ))
    
    def test_04_audit_log_filters(self):
        """Test audit log filtering options"""
        # Test username filter
        username_response = self.request(
            "GET",
            f"/api/v1/admin/audit?username={self.admin_to_add}",
            auth=True,
            auth_token=self.admin_token
        )
        
        success = username_response['success']
        error = None
        if success:
            data = username_response['response']
            if not data.get('audit_logs'):
                success = False
                error = "No audit logs found"
            else:
                for log in data['audit_logs']:
                    if log.get('username') != self.admin_to_add:
                        success = False
                        error = "Username filter not respected"
                        break
        
        self.add_result(TestResult(
            "Filter audit log by username",
            success,
            username_response.get('response'),
            error or username_response.get('error')
        ))
        
        # Test action filter
        action_response = self.request(
            "GET",
            "/api/v1/admin/audit?action=ADD",
            auth=True,
            auth_token=self.admin_token
        )
        
        success = action_response['success']
        error = None
        if success:
            data = action_response['response']
            if not data.get('audit_logs'):
                success = False
                error = "No audit logs found"
            else:
                for log in data['audit_logs']:
                    if log.get('action') != 'ADD':
                        success = False
                        error = "Action filter not respected"
                        break
        
        self.add_result(TestResult(
            "Filter audit log by action",
            success,
            action_response.get('response'),
            error or action_response.get('error')
        ))
        
        # Test limit filter
        limit_response = self.request(
            "GET",
            "/api/v1/admin/audit?limit=1",
            auth=True,
            auth_token=self.admin_token
        )
        
        success = limit_response['success']
        error = None
        if success:
            data = limit_response['response']
            if len(data.get('audit_logs', [])) > 1:
                success = False
                error = "Limit filter not respected"
        
        self.add_result(TestResult(
            "Filter audit log with limit",
            success,
            limit_response.get('response'),
            error or limit_response.get('error')
        ))
    
    def test_05_remove_admin_user(self):
        """Test removing admin user"""
        response = self.request(
            "DELETE",
            f"/api/v1/admin/users/{self.admin_to_add}",
            auth=True,
            auth_token=self.admin_token
        )
        
        self.add_result(TestResult(
            "Remove admin user",
            response['success'],
            response.get('response'),
            response.get('error')
        ))
        
        # Verify audit log entry for remove action
        audit_response = self.request(
            "GET",
            f"/api/v1/admin/audit?username={self.admin_to_add}&action=REMOVE&limit=1",
            auth=True,
            auth_token=self.admin_token
        )
        
        success = audit_response['success']
        error = None
        if success:
            data = audit_response['response']
            if not data.get('audit_logs'):
                success = False
                error = "No audit log entry found"
            else:
                log = data['audit_logs'][0]
                if (log.get('action') != 'REMOVE' or 
                    log.get('username') != self.admin_to_add or
                    log.get('changed_by') != 'pcapuser'):  # Database trigger uses current_user
                    success = False
                    error = f"Invalid log entry: {log}"
        
        self.add_result(TestResult(
            "Verify audit log for remove action",
            success,
            audit_response.get('response'),
            error or audit_response.get('error')
        ))
        
        # Verify user was removed
        verify_response = self.request(
            "GET",
            f"/api/v1/admin/users/{self.admin_to_add}",
            auth=True,
            auth_token=self.admin_token,
            expected_status=404
        )
        
        self.add_result(TestResult(
            "Verify admin user was removed",
            verify_response['success'],
            verify_response.get('response'),
            verify_response.get('error')
        ))
    
    def teardown(self):
        """Cleanup - logout both users"""
        if self.user_token:
            self.request(
                "POST",
                "/api/v1/logout",
                auth=True,
                auth_token=self.user_token
            )
        if self.admin_token:
            self.request(
                "POST",
                "/api/v1/logout",
                auth=True,
                auth_token=self.admin_token
            )
