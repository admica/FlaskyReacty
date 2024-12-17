"""
Health check endpoint testing
Tests the health and version endpoints
"""
from .base import BaseTest, TestResult

class HealthTest(BaseTest):
    """Test health check endpoints"""
    
    def test_01_health_check(self):
        """Test basic health check endpoint"""
        result = self.request(
            "GET",
            "/api/v1/health",
            auth=False  # Health check doesn't require auth
        )
        
        success = result['success']
        error = None
        
        if success:
            data = result['response']
            # Validate response structure
            if not isinstance(data, dict):
                success = False
                error = "Response is not a dictionary"
            elif not all(key in data for key in ['status', 'timestamp', 'components']):
                success = False
                error = "Missing required fields in response"
            elif not isinstance(data['components'], dict):
                success = False
                error = "Components field is not a dictionary"
            elif not all(key in data['components'] for key in ['database', 'redis']):
                success = False
                error = "Missing component status fields"
            elif data['status'] != 'healthy':
                success = False
                error = f"Unhealthy status: {data.get('error', 'No error details')}"
        
        self.add_result(TestResult(
            "Health check endpoint",
            success,
            result['response'],
            error or result.get('error')
        ))
    
    def test_02_version_info(self):
        """Test version information endpoint"""
        result = self.request(
            "GET",
            "/api/v1/version",
            auth=False  # Version check doesn't require auth
        )
        
        success = result['success']
        error = None
        
        if success:
            data = result['response']
            # Validate response structure
            if not isinstance(data, dict):
                success = False
                error = "Response is not a dictionary"
            elif not all(key in data for key in ['version', 'build_date']):
                success = False
                error = "Missing version information fields"
            elif not isinstance(data['version'], str):
                success = False
                error = "Version is not a string"
            elif not isinstance(data['build_date'], str):
                success = False
                error = "Build date is not a string"
        
        self.add_result(TestResult(
            "Version information endpoint",
            success,
            result['response'],
            error or result.get('error')
        ))
    
    def test_03_redis_dependency(self):
        """Test that Redis is required and operational"""
        result = self.request(
            "GET",
            "/api/v1/health",
            auth=False
        )
        
        success = result['success']
        error = None
        
        if success:
            data = result['response']
            if not data['components'].get('redis') == 'operational':
                success = False
                error = "Redis is not operational"
        
        self.add_result(TestResult(
            "Redis health check",
            success,
            result['response'],
            error or result.get('error')
        )) 