"""
Authentication tests for PCAP Server.
Tests login and logout functionality.
"""
from .base import BaseTest, TestResult

class AuthTest(BaseTest):
    """Test suite for authentication endpoints"""
    
    def test_01_protected_route_no_auth(self):
        """Test accessing protected route without authentication"""
        response = self.request(
            "GET",
            "/api/v1/sensors",  # Try accessing protected endpoint
            auth=False,
            expected_status=401
        )
        self.add_result(TestResult(
            "Access protected route without auth",
            response['success'],
            response['response'],
            response.get('error')
        ))
    
    def test_02_login_invalid(self):
        """Test login with invalid credentials"""
        response = self.request(
            "POST", 
            "/api/v1/login",
            data={
                "username": "invalid",
                "password": "wrong"
            },
            auth=False,
            expected_status=401
        )
        self.add_result(TestResult(
            "Login with invalid credentials",
            response['success'],
            response['response'],
            response.get('error')
        ))
        
    def test_03_login_success(self):
        """Test successful login and token usage"""
        # Login
        login_response = self.request(
            "POST",
            "/api/v1/login",
            data={
                "username": self.auth_username,
                "password": self.auth_password
            },
            auth=False
        )
        self.add_result(TestResult(
            "Login with valid credentials",
            login_response['success'],
            login_response['response'],
            login_response.get('error')
        ))
        
        if not login_response['success']:
            return
            
        # Store token for next test
        self.access_token = login_response['response']['access_token']
        
        # Verify can access protected route with token
        verify_response = self.request(
            "GET",
            "/api/v1/sensors",
            auth=True,
            auth_token=self.access_token
        )
        self.add_result(TestResult(
            "Access protected route with valid token",
            verify_response['success'],
            verify_response['response'],
            verify_response.get('error')
        ))
        
    def test_04_logout(self):
        """Test logout invalidates token"""
        if not hasattr(self, 'access_token'):
            self.add_result(TestResult(
                "Logout",
                False,
                None,
                "No access token available (login failed or not run)"
            ))
            return
            
        # Test logout
        response = self.request(
            "POST",
            "/api/v1/logout",
            auth=True,
            auth_token=self.access_token
        )
        self.add_result(TestResult(
            "Logout",
            response['success'],
            response['response'],
            response.get('error')
        ))
        
        # Verify token is invalid after logout
        verify_response = self.request(
            "GET",
            "/api/v1/sensors",
            auth=True,
            auth_token=self.access_token,
            expected_status=401
        )
        self.add_result(TestResult(
            "Verify token invalid after logout",
            verify_response['success'],
            verify_response['response'],
            verify_response.get('error')
        )) 