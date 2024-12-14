#!/opt/pcapserver/venv_linux/bin/python3
"""
PCAP Server API Testing Framework
Provides structured testing of the PCAP Server REST API endpoints.

Usage: ./test_api.py [base_url]
Example: ./test_api.py https://localhost:3000
"""
import requests
import json
from datetime import datetime, timedelta, timezone
import sys
import os
import time
import configparser
from typing import Dict, Any, Optional, List, Tuple
from urllib3.exceptions import InsecureRequestWarning
from rich.console import Console
from rich.table import Table
from rich.traceback import install as install_rich_traceback

# Disable SSL warnings for testing with self-signed certs
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Initialize rich console and traceback
install_rich_traceback(show_locals=True)
console = Console()

# Override print to use rich console
print = console.print

# Constants
DEFAULT_BASE_URL = "https://localhost:3000"

class TestResult:
    """Represents the result of a single test"""
    def __init__(self, name: str, success: bool, response: Optional[Dict] = None, error: Optional[str] = None):
        self.name = name
        self.success = success
        self.response = response
        self.error = error
        self.timestamp = datetime.now(timezone.utc)

    def __str__(self) -> str:
        status = "Success" if self.success else "Failed"
        return f"{self.name}: {status}"

class TestSuite:
    """Base class for test suites"""
    def __init__(self, name: str):
        self.name = name
        self.results: List[TestResult] = []

    def add_result(self, result: TestResult) -> None:
        """Add a test result to the suite"""
        self.results.append(result)

    def print_results(self) -> None:
        """Print results for this test suite"""
        print(f"\n[bold]{self.name} Results:[/bold]")
        
        success_count = len([r for r in self.results if r.success])
        total_count = len(self.results)
        
        if total_count == 0:
            print("[yellow]No tests were executed[/yellow]")
            return

        table = Table(show_header=True, header_style="bold")
        table.add_column("Test Name")
        table.add_column("Result")
        table.add_column("Details", overflow="fold")

        for result in self.results:
            status = "[green]Success[/green]" if result.success else "[red]Failed[/red]"
            details = ""
            if result.error:
                details = f"[red]{result.error}[/red]"
            elif result.response:
                try:
                    details = json.dumps(result.response, indent=2)
                except:
                    details = str(result.response)

            table.add_row(
                result.name,
                status,
                details
            )

        print(table)
        print(f"\nSuccess Rate: {(success_count/total_count)*100:.1f}% ({success_count}/{total_count})")

class AuthTestSuite(TestSuite):
    """Test suite for authentication endpoints"""
    def __init__(self, api):
        super().__init__("Authentication Tests")
        self.api = api

    def run(self) -> None:
        """Run all authentication tests"""
        print("\n[bold]Running Authentication Tests[/bold]")

        # Test 1: Initial login
        print("Running: Initial Login")
        result = self.api.login()
        self.add_result(TestResult(
            "Initial Login",
            result.get('success', False),
            result.get('response'),
            result.get('error')
        ))

        if not result.get('success'):
            print("[red]Login failed - skipping remaining auth tests[/red]")
            return

        # Test 2: Token refresh
        time.sleep(1)  # Small delay between tests
        print("Running: Token Refresh")
        result = self.api.refresh_token()
        self.add_result(TestResult(
            "Token Refresh",
            result.get('success', False),
            result.get('response'),
            result.get('error')
        ))

        # Test 3: Logout
        time.sleep(1)
        print("Running: Logout")
        result = self.api.logout()
        self.add_result(TestResult(
            "Logout",
            result.get('success', False),
            result.get('response'),
            result.get('error')
        ))

        # Test 4: Verify logged out token is invalid
        time.sleep(1)
        print("Running: Verify Token Invalid")
        result = self.api.verify_token_invalid()
        self.add_result(TestResult(
            "Verify Token Invalid",
            result.get('success', False),
            result.get('response'),
            result.get('error')
        ))

        # Test 5: Re-login after logout
        time.sleep(1)
        print("Running: Re-login After Logout")
        result = self.api.login()
        self.add_result(TestResult(
            "Re-login After Logout",
            result.get('success', False),
            result.get('response'),
            result.get('error')
        ))

class PCAPServerAPI:
    """Main API testing class"""
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.access_token = None
        self.refresh_token_str = None
        self.session = requests.Session()
        self.session.verify = False  # Allow self-signed certs

        # Load config
        self.config = configparser.ConfigParser()
        config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
        self.config.read(config_path)

        # Get test user credentials
        self.test_user = self.config.get('TEST_USER', 'username')
        self.test_password = self.config.get('TEST_USER', 'password')

    def request(self, method: str, endpoint: str, data: Dict = None,
                expected_status: int = 200, auth: bool = True) -> Dict:
        """Make an API request"""
        url = f"{self.base_url}{endpoint}"
        headers = {'Content-Type': 'application/json'}

        if auth:
            if endpoint == '/api/v1/refresh':
                if not self.refresh_token_str:
                    return {'success': False, 'error': 'No refresh token available'}
                headers['Authorization'] = f'Bearer {self.refresh_token_str}'
            else:
                if not self.access_token:
                    return {'success': False, 'error': 'No access token available'}
                headers['Authorization'] = f'Bearer {self.access_token}'

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

    def login(self) -> Dict:
        """Login with test credentials"""
        result = self.request(
            "POST",
            "/api/v1/login",
            data={
                "username": self.test_user,
                "password": self.test_password
            },
            auth=False
        )

        if result['success']:
            self.access_token = result['response']['access_token']
            self.refresh_token_str = result['response']['refresh_token']

        return result

    def refresh_token(self) -> Dict:
        """Refresh the access token"""
        result = self.request(
            "POST",
            "/api/v1/refresh",
            data={}
        )

        if result['success']:
            self.access_token = result['response']['access_token']

        return result

    def logout(self) -> Dict:
        """Logout and invalidate tokens"""
        return self.request(
            "POST",
            "/api/v1/logout",
            data={}
        )

    def verify_token_invalid(self) -> Dict:
        """Verify that the token has been invalidated after logout"""
        result = self.request(
            "GET",
            "/api/v1/sensors"  # Use sensors endpoint as a test
        )
        # Success here means we got a 401 (unauthorized)
        return {
            'success': result['status_code'] == 401,
            'response': result['response'],
            'error': None if result['status_code'] == 401 else 'Token still valid after logout'
        }

def main():
    """Main test runner"""
    # Get base URL from command line or use default
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    print(f"Testing API at {base_url}")

    try:
        # Initialize API
        api = PCAPServerAPI(base_url)

        # Run test suites
        auth_suite = AuthTestSuite(api)
        auth_suite.run()
        auth_suite.print_results()

    except KeyboardInterrupt:
        print("\n[yellow]Tests interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        print("\n[red]Test execution failed![/red]")
        print(f"[red]Error: {str(e)}[/red]")
        print("[red]Traceback:[/red]")
        import traceback
        print(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main() 