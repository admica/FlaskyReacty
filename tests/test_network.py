"""
Network endpoint testing
Tests the network visualization endpoints
"""
from .base import BaseTest, TestResult
import time

class NetworkTest(BaseTest):
    """Test suite for network visualization endpoints"""
    
    def setup(self):
        """Setup required for network tests - login to get access token"""
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
            raise Exception("Failed to login for network tests")
            
        self.access_token = result['response']['access_token']
        
        self.add_result(TestResult(
            "Setup - Login",
            True,
            {"status": "logged in"}
        ))
    
    def test_01_locations_no_auth(self):
        """Test accessing locations without authentication"""
        result = self.request(
            "GET",
            "/api/v1/network/locations",
            auth=False,
            expected_status=401
        )
        
        self.add_result(TestResult(
            "Access locations without auth",
            result['success'],
            result['response'],
            result.get('error')
        ))
    
    def test_02_get_locations(self):
        """Test getting locations"""
        result = self.request(
            "GET",
            "/api/v1/network/locations",
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
            elif not all(key in data for key in ['locations', 'cached', 'timestamp']):
                success = False
                error = "Missing required fields in response"
            elif not isinstance(data['locations'], list):
                success = False
                error = "Locations is not a list"
            elif data['locations']:  # If we have any locations
                first_loc = data['locations'][0]
                # Check location structure
                required_fields = {
                    'site': str,
                    'name': str,
                    'latitude': float,
                    'longitude': float,
                    'description': (str, type(None)),  # Can be string or null
                    'color': str
                }
                for field, field_type in required_fields.items():
                    if field not in first_loc:
                        success = False
                        error = f"Missing field '{field}' in location data"
                        break
                    if not isinstance(first_loc[field], field_type):
                        if isinstance(field_type, tuple):
                            if not any(isinstance(first_loc[field], t) for t in field_type):
                                success = False
                                error = f"Field '{field}' has wrong type"
                                break
                        else:
                            success = False
                            error = f"Field '{field}' has wrong type"
                            break
        
        self.add_result(TestResult(
            "Get locations",
            success,
            result['response'],
            error or result.get('error')
        ))
    
    def test_03_connections_no_auth(self):
        """Test accessing connections without authentication"""
        result = self.request(
            "GET",
            "/api/v1/network/connections",
            auth=False,
            expected_status=401
        )
        
        self.add_result(TestResult(
            "Access connections without auth",
            result['success'],
            result['response'],
            result.get('error')
        ))
    
    def test_04_get_connections(self):
        """Test getting network connections"""
        result = self.request(
            "GET",
            "/api/v1/network/connections",
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
            elif not all(key in data for key in ['connections', 'cached', 'timestamp']):
                success = False
                error = "Missing required fields in response"
            elif not isinstance(data['connections'], list):
                success = False
                error = "Connections is not a list"
            elif data['connections']:  # If we have any connections
                first_conn = data['connections'][0]
                # Check connection structure
                required_fields = {
                    'src_location': str,
                    'dst_location': str,
                    'unique_subnets': int,
                    'packet_count': int,
                    'earliest_seen': int,
                    'latest_seen': int
                }
                for field, field_type in required_fields.items():
                    if field not in first_conn:
                        success = False
                        error = f"Missing field '{field}' in connection data"
                        break
                    if not isinstance(first_conn[field], field_type):
                        success = False
                        error = f"Field '{field}' has wrong type"
                        break
                
                # Validate timestamps
                if first_conn['earliest_seen'] > first_conn['latest_seen']:
                    success = False
                    error = "earliest_seen is after latest_seen"
        
        self.add_result(TestResult(
            "Get network connections",
            success,
            result['response'],
            error or result.get('error')
        ))
    
    def test_05_cache_clear_no_auth(self):
        """Test clearing cache without authentication"""
        result = self.request(
            "POST",
            "/api/v1/network/locations/clear-cache",
            auth=False,
            expected_status=401
        )
        
        self.add_result(TestResult(
            "Clear cache without auth",
            result['success'],
            result['response'],
            result.get('error')
        ))
    
    def test_06_cache_management(self):
        """Test location cache management"""
        # First get locations to ensure cache is populated
        initial_result = self.request(
            "GET",
            "/api/v1/network/locations",
            auth=True,
            auth_token=self.access_token
        )
        
        if not initial_result['success']:
            self.add_result(TestResult(
                "Cache test - initial locations fetch",
                False,
                initial_result['response'],
                "Failed to get initial locations"
            ))
            return
        
        # Clear the cache
        clear_result = self.request(
            "POST",
            "/api/v1/network/locations/clear-cache",
            auth=True,
            auth_token=self.access_token
        )
        
        success = clear_result['success']
        error = None
        
        if success:
            # Get locations again to verify cache was cleared
            second_result = self.request(
                "GET",
                "/api/v1/network/locations",
                auth=True,
                auth_token=self.access_token
            )
            
            if second_result['success']:
                data = second_result['response']
                if data.get('cached', True):  # Should be False after clearing
                    success = False
                    error = "Data still marked as cached after clearing"
            else:
                success = False
                error = "Failed to get locations after clearing cache"
        
        self.add_result(TestResult(
            "Location cache management",
            success,
            clear_result['response'],
            error or clear_result.get('error')
        ))
    
    def test_07_location_cache_duration(self):
        """Test location cache duration (1 hour)"""
        # Get initial locations
        first_result = self.request(
            "GET",
            "/api/v1/network/locations",
            auth=True,
            auth_token=self.access_token
        )
        
        if not first_result['success']:
            self.add_result(TestResult(
                "Location cache duration - initial fetch",
                False,
                first_result['response'],
                "Failed to get initial locations"
            ))
            return
            
        # Get locations again immediately - should be cached
        second_result = self.request(
            "GET",
            "/api/v1/network/locations",
            auth=True,
            auth_token=self.access_token
        )
        
        success = second_result['success']
        error = None
        
        if success:
            data = second_result['response']
            if not data.get('cached', False):
                success = False
                error = "Second request not using cache"
            elif not data.get('timestamp'):
                success = False
                error = "Missing timestamp in response"
            
            # Verify data matches between requests
            if success:
                first_data = first_result['response']
                if first_data.get('locations') != data.get('locations'):
                    success = False
                    error = "Cached data does not match original data"
                
        self.add_result(TestResult(
            "Location cache duration",
            success,
            second_result['response'],
            error or second_result.get('error')
        ))
    
    def test_08_connection_cache_duration(self):
        """Test connection cache duration (1 minute)"""
        # Get initial connections
        first_result = self.request(
            "GET",
            "/api/v1/network/connections",
            auth=True,
            auth_token=self.access_token
        )
        
        if not first_result['success']:
            self.add_result(TestResult(
                "Connection cache duration - initial fetch",
                False,
                first_result['response'],
                "Failed to get initial connections"
            ))
            return
            
        # Get connections again immediately - should be cached
        second_result = self.request(
            "GET",
            "/api/v1/network/connections",
            auth=True,
            auth_token=self.access_token
        )
        
        success = second_result['success']
        error = None
        
        if success:
            data = second_result['response']
            if not data.get('cached', False):
                success = False
                error = "Second request not using cache"
            elif not data.get('timestamp'):
                success = False
                error = "Missing timestamp in response"
            
            # Verify data matches between requests
            if success:
                first_data = first_result['response']
                if first_data.get('connections') != data.get('connections'):
                    success = False
                    error = "Cached data does not match original data"
                
        self.add_result(TestResult(
            "Connection cache duration",
            success,
            second_result['response'],
            error or second_result.get('error')
        ))
    
    def test_09_connection_cache_management(self):
        """Test connection cache management"""
        # First get connections to ensure cache is populated
        initial_result = self.request(
            "GET",
            "/api/v1/network/connections",
            auth=True,
            auth_token=self.access_token
        )
        
        if not initial_result['success']:
            self.add_result(TestResult(
                "Connection cache test - initial fetch",
                False,
                initial_result['response'],
                "Failed to get initial connections"
            ))
            return
        
        # Wait briefly to ensure cache is populated
        time.sleep(0.1)
        
        # Get connections again to verify caching
        second_result = self.request(
            "GET",
            "/api/v1/network/connections",
            auth=True,
            auth_token=self.access_token
        )
        
        success = second_result['success']
        error = None
        
        if success:
            data = second_result['response']
            if not data.get('cached', False):
                success = False
                error = "Second request not using cache"
            
            # Verify data matches between requests
            if success:
                first_data = initial_result['response']
                if first_data.get('connections') != data.get('connections'):
                    success = False
                    error = "Cached data does not match original data"
        
        self.add_result(TestResult(
            "Connection cache management",
            success,
            second_result['response'],
            error or second_result.get('error')
        ))
    
    def test_10_location_data_validation(self):
        """Test location data validation"""
        result = self.request(
            "GET",
            "/api/v1/network/locations",
            auth=True,
            auth_token=self.access_token
        )
        
        success = result['success']
        error = None
        
        if success and result['response'].get('locations'):
            locations = result['response']['locations']
            for location in locations:
                # Validate latitude range
                if not -90 <= location.get('latitude', 0) <= 90:
                    success = False
                    error = f"Invalid latitude value: {location.get('latitude')}"
                    break
                    
                # Validate longitude range
                if not -180 <= location.get('longitude', 0) <= 180:
                    success = False
                    error = f"Invalid longitude value: {location.get('longitude')}"
                    break
                    
                # Validate color format (hex)
                color = location.get('color', '')
                if not (color.startswith('#') and len(color) in [4, 7]):
                    success = False
                    error = f"Invalid color format: {color}"
                    break
                    
                # Validate site format
                if not location.get('site', '').strip():
                    success = False
                    error = "Empty site identifier"
                    break
        
        self.add_result(TestResult(
            "Location data validation",
            success,
            result['response'],
            error or result.get('error')
        ))
    
    def test_11_connection_data_validation(self):
        """Test connection data validation"""
        result = self.request(
            "GET",
            "/api/v1/network/connections",
            auth=True,
            auth_token=self.access_token
        )
        
        success = result['success']
        error = None
        
        if success and result['response'].get('connections'):
            connections = result['response']['connections']
            for connection in connections:
                # Validate packet count
                if connection.get('packet_count', 0) < 0:
                    success = False
                    error = f"Invalid packet count: {connection.get('packet_count')}"
                    break
                    
                # Validate unique subnets
                if connection.get('unique_subnets', 0) < 0:
                    success = False
                    error = f"Invalid unique subnets: {connection.get('unique_subnets')}"
                    break
                    
                # Validate timestamp order
                if connection.get('earliest_seen', 0) > connection.get('latest_seen', 0):
                    success = False
                    error = "earliest_seen is after latest_seen"
                    break
                    
                # Validate location references
                if not all([connection.get('src_location'), connection.get('dst_location')]):
                    success = False
                    error = "Missing source or destination location"
                    break
        
        self.add_result(TestResult(
            "Connection data validation",
            success,
            result['response'],
            error or result.get('error')
        ))
    
    def teardown(self):
        """Cleanup after network tests"""
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
  
