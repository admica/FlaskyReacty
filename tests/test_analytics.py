"""
Analytics endpoint testing
Tests the analytics-related endpoints
"""
from .base import BaseTest, TestResult

class AnalyticsTest(BaseTest):
    """Test suite for analytics-related endpoints"""
    
    def setup(self):
        """Setup required for analytics tests - login to get access token"""
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
            raise Exception("Failed to login for analytics tests")
            
        self.access_token = result['response']['access_token']
        
        self.add_result(TestResult(
            "Setup - Login",
            True,
            {"status": "logged in"}
        ))

    def test_01_get_sensor_activity_default(self):
        """Test getting sensor activity data with default parameters"""
        result = self.request(
            "GET",
            "/api/v1/analytics/sensors/activity",
            auth=True,
            auth_token=self.access_token
        )
        
        success = result['success']
        error = None
        
        if success:
            data = result['response']
            # Validate response structure
            required_fields = {
                'timeframe': dict,
                'query': dict,
                'summary': dict,
                'sensors': dict,
                'locations': list
            }
            
            for field, field_type in required_fields.items():
                if field not in data:
                    success = False
                    error = f"Missing required field: {field}"
                    break
                if not isinstance(data[field], field_type):
                    success = False
                    error = f"Field {field} has wrong type"
                    break
            
            if success:
                # Validate timeframe structure
                timeframe = data['timeframe']
                if not all(k in timeframe for k in ['start', 'end', 'hours']):
                    success = False
                    error = "Invalid timeframe structure"
                
                # Validate summary structure
                summary = data['summary']
                if not all(k in summary for k in ['total_packets', 'active_sensors', 'total_locations']):
                    success = False
                    error = "Invalid summary structure"
                
                # If we have sensors, validate first sensor structure
                if data['sensors']:
                    first_sensor = next(iter(data['sensors'].values()))
                    required_sensor_fields = {
                        'location': str,
                        'total_packets': int,
                        'active_source_devices': int,
                        'active_dest_devices': int,
                        'devices': list
                    }
                    
                    for field, field_type in required_sensor_fields.items():
                        if field not in first_sensor:
                            success = False
                            error = f"Missing sensor field: {field}"
                            break
                        if not isinstance(first_sensor[field], field_type):
                            success = False
                            error = f"Sensor field {field} has wrong type"
                            break
        
        self.add_result(TestResult(
            "Get sensor activity (default params)",
            success,
            result['response'],
            error or result.get('error')
        ))

    def test_02_get_sensor_activity_with_params(self):
        """Test getting sensor activity data with custom parameters"""
        result = self.request(
            "GET",
            "/api/v1/analytics/sensors/activity?hours=24&min_packets=5000",
            auth=True,
            auth_token=self.access_token
        )
        
        success = result['success']
        error = None
        
        if success:
            data = result['response']
            # Verify custom parameters were applied
            if data['timeframe']['hours'] != 24:
                success = False
                error = "Custom hours parameter not applied"
            elif data['query']['min_packets'] != 5000:
                success = False
                error = "Custom min_packets parameter not applied"
        
        self.add_result(TestResult(
            "Get sensor activity (custom params)",
            success,
            result['response'],
            error or result.get('error')
        ))

    def test_03_get_sensor_activity_invalid_params(self):
        """Test getting sensor activity data with invalid parameters"""
        # Test with hours > max allowed (168)
        result = self.request(
            "GET",
            "/api/v1/analytics/sensors/activity?hours=500",
            auth=True,
            auth_token=self.access_token
        )
        
        # Should still succeed but with capped hours
        success = result['success']
        error = None
        
        if success:
            data = result['response']
            if data['timeframe']['hours'] > 168:
                success = False
                error = "Hours parameter not capped at maximum"
        
        self.add_result(TestResult(
            "Get sensor activity (invalid hours)",
            success,
            result['response'],
            error or result.get('error')
        ))

    def teardown(self):
        """Cleanup after analytics tests"""
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