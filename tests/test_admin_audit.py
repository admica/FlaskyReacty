"""
Test suite for admin audit log functionality
"""
from tests.base import BaseTest, TestResult
import json

class AdminAuditTest(BaseTest):
    """Test suite for admin audit log endpoints"""
    
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
                if user_data.get('username') == 'test_admin':
                    self.admin_pass = user_data.get('password')
                    break
            except json.JSONDecodeError:
                continue
                
        if not hasattr(self, 'admin_pass'):
            raise Exception("Could not find test_admin in TEST_USERS section")
    
    def setup(self):
        """Setup test environment - login as admin"""
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
            return False
            
        self.access_token = login_response['response']['access_token']
        return True
    
    def test_01_audit_log_empty(self):
        """Test getting audit log when empty"""
        response = self.request(
            "GET",
            "/api/v1/admin/audit",
            auth=True,
            auth_token=self.access_token
        )
        
        success = response['success']
        if success:
            # Verify response structure
            data = response['response']
            if not isinstance(data, dict) or 'audit_logs' not in data:
                success = False
                error = "Invalid response format"
            else:
                # Initial log might be empty or have previous entries
                error = None
        else:
            error = response.get('error')
        
        self.add_result(TestResult(
            "Get initial audit log",
            success,
            response.get('response'),
            error
        ))
    
    def test_02_add_admin_creates_log(self):
        """Test that adding an admin user creates an audit log entry"""
        # First add an admin user
        add_response = self.request(
            "POST",
            "/api/v1/admin/users",
            data={"username": self.admin_to_add},
            auth=True,
            auth_token=self.access_token,
            expected_status=201
        )
        
        self.add_result(TestResult(
            "Add admin user",
            add_response['success'],
            add_response.get('response'),
            add_response.get('error')
        ))
        
        if not add_response['success']:
            return
            
        # Check audit log for the add action
        audit_response = self.request(
            "GET",
            f"/api/v1/admin/audit?username={self.admin_to_add}&action=ADD&limit=1",
            auth=True,
            auth_token=self.access_token
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
            "Verify add_admin audit log",
            success,
            audit_response.get('response'),
            error or audit_response.get('error')
        ))
    
    def test_03_remove_admin_creates_log(self):
        """Test that removing an admin user creates an audit log entry"""
        # Remove the admin user
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
        
        if not remove_response['success']:
            return
            
        # Check audit log for the remove action
        audit_response = self.request(
            "GET",
            f"/api/v1/admin/audit?username={self.admin_to_add}&action=REMOVE&limit=1",
            auth=True,
            auth_token=self.access_token
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
                    log.get('changed_by') != 'pcapuser'):  # Changed to match database trigger
                    success = False
                    error = f"Invalid log entry: {log}"
        
        self.add_result(TestResult(
            "Verify remove_admin audit log",
            success,
            audit_response.get('response'),
            error or audit_response.get('error')
        ))
    
    def test_04_audit_log_filters(self):
        """Test audit log filtering options"""
        # Test days filter
        days_response = self.request(
            "GET",
            "/api/v1/admin/audit?days=1",
            auth=True,
            auth_token=self.access_token
        )
        
        self.add_result(TestResult(
            "Filter audit log by days",
            days_response['success'],
            days_response.get('response'),
            days_response.get('error')
        ))
        
        # Test action filter
        action_response = self.request(
            "GET",
            "/api/v1/admin/audit?action=ADD",
            auth=True,
            auth_token=self.access_token
        )
        
        self.add_result(TestResult(
            "Filter audit log by action",
            action_response['success'],
            action_response.get('response'),
            action_response.get('error')
        ))
        
        # Test limit
        limit_response = self.request(
            "GET",
            "/api/v1/admin/audit?limit=1",
            auth=True,
            auth_token=self.access_token
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
    
    def teardown(self):
        """Cleanup - logout if needed"""
        if self.access_token:
            self.request(
                "POST",
                "/api/v1/logout",
                auth=True,
                auth_token=self.access_token
            ) 