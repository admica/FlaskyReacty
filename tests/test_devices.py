"""
Device endpoint testing
Tests the device-related endpoints, ensuring proper sensor context
"""
from .base import BaseTest, TestResult
from typing import Dict, Optional

class DeviceTest(BaseTest):
    """Test suite for device-related endpoints"""
    
    def setup(self):
        """Setup required for device tests - login and get sensor info"""
        # First login to get access token
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
            raise Exception("Failed to login for device tests")
            
        self.access_token = result['response']['access_token']
        
        # Get list of sensors
        sensor_result = self.request(
            "GET",
            "/api/v1/sensors",
            auth=True,
            auth_token=self.access_token
        )
        
        if not sensor_result['success']:
            raise Exception("Failed to get sensor list")
            
        sensors = sensor_result['response'].get('sensors', [])
        if not sensors:
            raise Exception("No sensors available for testing")
        
        # Store first online sensor for testing
        self.test_sensor = next(
            (s['name'] for s in sensors if s['status'] == 'Online'),
            sensors[0]['name']  # Fallback to first sensor if none online
        )
        
        self.add_result(TestResult(
            "Setup - Login and get sensor",
            True,
            {"sensor": self.test_sensor}
        ))

    def test_01_get_devices(self):
        """Test getting devices for a sensor"""
        result = self.request(
            "GET",
            f"/api/v1/sensors/{self.test_sensor}/devices",
            auth=True,
            auth_token=self.access_token
        )
        
        success = result['success']
        error = None
        
        if success:
            data = result['response']
            # Validate response structure
            if not all(k in data for k in ['devices', 'count', 'sensor']):
                success = False
                error = "Missing required fields in response"
            elif data['sensor'] != self.test_sensor:
                success = False
                error = f"Wrong sensor in response: {data['sensor']}"
            elif data['devices']:
                # Validate first device structure
                device = data['devices'][0]
                required_fields = {
                    'name': str,
                    'port': int,
                    'type': str,
                    'status': str,
                    'last_checked': str,
                    'runtime': int,
                    'workers': int,
                    'src_subnets': int,
                    'dst_subnets': int,
                    'uniq_subnets': int,
                    'avg_idle_time': (int, float),
                    'avg_work_time': (int, float),
                    'overflows': int,
                    'size': str,
                    'version': str,
                    'output_path': str,
                    'proc': str,
                    'stats_date': (str, type(None))
                }
                
                for field, field_type in required_fields.items():
                    if field not in device:
                        success = False
                        error = f"Missing field '{field}' in device"
                        break
                    if not isinstance(device[field], field_type):
                        success = False
                        error = f"Field '{field}' has wrong type"
                        break
        
        self.add_result(TestResult(
            f"Get devices for sensor {self.test_sensor}",
            success,
            result['response'],
            error or result.get('error')
        ))

    def test_02_get_devices_invalid_sensor(self):
        """Test getting devices for invalid sensor"""
        result = self.request(
            "GET",
            "/api/v1/sensors/invalid_sensor/devices",
            auth=True,
            auth_token=self.access_token,
            expected_status=404
        )
        
        self.add_result(TestResult(
            "Get devices for invalid sensor",
            result['success'],
            result['response'],
            result.get('error')
        ))

    def teardown(self):
        """Cleanup after device tests"""
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