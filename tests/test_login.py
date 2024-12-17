"""
Authentication tests for PCAP Server.
Tests login and logout functionality.
"""
from .base import BaseTest, TestResult

class LoginTest(BaseTest):
    """Test suite for authentication endpoints"""
    
    def __init__(self, base_url: str):
        super().__init__(base_url)
        self.access_token = None
    
    def test_login(self) -> None:
        """Test successful login with valid credentials"""
        result = self.request(
            "POST",
            "/api/v1/login",
            data={
                "username": self.auth_username,
                "password": self.auth_password
            },
            auth=False  # Login doesn't require auth
        )
        
        # Store token if login successful
        if result['success']:
            self.access_token = result['response']['access_token']
        
        self.add_result(TestResult(
            "Login with valid credentials",
            result['success'],
            result['response'],
            result.get('error')
        ))
    
    def test_logout(self) -> None:
        """Test logout functionality"""
        if not self.access_token:
            self.add_result(TestResult(
                "Logout",
                False,
                None,
                "Cannot test logout: No access token available (login failed or not run)"
            ))
            return
        
        result = self.request(
            "POST",
            "/api/v1/logout",
            data={},
            auth=True,
            auth_token=self.access_token
        )
        
        self.add_result(TestResult(
            "Logout",
            result['success'],
            result['response'],
            result.get('error')
        ))
        
        # Verify token is invalid after logout
        verify_result = self.request(
            "GET",
            "/api/v1/sensors",  # Use sensors endpoint as a test
            auth=True,
            auth_token=self.access_token,
            expected_status=401  # Should get unauthorized
        )
        
        self.add_result(TestResult(
            "Verify token invalid after logout",
            verify_result['success'],
            verify_result['response'],
            verify_result.get('error')
        )) 