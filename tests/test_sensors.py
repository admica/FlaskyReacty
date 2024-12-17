"""
Sensor tests for PCAP Server.
Tests sensor listing and status functionality.
"""
from .base import BaseTest, TestResult

class SensorTest(BaseTest):
    """Test suite for sensor endpoints"""
    
    def setup(self):
        """Setup required for sensor tests - login first"""
        result = self.request(
            "POST",
            "/api/v1/login",
            data={
                "username": self.auth_username,
                "password": self.auth_password
            },
            auth=False
        )
        
        if result['success']:
            self.access_token = result['response']['access_token']
        else:
            raise Exception("Failed to login for sensor tests")
    
    def test_01_list_sensors(self):
        """Test getting list of all sensors"""
        response = self.request(
            "GET",
            "/api/v1/sensors",
            auth=True,
            auth_token=self.access_token
        )
        
        # Store sensor data for subsequent tests
        if response['success']:
            self.sensors = response['response']['sensors']
        
        self.add_result(TestResult(
            "List all sensors",
            response['success'],
            response['response'],
            response.get('error')
        ))
    
    def test_02_get_sensor_status(self):
        """Test getting status of a specific sensor"""
        if not hasattr(self, 'sensors'):
            self.add_result(TestResult(
                "Get sensor status",
                False,
                None,
                "No sensor list available (previous test failed)"
            ))
            return
            
        # Get first online sensor
        online_sensor = next(
            (s for s in self.sensors if s['status'] == 'Online'),
            None
        )
        
        if not online_sensor:
            self.add_result(TestResult(
                "Get sensor status",
                False,
                None,
                "No online sensors found"
            ))
            return
            
        response = self.request(
            "GET",
            f"/api/v1/sensors/{online_sensor['name']}/status",
            auth=True,
            auth_token=self.access_token
        )
        
        self.add_result(TestResult(
            f"Get status for sensor {online_sensor['name']}",
            response['success'],
            response['response'],
            response.get('error')
        ))
    
    def test_03_get_sensor_devices(self):
        """Test getting devices for a specific sensor"""
        if not hasattr(self, 'sensors'):
            self.add_result(TestResult(
                "Get sensor devices",
                False,
                None,
                "No sensor list available (previous test failed)"
            ))
            return
            
        # Get first online sensor
        online_sensor = next(
            (s for s in self.sensors if s['status'] == 'Online'),
            None
        )
        
        if not online_sensor:
            self.add_result(TestResult(
                "Get sensor devices",
                False,
                None,
                "No online sensors found"
            ))
            return
            
        response = self.request(
            "GET",
            f"/api/v1/sensors/{online_sensor['name']}/devices",
            auth=True,
            auth_token=self.access_token
        )
        
        self.add_result(TestResult(
            f"Get devices for sensor {online_sensor['name']}",
            response['success'],
            response['response'],
            response.get('error')
        ))
    
    def teardown(self):
        """Cleanup after sensor tests - logout"""
        if hasattr(self, 'access_token'):
            self.request(
                "POST",
                "/api/v1/logout",
                auth=True,
                auth_token=self.access_token
            ) 