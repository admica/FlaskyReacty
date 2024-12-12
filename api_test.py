#!/opt/pcapserver/venv_linux/bin/python3
"""
PCAP Server API Integration testing
PATH: ./api_test.py

Tests:
1. Authentication with test user
2. JWT token handling
3. Sensor endpoints
4. Job submission and management
5. Analysis functionality
6. File download URLs
7. Admin endpoints
8. Health checks
9. Log endpoints

Usage: ./api_test.py [base_url]
Example: ./api_test.py https://localhost:3000
"""
import requests
import json
from datetime import datetime, timedelta, timezone
import sys
from rich import print
from rich.console import Console
from rich.table import Table
from typing import Dict, Any, Optional
from urllib3.exceptions import InsecureRequestWarning
import configparser
import os
import time
import psycopg2
from urllib.parse import quote

# Disable SSL warnings for testing with self-signed certs
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

console = Console()

# Default to HTTPS
DEFAULT_BASE_URL = "https://localhost:3000"

class ApiTester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.access_token = None
        self.refresh_token = None
        self.results = []

        # Load config
        self.config = configparser.ConfigParser()
        config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
        self.config.read(config_path)

        # Get test user credentials
        self.test_user = self.config.get('TEST_USER', 'username')
        self.test_password = self.config.get('TEST_USER', 'password')

        # Initialize first_sensor as None - will be set in test_sensors()
        self.first_sensor = None

    def run_test(self, name: str, method: str, endpoint: str, data: Dict = None,
                expected_status: int = 200, auth: bool = True, quiet: bool = False) -> Optional[Dict]:
        """Run a single test"""
        try:
            url = f"{self.base_url}{endpoint}"
            headers = {'Content-Type': 'application/json'}

            if auth:
                if endpoint == '/api/v1/refresh':
                    if not self.refresh_token:
                        console.print("[red]No refresh token available[/red]")
                        return None
                    headers['Authorization'] = f'Bearer {self.refresh_token}'
                else:
                    if not self.access_token:
                        console.print("[red]No access token available[/red]")
                        return None
                    headers['Authorization'] = f'Bearer {self.access_token}'

            if not quiet:
                console.print(f"\nRequest to: {url}")
                console.print(f"Headers: {headers}")
                if data:
                    console.print(f"Data: {json.dumps(data)}")

            try:
                # Use verify=False to accept self-signed certificates
                response = requests.request(method, url, headers=headers, json=data, verify=False, timeout=10)

                if not quiet:
                    console.print(f"Response Status: {response.status_code}")
                    console.print(f"Raw Response Text: {response.text}")

                result = {
                    'name': name,
                    'method': method,
                    'endpoint': endpoint,
                    'status': response.status_code,
                    'expected': expected_status,
                    'response': response.json() if response.text else None,
                    'success': response.status_code == expected_status
                }
                self.results.append(result)

                if not quiet:
                    if result['success']:
                        console.print(f"[green]{name}: Success[/green]")
                    else:
                        console.print(f"[red]{name}: Failed (Status: {response.status_code})[/red]")
                        if result['response']:
                            console.print(f"Response: {json.dumps(result['response'], indent=2)}")

                return result

            except requests.exceptions.SSLError as e:
                console.print(f"[red]SSL Error: {str(e)}[/red]")
                return None
            except requests.exceptions.ConnectionError as e:
                console.print(f"[red]Connection Error - Is the server running? {str(e)}[/red]")
                return None
            except requests.exceptions.Timeout as e:
                console.print(f"[red]Timeout Error - Server took too long to respond: {str(e)}[/red]")
                return None
            except requests.exceptions.RequestException as e:
                console.print(f"[red]Request Error: {str(e)}[/red]")
                return None

        except Exception as e:
            if not quiet:
                console.print(f"[red]Error in {name}: {str(e)}[/red]")
            return None

    def authenticate(self) -> bool:
        """Authenticate with test credentials"""
        console.print("\n[bold]Testing Authentication[/bold]")

        result = self.run_test(
            "Login with test user",
            "POST",
            "/api/v1/login",
            data={
                "username": self.test_user,
                "password": self.test_password
            },
            auth=False
        )

        if result and result['success']:
            self.access_token = result['response']['access_token']
            self.refresh_token = result['response']['refresh_token']
            return True
        return False

    def test_refresh_token(self):
        """Test refresh token functionality"""
        console.print("\n[bold]Testing Token Refresh[/bold]")

        result = self.run_test("Refresh access token", "POST", "/api/v1/refresh", auth=True, data={})

        if result and result['success']:
            self.access_token = result['response']['access_token']
            return True
        return False

    def test_sensors(self):
        """Test getting all sensors"""
        console.print("\n[bold]Testing All Sensors[/bold]")

        result = self.run_test("Get all sensors list", "GET", "/api/v1/sensors")

        # Store first sensor name if available
        if result and result['success'] and result['response']:
            sensors = result['response'].get('sensors', [])
            if sensors:
                # Find first online sensor
                for sensor in sensors:
                    if sensor.get('status') == 'Online':
                        self.first_sensor = sensor['name']
                        console.print(f"[blue]Found active sensor for testing: {self.first_sensor}[/blue]")
                        break

                if not self.first_sensor:
                    self.first_sensor = sensors[0]['name']
                    console.print(f"[yellow]No online sensors found, using first available: {self.first_sensor}[/yellow]")
            else:
                console.print("[red]No sensors found in response[/red]")
        else:
            console.print("[yellow]No sensors available for testing[/yellow]")

    def test_sensor(self):
        """Test getting specific sensor status"""
        console.print("\n[bold]Testing Single Sensor Status[/bold]")

        if not hasattr(self, 'first_sensor') or not self.first_sensor:
            console.print("[yellow]Skipping sensor status test - no sensor available[/yellow]")
            return

        self.run_test(f"Get status for sensor '{self.first_sensor}'", "GET", f"/api/v1/sensors/{self.first_sensor}/status")

    def test_subnet_location_counts(self):
        """Test subnet location mapping counts"""
        console.print("\n[bold]Testing Subnet Location Mapping Counts[/bold]")

        # Test 1: Get all counts
        result = self.run_test("Get all subnet location counts", "GET", "/api/v1/subnet-location-counts")

        if result and result['success'] and result['response']:
            counts = result['response']
            if len(counts) > 0:
                # Get the first mapping for subsequent tests
                first_mapping = counts[0]
                src_loc = first_mapping['src_location']
                dst_loc = first_mapping['dst_location']

                # Test 2: Get counts for specific source location
                self.run_test(
                    f"Get counts for source location '{src_loc}'",
                    "GET",
                    f"/api/v1/subnet-location-counts?src={src_loc}"
                )

                # Test 3: Get count for specific source->destination pair
                self.run_test(
                    f"Get count for {src_loc}->{dst_loc} pair",
                    "GET",
                    f"/api/v1/subnet-location-counts?src={src_loc}&dst={dst_loc}"
                )
            else:
                console.print("[yellow]No subnet location mappings found for testing[/yellow]")

    def test_get_jobs(self):
        """Test getting jobs with filters"""
        console.print("\n[bold]Testing Get Jobs[/bold]")

        job_filter = {
            "start_time": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat()
        }

        result = self.run_test("Get recent jobs", "POST", "/api/v1/jobs", data=job_filter)

        if result and result['success']:
            jobs = result['response']
            console.print(f"[green]Successfully retrieved {len(jobs)} jobs[/green]")

            # Validate job structure if any jobs returned
            if jobs:
                required_fields = ['id', 'username', 'sensor', 'start_time', 'end_time', 'status']
                for job in jobs:
                    missing_fields = [field for field in required_fields if field not in job]
                    if missing_fields:
                        console.print(f"[red]Error: Job missing required fields: {missing_fields}[/red]")
                        return False
        return result

    def test_submit_job(self):
        """Test job submission with various time combinations"""
        console.print("\n[bold]Testing Job Submission[/bold]")

        if not hasattr(self, 'first_sensor') or not self.first_sensor:
            console.print("[yellow]Skipping job submission test - no sensor available[/yellow]")
            return

        # Test case 1: Submit with event_time only
        event_time = datetime.now(timezone.utc)
        job_data = {
            "location": self.first_sensor,
            "src_ip": "192.168.1.1",
            "description": "API Test Job - Event Time Only",
            "event_time": event_time.isoformat(),
            "tz": "+00:00"
        }
        result1 = self.run_test("Submit job with event_time only", "POST", "/api/v1/submit",
                               data=job_data, expected_status=201)

        # Test case 2: Submit with event_time and start_time
        start_time = event_time - timedelta(minutes=5)
        job_data = {
            "location": self.first_sensor,
            "src_ip": "192.168.1.1",
            "description": "API Test Job - Event Time + Start Time",
            "event_time": event_time.isoformat(),
            "start_time": start_time.isoformat(),
            "tz": "+00:00"
        }
        result2 = self.run_test("Submit job with event_time and start_time", "POST",
                               "/api/v1/submit", data=job_data, expected_status=201)

        # Test case 3: Submit with event_time and end_time
        end_time = event_time + timedelta(minutes=10)
        job_data = {
            "location": self.first_sensor,
            "src_ip": "192.168.1.1",
            "description": "API Test Job - Event Time + End Time",
            "event_time": event_time.isoformat(),
            "end_time": end_time.isoformat(),
            "tz": "+00:00"
        }
        result3 = self.run_test("Submit job with event_time and end_time", "POST",
                               "/api/v1/submit", data=job_data, expected_status=201)

        # Test case 4: Submit with start_time and end_time
        job_data = {
            "location": self.first_sensor,
            "src_ip": "192.168.1.1",
            "description": "API Test Job - Start Time + End Time",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "tz": "+00:00"
        }
        result4 = self.run_test("Submit job with start_time and end_time", "POST",
                               "/api/v1/submit", data=job_data, expected_status=201)

        # Store the last job ID from any successful submission
        for result in [result4, result3, result2, result1]:
            if result and result['success']:
                self.last_job_id = result['response'].get('job_id')
                if self.last_job_id:
                    console.print(f"[green]Successfully submitted job with ID: {self.last_job_id}[/green]")
                    break
                else:
                    console.print("[red]Error: No job ID in response[/red]")

        return result4  # Return the last result for consistency

    def test_get_job(self):
        """Test getting a specific job's details"""
        console.print("\n[bold]Testing Get Job Details[/bold]")

        if not hasattr(self, 'last_job_id'):
            console.print("[yellow]Skipping job details test - no job ID available[/yellow]")
            return

        result = self.run_test(f"Get job details for ID {self.last_job_id}", "GET", f"/api/v1/jobs/{self.last_job_id}")
        return result

    def test_cancel_job(self):
        """Test job cancellation"""
        console.print("\n[bold]Testing Job Cancellation[/bold]")

        if not hasattr(self, 'last_job_id'):
            console.print("[yellow]Skipping job cancellation test - no job ID available[/yellow]")
            return

        cancel_result = self.run_test(f"Cancel job {self.last_job_id}", "POST", f"/api/v1/jobs/{self.last_job_id}/cancel")

        if cancel_result and cancel_result['success']:
            console.print(f"[green]Successfully cancelled job {self.last_job_id}[/green]")
            time.sleep(1)  # Wait for status update

            try:
                status_result = self.run_test(f"Get status for job {self.last_job_id}", "GET", f"/api/v1/jobs/{self.last_job_id}")
                if status_result and status_result['success'] and status_result['response']:
                    console.print("[blue]Job status after cancellation:[/blue]")
                    console.print(json.dumps(status_result['response'], indent=2))
            except Exception as e:
                console.print("[yellow]Error retrieving job status (job may have been deleted)[/yellow]")
        else:
            console.print(f"[red]Failed to cancel job {self.last_job_id}[/red]")

        return cancel_result

    def test_delete_job(self):
        """Test job deletion"""
        console.print("\n[bold]Testing Job Deletion[/bold]")

        if not hasattr(self, 'last_job_id'):
            console.print("[yellow]Skipping job deletion test - no job ID available[/yellow]")
            return

        delete_result = self.run_test(f"Delete job {self.last_job_id}", "DELETE", f"/api/v1/jobs/{self.last_job_id}")

        if delete_result and delete_result['success']:
            console.print(f"[green]Successfully deleted job {self.last_job_id}[/green]")
        else:
            console.print(f"[red]Failed to delete job {self.last_job_id}[/red]")

        return delete_result

    def test_storage_status(self):
        """Test storage status endpoint"""
        console.print("\n[bold]Testing Storage Status[/bold]")

        result = self.run_test("Get storage status", "GET", "/api/v1/storage")

        if result and result['success']:
            storage_data = result['response'].get('storage', {})
            if not storage_data:
                console.print("[red]Error: No storage data in response[/red]")
                return False

            for path_name, path_data in storage_data.items():
                console.print(f"\n[blue]Checking storage path: {path_name}[/blue]")
                required_fields = ['path', 'total_bytes', 'used_bytes', 'free_bytes', 'percent_used', 'human_readable']
                missing_fields = [field for field in required_fields if field not in path_data]

                if missing_fields:
                    console.print(f"[red]Missing required fields: {missing_fields}[/red]")
                    continue

                human_readable = path_data['human_readable']
                if not all(k in human_readable for k in ['total', 'used', 'free']):
                    console.print("[red]Missing human readable values[/red]")
                    continue

                console.print(f"Total: {human_readable['total']}")
                console.print(f"Used: {human_readable['used']}")
                console.print(f"Free: {human_readable['free']}")
                console.print(f"Usage: {path_data['percent_used']}%")

            return True
        return False

    def test_admin_endpoints(self):
        """Test admin-only endpoints"""
        console.print("\n[bold]Testing Admin Endpoints[/bold]")

        result = self.run_test("Get system status", "GET", "/api/v1/admin/system/status")
        if not result:
            return False

        result = self.run_test("Get cache state", "GET", "/api/v1/admin/system/cache")
        if not result:
            return False

        return True

    def test_health_endpoints(self):
        """Test health and version endpoints"""
        console.print("\n[bold]Testing Health Endpoints[/bold]")
        self.run_test("Health check", "GET", "/api/v1/health", auth=False)
        self.run_test("Version check", "GET", "/api/v1/version", auth=False)

    def test_ip_search(self):
        """Test IP search functionality using real IPs from the database."""
        if not self.access_token:
            console.print("[red]No access token available. Please login first.[/red]")
            return False

        if not hasattr(self, 'first_sensor') or not self.first_sensor:
            console.print("[red]No sensor available for testing. Run test_sensors() first.[/red]")
            return False

        # Get database credentials from config
        db_config = {
            'dbname': self.config.get('DB', 'database'),
            'user': self.config.get('DB', 'username'),
            'password': self.config.get('DB', 'password'),
            'host': self.config.get('DB', 'hostname'),
            'port': self.config.get('DB', 'port')
        }

        try:
            with psycopg2.connect(**db_config) as conn:
                with conn.cursor() as cur:
                    # Get sensor location from sensors table
                    cur.execute("""
                        SELECT name, location
                        FROM sensors
                        WHERE name = %s
                    """, (self.first_sensor,))
                    sensor_result = cur.fetchone()
                    if not sensor_result:
                        console.print(f"[red]Sensor {self.first_sensor} not found in database[/red]")
                        return False

                    sensor_name, location = sensor_result
                    console.print(f"[blue]Using sensor {sensor_name} in location {location}[/blue]")

                    # Find a real source subnet from the sensor's location
                    cur.execute(f"""
                        SELECT subnet, sensor, device
                        FROM loc_src_{location}
                        WHERE count > 0 AND sensor = %s
                        ORDER BY last_seen DESC
                        LIMIT 1
                    """, (sensor_name,))
                    src_result = cur.fetchone()
                    if not src_result:
                        console.print(f"[yellow]Warning: No source subnets found for sensor {sensor_name}[/yellow]")
                        return False

                    src_subnet = src_result[0]
                    src_ip = src_subnet.split('/')[0][:-1] + "99"  # e.g. "1.2.3.99"
                    console.print(f"[blue]Using source IP {src_ip} from subnet {src_subnet}[/blue]")

                    # Find a real destination subnet from the sensor's location
                    cur.execute(f"""
                        SELECT subnet, sensor, device
                        FROM loc_dst_{location}
                        WHERE count > 0 AND sensor = %s
                        ORDER BY last_seen DESC
                        LIMIT 1
                    """, (sensor_name,))
                    dst_result = cur.fetchone()
                    if not dst_result:
                        console.print(f"[yellow]Warning: No destination subnets found for sensor {sensor_name}[/yellow]")
                        return False

                    dst_subnet = dst_result[0]
                    dst_ip = dst_subnet.split('/')[0][:-1] + "99"  # e.g. "192.168.1.99"
                    console.print(f"[blue]Using destination IP {dst_ip} from subnet {dst_subnet}[/blue]")

            # Test 1: Single source IP search
            console.print("\n[bold]Test 1: Single Source IP Search[/bold]")
            result = self.run_test(
                f"Search for source IP {src_ip}",
                "POST",
                "/api/v1/search/ip",
                data={'src_ip': src_ip}
            )
            if not result or not result['success']:
                return False

            # Test 2: Single destination IP search
            console.print("\n[bold]Test 2: Single Destination IP Search[/bold]")
            result = self.run_test(
                f"Search for destination IP {dst_ip}",
                "POST",
                "/api/v1/search/ip",
                data={'dst_ip': dst_ip}
            )
            if not result or not result['success']:
                return False

            # Test 3: Source-destination pair search
            console.print("\n[bold]Test 3: Source-Destination Pair Search[/bold]")
            result = self.run_test(
                f"Search for IP pair {src_ip}->{dst_ip}",
                "POST",
                "/api/v1/search/ip",
                data={
                    'src_ip': src_ip,
                    'dst_ip': dst_ip
                }
            )
            if not result or not result['success']:
                return False

            # Test 4: Search with timeframe
            current_time = int(time.time())
            console.print("\n[bold]Test 4: Search with Timeframe[/bold]")
            result = self.run_test(
                "Search with timeframe",
                "POST",
                "/api/v1/search/ip",
                data={
                    'src_ip': src_ip,
                    'start_time': current_time - 3600,  # Last hour
                    'end_time': current_time
                }
            )
            if not result or not result['success']:
                return False

            # Test 5: Invalid IP format
            console.print("\n[bold]Test 5: Invalid IP Format[/bold]")
            result = self.run_test(
                "Search with invalid IP",
                "POST",
                "/api/v1/search/ip",
                data={'src_ip': 'invalid.ip'},
                expected_status=400
            )
            if not result or not result['success']:
                return False

            # Test 6: Non-existent IP
            console.print("\n[bold]Test 6: Non-existent IP[/bold]")
            result = self.run_test(
                "Search for non-existent IP",
                "POST",
                "/api/v1/search/ip",
                data={'src_ip': '8.8.8.8'}
            )
            if not result or not result['success']:
                return False

            if result['response'].get('matches'):
                console.print("[red]Expected no matches for non-existent IP[/red]")
                return False

            return True

        except psycopg2.Error as e:
            console.print(f"[red]Database error: {str(e)}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Error in IP search test: {str(e)}[/red]")
            return False

    def test_analytics(self):
        """Test analytics endpoints"""
        console.print("\n[bold]Testing Analytics[/bold]")

        # Test valid request
        result = self.run_test(
            "Get sensor activity (1 hour)",
            "GET",
            "/api/v1/analytics/sensors/activity?hours=1&min_packets=1000"
        )
        if result and result['success']:
            # Validate response structure
            response = result['response']
            assert 'timeframe' in response, "Missing timeframe in response"
            assert 'query' in response, "Missing query in response"
            assert 'summary' in response, "Missing summary in response"
            assert 'sensors' in response, "Missing sensors in response"
            assert 'locations' in response, "Missing locations in response"

        # Test invalid hours parameter
        result = self.run_test(
            "Test invalid hours parameter",
            "GET",
            "/api/v1/analytics/sensors/activity?hours=invalid",
            expected_status=400
        )

        # Test invalid min_packets parameter
        result = self.run_test(
            "Test invalid min_packets parameter",
            "GET",
            "/api/v1/analytics/sensors/activity?min_packets=invalid",
            expected_status=400
        )

        # Test hours limit
        result = self.run_test(
            "Test hours limit (>168)",
            "GET",
            "/api/v1/analytics/sensors/activity?hours=169",
        )
        if result and result['success']:
            # Verify hours was capped at 168
            assert result['response']['timeframe']['hours'] <= 168, "Hours not capped at 168"

        # Test min_packets limit
        result = self.run_test(
            "Test min_packets limit (<1)",
            "GET",
            "/api/v1/analytics/sensors/activity?min_packets=0",
        )
        if result and result['success']:
            # Verify min_packets was set to at least 1
            assert result['response']['query']['min_packets'] >= 1, "Min packets not enforced to >= 1"

    def test_cache_state(self):
        """Test cache state endpoint"""
        console.print("\n[bold]Testing Cache State[/bold]")

        # Test cache state endpoint
        result = self.run_test(
            "Get cache state",
            "GET",
            "/api/v1/admin/cache/state"
        )
        if result and result['success']:
            # Validate response structure
            response = result['response']
            assert 'info' in response, "Missing info in response"
            assert 'keys' in response, "Missing keys in response"
            assert isinstance(response['keys'], dict), "Keys should be a dictionary"

    def test_rate_limiting(self):
        """Test rate limiting behavior"""
        console.print("\n[bold]Testing Rate Limiting[/bold]")

        # Make rapid requests to trigger rate limiting
        results = []
        for i in range(5):
            result = self.run_test(
                f"Rapid request {i+1}",
                "GET",
                "/api/v1/health",
                quiet=True
            )
            results.append(result)
            time.sleep(0.1)  # Small delay to not overwhelm server

        # At least one request should succeed
        assert any(r['success'] for r in results), "All requests failed"

        # Test rate limit reset after delay
        time.sleep(1)  # Wait for rate limit window
        result = self.run_test(
            "Request after rate limit window",
            "GET",
            "/api/v1/health"
        )
        assert result['success'], "Rate limit not reset after window"

    def test_subnet_mapping(self):
        """Test subnet mapping functionality"""
        console.print("\n[bold]Testing Subnet Mapping[/bold]")

        # Get test data from database
        try:
            db_config = {
                'dbname': self.config.get('DB', 'database'),
                'user': self.config.get('DB', 'username'),
                'password': self.config.get('DB', 'password'),
                'host': self.config.get('DB', 'hostname'),
                'port': self.config.get('DB', 'port')
            }

            with psycopg2.connect(**db_config) as conn:
                with conn.cursor() as cur:
                    # Get a real source subnet and location
                    cur.execute("""
                        SELECT DISTINCT s.subnet, s.sensor, s.device, sen.location
                        FROM loc_src_gsfc s
                        JOIN sensors sen ON sen.name = s.sensor
                        WHERE s.count > 0
                        LIMIT 1
                    """)
                    src_result = cur.fetchone()
                    if not src_result:
                        console.print("[yellow]Warning: No source subnets found in GSFC location[/yellow]")
                        return False

                    src_subnet, src_sensor, src_device, src_location = src_result

                    # Get a real destination subnet from the same sensor
                    cur.execute("""
                        SELECT DISTINCT s.subnet, s.sensor, s.device, sen.location
                        FROM loc_dst_gsfc s
                        JOIN sensors sen ON sen.name = s.sensor
                        WHERE s.sensor = %s AND s.device = %s AND s.count > 0
                        LIMIT 1
                    """, (src_sensor, src_device))
                    dst_result = cur.fetchone()
                    if not dst_result:
                        console.print("[yellow]Warning: No matching destination subnets found[/yellow]")
                        return False

                    dst_subnet, dst_sensor, dst_device, dst_location = dst_result

            # Test 1: Source subnet search (requires location)
            console.print("\n[bold]Test 1: Source Subnet Search[/bold]")
            result = self.run_test(
                "Query source subnet mapping",
                "GET",
                f"/api/v1/admin/subnet_mapping?src_subnet={src_subnet}&src_location={src_location}",
                expected_status=200
            )

            if not result or not result['success']:
                return False

            data = result['response']
            if not data.get('mappings'):
                console.print("[red]No mappings found in source search[/red]")
                return False

            # Verify source mapping fields
            mapping = data['mappings'][0]
            if not all(key in mapping for key in ['src_subnet', 'location', 'sensor', 'device']):
                console.print("[red]Missing required fields in source mapping response[/red]")
                return False

            # Test 2: Destination subnet search (requires location)
            console.print("\n[bold]Test 2: Destination Subnet Search[/bold]")
            result = self.run_test(
                "Query destination subnet mapping",
                "GET",
                f"/api/v1/admin/subnet_mapping?dst_subnet={dst_subnet}&dst_location={dst_location}",
                expected_status=200
            )

            if not result or not result['success']:
                return False

            data = result['response']
            if not data.get('mappings'):
                console.print("[red]No mappings found in destination search[/red]")
                return False

            # Test 3: Source-destination pair search (requires both locations)
            console.print("\n[bold]Test 3: Source-Destination Pair Search[/bold]")
            result = self.run_test(
                "Query subnet pair mapping",
                "GET",
                f"/api/v1/admin/subnet_mapping?src_subnet={src_subnet}&dst_subnet={dst_subnet}&src_location={src_location}&dst_location={dst_location}",
                expected_status=200
            )

            if not result or not result['success']:
                return False

            data = result['response']
            if not data.get('mappings'):
                console.print("[red]No mappings found in pair search[/red]")
                return False

            # Verify pair mapping has all required fields
            mapping = data['mappings'][0]
            if not all(key in mapping for key in ['src_subnet', 'dst_subnet', 'src_location', 'dst_location', 'sensor', 'device']):
                console.print("[red]Missing required fields in pair mapping response[/red]")
                return False

            # Test 4: Location-only summary
            console.print("\n[bold]Test 4: Location Summary[/bold]")
            result = self.run_test(
                "Query location summary",
                "GET",
                f"/api/v1/admin/subnet_mapping?src_location={src_location}&dst_location={dst_location}",
                expected_status=200
            )

            if not result or not result['success']:
                return False

            # Test 5: Error - Missing required location
            console.print("\n[bold]Test 5: Error - Missing Location[/bold]")
            result = self.run_test(
                "Test missing location",
                "GET",
                f"/api/v1/admin/subnet_mapping?src_subnet={src_subnet}",
                expected_status=400
            )

            if not result or not result['success']:
                return False

            # Test 6: Error - Invalid subnet format
            console.print("\n[bold]Test 6: Error - Invalid Subnet[/bold]")
            result = self.run_test(
                "Test invalid subnet format",
                "GET",
                f"/api/v1/admin/subnet_mapping?src_subnet=invalid&src_location={src_location}",
                expected_status=400
            )

            if not result or not result['success']:
                return False

            # Test 7: Error - Invalid location
            console.print("\n[bold]Test 7: Error - Invalid Location[/bold]")
            result = self.run_test(
                "Test invalid location",
                "GET",
                "/api/v1/admin/subnet_mapping?src_subnet=192.168.1.0/24&src_location=invalid",
                expected_status=400
            )

            return result and result['success']

        except psycopg2.Error as e:
            console.print(f"[red]Database error: {str(e)}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Error in subnet mapping test: {str(e)}[/red]")
            return False

    def test_token_invalidation(self):
        """Test that logged out tokens can't access protected endpoints"""
        console.print("\n[bold]Testing Token Invalidation[/bold]")

        # First login to get tokens
        result = self.run_test(
            "Login to get tokens",
            "POST",
            "/api/v1/login",
            data={
                "username": self.test_user,
                "password": self.test_password
            },
            auth=False
        )

        if not result or not result['success']:
            console.print("[red]Failed to login[/red]")
            return False

        # Store the access token
        access_token = result['response']['access_token']
        self.access_token = access_token  # Set it for the logout request

        # Now logout using the endpoint
        result = self.run_test(
            "Logout user",
            "POST",
            "/api/v1/logout"
        )

        if not result or not result['success']:
            console.print("[red]Failed to logout[/red]")
            return False

        # Try to use the same token to access a protected endpoint
        # Note: We're already using the same token since we didn't clear it
        result = self.run_test(
            "Try to access sensors with old token",
            "GET",
            "/api/v1/sensors",
            expected_status=401  # Should fail with unauthorized
        )
        self.access_token = None  # Clear the token after the test

        # The test passes if we got a 401 (token rejected)
        # It fails if we got a 200 (token still accepted)
        if result and result['status'] == 401:
            console.print("[green]Token invalidation test passed - old token was rejected[/green]")
            return True
        else:
            console.print("[red]Token invalidation test failed - old token was still accepted[/red]")
            return False

    def test_network_locations(self):
        """Test getting network locations"""
        console.print("\n[bold]Testing Network Locations[/bold]")

        # Test without auth first
        self.run_test(
            "Get locations without auth",
            "GET",
            "/api/v1/network/locations",
            auth=False,
            expected_status=401
        )

        # Test with auth
        result = self.run_test(
            "Get locations with auth",
            "GET",
            "/api/v1/network/locations"
        )

        if result and result['success']:
            locations = result['response'].get('locations', [])
            console.print(f"[green]Successfully retrieved {len(locations)} locations[/green]")

            # Validate location structure if any returned
            if locations:
                required_fields = ['site', 'name', 'latitude', 'longitude', 'description']
                for loc in locations:
                    missing_fields = [field for field in required_fields if field not in loc]
                    if missing_fields:
                        console.print(f"[red]Error: Location missing required fields: {missing_fields}[/red]")
                        return False
        return result

    def test_network_connections(self):
        """Test getting network connections"""
        console.print("\n[bold]Testing Network Connections[/bold]")

        # Test without auth first
        self.run_test(
            "Get connections without auth",
            "GET",
            "/api/v1/network/connections",
            auth=False,
            expected_status=401
        )

        # Test with auth
        result = self.run_test(
            "Get network connections",
            "GET",
            "/api/v1/network/connections"
        )

        if result and result['success']:
            connections = result['response'].get('connections', [])
            console.print(f"[green]Successfully retrieved {len(connections)} connections[/green]")

            # Validate connection structure if any returned
            if connections:
                required_fields = ['src_location', 'dst_location', 'packet_count', 'latest_seen', 'earliest_seen']
                for conn in connections:
                    missing_fields = [field for field in required_fields if field not in conn]
                    if missing_fields:
                        console.print(f"[red]Error: Connection missing required fields: {missing_fields}[/red]")
                        return False

        return result

    def test_logs(self):
        """Test getting system logs"""
        console.print("\n[bold]Testing System Logs[/bold]")

        # Test without auth first
        self.run_test(
            "Get logs without auth",
            "GET",
            "/api/v1/logs",
            auth=False,
            expected_status=401
        )

        # Test with auth
        result = self.run_test(
            "Get system logs",
            "GET",
            "/api/v1/logs"
        )

        if result and result['success']:
            files = result['response'].get('files', [])
            console.print(f"[green]Successfully retrieved {len(files)} log files[/green]")

            # Validate log file structure
            required_fields = ['name', 'size', 'modified']
            for file in files:
                missing_fields = [field for field in required_fields if field not in file]
                if missing_fields:
                    console.print(f"[red]Error: Log file missing required fields: {missing_fields}[/red]")
                    return False

                # Validate field types
                if not isinstance(file['name'], str):
                    console.print("[red]Error: Log file name must be a string[/red]")
                    return False
                if not isinstance(file['size'], int):
                    console.print("[red]Error: Log file size must be an integer[/red]")
                    return False
                try:
                    datetime.fromisoformat(file['modified'].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    console.print("[red]Error: Log file modified timestamp must be ISO format[/red]")
                    return False

            # Test content retrieval with network.log
            test_file = "network.log"
            console.print(f"[blue]Testing content endpoint with {test_file}[/blue]")

            # Test getting content
            content_result = self.run_test(
                f"Get content for {test_file}",
                "GET",
                f"/api/v1/logs/{test_file}/content"
            )

            if content_result and content_result['success']:
                content = content_result['response'].get('content', [])
                console.print(f"[green]Successfully retrieved {len(content)} lines from {test_file}[/green]")

                # Validate content structure
                if not isinstance(content, list):
                    console.print("[red]Error: Log content must be a list of strings[/red]")
                    return False

                # Validate content types
                if content and not all(isinstance(line, str) for line in content):
                    console.print("[red]Error: All log lines must be strings[/red]")
                    return False

                # Test path traversal attempt
                self.run_test(
                    "Test path traversal prevention",
                    "GET",
                    "/api/v1/logs/..%2F..%2Fetc%2Fpasswd/content",
                    expected_status=400
                )

                # Test non-existent file
                self.run_test(
                    "Get content for non-existent file",
                    "GET",
                    "/api/v1/logs/nonexistent.log/content",
                    expected_status=404
                )

                # Test without auth
                self.run_test(
                    "Get log content without auth",
                    "GET",
                    "/api/v1/logs/network.log/content",
                    auth=False,
                    expected_status=401
                )

            return True
        return False

    def run_all_tests(self):
        """Run complete test suite"""
        console.print("[bold]Starting API Tests[/bold]\n")

        # Initial authentication
        if not self.authenticate():
            console.print("[red]Authentication failed - cannot continue tests[/red]")
            return

        # Token tests
        time.sleep(.33)
        self.test_refresh_token()
        time.sleep(.33)
        self.test_token_invalidation()

        # Re-authenticate after token invalidation
        time.sleep(.33)
        if not self.authenticate():
            console.print("[red]Re-authentication failed after token invalidation - cannot continue tests[/red]")
            return

        # Sensor tests
        time.sleep(.33)
        self.test_sensors()
        time.sleep(.25)
        self.test_sensor()

        # Subnet location counts tests
        time.sleep(.25)
        self.test_subnet_location_counts()

        # IP search tests (using real sensors)
        time.sleep(.25)
        self.test_ip_search()

        # Analytics tests
        time.sleep(.25)
        self.test_analytics()

        # Subnet mapping tests
        time.sleep(.25)
        self.test_subnet_mapping()

        # Job management tests
        time.sleep(.25)
        self.test_submit_job()
        time.sleep(.25)
        self.test_get_job()
        time.sleep(.25)
        self.test_cancel_job()
        time.sleep(.25)
        self.test_delete_job()

        # System tests
        time.sleep(.25)
        self.test_admin_endpoints()
        time.sleep(.25)
        self.test_health_endpoints()
        time.sleep(.25)
        self.test_storage_status()

        # Network tests
        time.sleep(.25)
        self.test_network_locations()
        time.sleep(.25)
        self.test_network_connections()

        # Log tests
        time.sleep(.25)
        self.test_logs()

    def print_results(self):
        """Print test results in a table"""
        console.print("\n[bold]Test Results Summary[/bold]")

        if not self.results:
            console.print("[yellow]No test results to display[/yellow]")
            return

        table = Table()
        table.add_column("Test", style="cyan")
        table.add_column("Method", style="magenta")
        table.add_column("Endpoint", style="blue")
        table.add_column("Status", justify="right")
        table.add_column("Expected", justify="right")
        table.add_column("Result", justify="center")

        total_tests = len(self.results)
        success_count = 0

        for result in self.results:
            if not isinstance(result, dict):
                console.print(f"[red]Invalid result format: {result}[/red]")
                continue

            try:
                status = str(result.get('status', 'N/A'))
                expected = str(result.get('expected', 'N/A'))
                success = result.get('success', False)

                if success:
                    success_count += 1
                    result_text = "✓"
                    style = "green"
                else:
                    result_text = "✗"
                    style = "red"

                table.add_row(
                    str(result.get('name', 'Unknown')),
                    str(result.get('method', 'N/A')),
                    str(result.get('endpoint', 'N/A')),
                    status,
                    expected,
                    result_text,
                    style=style
                )
            except Exception as e:
                console.print(f"[red]Error processing result: {e}[/red]")
                console.print(f"[red]Result data: {result}[/red]")

        console.print(table)

        if total_tests > 0:
            success_rate = (success_count / total_tests) * 100
            console.print(f"\nSuccess Rate: {success_rate:.1f}% ({success_count}/{total_tests})")

            failed_tests = [r for r in self.results if not r.get('success', False)]
            if failed_tests:
                console.print("\n[bold red]Failed Tests Details:[/bold red]")
                for test in failed_tests:
                    console.print(f"\n[bold]{test.get('name', 'Unknown Test')}[/bold]")
                    console.print(f"Endpoint: {test.get('endpoint', 'N/A')}")
                    if 'response' in test:
                        console.print("Response:")
                        if isinstance(test['response'], dict):
                            console.print(json.dumps(test['response'], indent=2))
                        else:
                            console.print(str(test['response']))
        else:
            console.print("\n[yellow]No tests were executed[/yellow]")

if __name__ == '__main__':
    # Get base URL from command line or use default
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL

    console.print(f"Testing API at {base_url}")

    try:
        tester = ApiTester(base_url)
        tester.run_all_tests()
        tester.print_results()
    except KeyboardInterrupt:
        console.print("\n[yellow]Tests interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Test execution failed: {str(e)}[/red]")
        sys.exit(1)

