"""
Base test functionality for PCAP Server tests.
"""
import requests
import configparser
import os
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from urllib3.exceptions import InsecureRequestWarning

# Disable SSL warnings for testing with self-signed certs
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

@dataclass
class TestResult:
    """Represents the result of a single test"""
    name: str
    success: bool
    response: Optional[Dict] = None
    error: Optional[str] = None
    timestamp: datetime = datetime.now(timezone.utc)

    def __str__(self) -> str:
        status = "Success" if self.success else "Failed"
        return f"{self.name}: {status}"

class BaseTest:
    """Base class providing common test functionality"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.results = []
        self.session = requests.Session()
        self.session.verify = False  # Allow self-signed certs
        
        # Load config
        self.config = configparser.ConfigParser()
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
        self.config.read(config_path)
        
        # Get local user credentials
        local_users = self.config.items('LOCAL_USERS')
        for _, user_json in local_users:
            try:
                user_data = json.loads(user_json)
                if user_data.get('role') == 'user':
                    self.auth_username = user_data.get('username')
                    self.auth_password = user_data.get('password')
                    break
            except json.JSONDecodeError:
                continue
        
        if not hasattr(self, 'auth_username') or not hasattr(self, 'auth_password'):
            raise Exception("No local user found in config")
    
    def add_result(self, result: TestResult) -> None:
        """Add a test result"""
        self.results.append(result)
    
    def request(self, method: str, endpoint: str, data: Dict = None,
                expected_status: int = 200, auth: bool = True,
                auth_token: Optional[str] = None) -> Dict[str, Any]:
        """Make an API request"""
        url = f"{self.base_url}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if auth and auth_token:
            headers['Authorization'] = f'Bearer {auth_token}'
        
        try:
            response = self.session.request(
                method,
                url,
                headers=headers,
                json=data,
                timeout=10
            )
            
            result = {
                'success': response.status_code == expected_status,
                'status_code': response.status_code,
                'response': response.json() if response.text else None
            }
            
            if not result['success']:
                result['error'] = f"Expected status {expected_status}, got {response.status_code}"
            
            return result
        
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e)
            } 