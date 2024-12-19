"""
Test suite for IP search functionality
"""
from tests.base import BaseTest, TestResult
from core import db
import json
import time
from datetime import datetime, timezone

class IPSearchTest(BaseTest):
    """Test suite for IP search endpoints"""
    
    def __init__(self, base_url: str):
        super().__init__(base_url)
        self.access_token = None
        self.test_ip = None  # Will be set in setup after getting a real IP
    
    def setup(self):
        """Setup test environment - login and get token"""
        # Login with regular user from config.ini
        login_response = self.request(
            "POST",
            "/api/v1/login",
            data={
                "username": "user",  # Regular user from config.ini
                "password": "user"   # Default password from config.ini
            },
            auth=False
        )
        
        if not login_response['success']:
            self.add_result(TestResult(
                "Login for IP search tests",
                False,
                None,
                "Failed to login"
            ))
            return False
            
        self.access_token = login_response['response']['access_token']
        
        # Get list of loc_src_* tables directly from database
        tables = db("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name LIKE 'loc_src_%'
            AND table_schema = 'public'
            ORDER BY table_name
        """)
        
        if not tables:
            self.add_result(TestResult(
                "Get location tables",
                False,
                None,
                "No source location tables found"
            ))
            return False
            
        # Get first IP from the first table
        first_table = tables[0][0]
        result = db(f"""
            SELECT subnet::text
            FROM {first_table}
            WHERE count > 0
            ORDER BY last_seen DESC
            LIMIT 1
        """)
        
        if not result:
            self.add_result(TestResult(
                "Get test IP",
                False,
                None,
                "No IPs found in first location table"
            ))
            return False
            
        # Extract an IP from the subnet (e.g., "192.168.1.0/24" -> "192.168.1.100")
        subnet = result[0][0]
        base_ip = subnet.split('/')[0]  # Get the network portion
        ip_parts = base_ip.split('.')
        ip_parts[-1] = "100"  # Use .100 in the last octet
        self.test_ip = ".".join(ip_parts)
        
        return True
    
    def test_01_search_source_ip(self):
        """Test searching for a source IP"""
        result = self.request(
            "POST",
            "/api/v1/search/ip",
            data={
                "src_ip": self.test_ip
            },
            auth=True,
            auth_token=self.access_token
        )
        
        success = result['success']
        error = None
        
        if success:
            data = result['response']
            if not isinstance(data, dict):
                success = False
                error = "Response is not a dictionary"
            elif not all(key in data for key in ['matches', 'confidence']):
                success = False
                error = "Missing required fields in response"
        
        self.add_result(TestResult(
            "Search for source IP",
            success,
            result['response'],
            error or result.get('error')
        ))
    
    def test_02_search_with_timerange(self):
        """Test searching with a time range"""
        # Use UNIX timestamps for the time range
        current_time = int(time.time())
        start_time = current_time - 3600  # 1 hour ago
        end_time = current_time
        
        result = self.request(
            "POST",
            "/api/v1/search/ip",
            data={
                "src_ip": self.test_ip,
                "start_time": start_time,
                "end_time": end_time
            },
            auth=True,
            auth_token=self.access_token
        )
        
        success = result['success']
        error = None
        
        if success:
            data = result['response']
            if not isinstance(data, dict):
                success = False
                error = "Response is not a dictionary"
            elif not all(key in data for key in ['matches', 'confidence']):
                success = False
                error = "Missing required fields in response"
        
        self.add_result(TestResult(
            "Search with time range",
            success,
            result['response'],
            error or result.get('error')
        ))
    
    def test_03_invalid_ip_format(self):
        """Test searching with invalid IP format"""
        result = self.request(
            "POST",
            "/api/v1/search/ip",
            data={
                "src_ip": "invalid.ip.address"
            },
            auth=True,
            auth_token=self.access_token,
            expected_status=400
        )
        
        self.add_result(TestResult(
            "Search with invalid IP format",
            result['success'],
            result['response'],
            result.get('error')
        ))
    
    def test_04_invalid_time_format(self):
        """Test searching with invalid time format"""
        result = self.request(
            "POST",
            "/api/v1/search/ip",
            data={
                "src_ip": self.test_ip,
                "start_time": "invalid-time",
                "end_time": "2024-12-31T23:59:59Z"
            },
            auth=True,
            auth_token=self.access_token,
            expected_status=400
        )
        
        self.add_result(TestResult(
            "Search with invalid time format",
            result['success'],
            result['response'],
            result.get('error')
        ))
    
    def test_05_authentication(self):
        """Test search endpoint authentication"""
        result = self.request(
            "POST",
            "/api/v1/search/ip",
            data={
                "src_ip": self.test_ip
            },
            auth=False,
            expected_status=401
        )
        
        self.add_result(TestResult(
            "Search without authentication",
            result['success'],
            result['response'],
            result.get('error')
        )) 