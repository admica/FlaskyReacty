#!/opt/pcapserver/venv_linux/bin/python3
"""
Unified sensor monitoring and management service.
Combines functionality of sensor-info and sensor-status into a single systemd service.
"""
import psycopg2
import psycopg2.extras
import configparser
import subprocess
import sys
import os
import time
from datetime import datetime, timezone, timedelta
import traceback
import psutil
import json
from typing import Dict, Any, List
from partition_manager import manage_time_partitions
import threading
from simpleLogger import SimpleLogger
from cache_utils import invalidate_caches
import paramiko

# Setup logging
logger = SimpleLogger('sensor_monitor')

class ProcessingSummary:
    """Track metrics during sensor processing."""
    def __init__(self):
        self.start_time = datetime.now(timezone.utc)
        self.total_sensors = 0
        self.successful_sensors = 0
        self.failed_sensors = 0
        self.total_devices = 0
        self.online_devices = 0
        self.offline_devices = 0
        self.degraded_devices = 0
        self.src_subnets = 0
        self.dst_subnets = 0
        self.unique_subnets = set()
        self.connection_errors = 0
        self.stats_parse_errors = 0
        self.subnet_parse_errors = 0
        self.db_errors = 0
        self.sensor_times = []
        self.error_details = []
        self.devices = {}  # Track device stats for calculating averages

    def add_device_stats(self, device_name: str, stats: Dict[str, Any]):
        """Track device statistics."""
        self.devices[device_name] = stats

    def add_sensor_time(self, seconds: float):
        """Track processing time for a sensor."""
        self.sensor_times.append(seconds)

    def add_error(self, error_type: str, details: str):
        """Track an error occurrence."""
        self.error_details.append({"type": error_type, "details": details})
        if error_type == "connection":
            self.connection_errors += 1
        elif error_type == "stats_parse":
            self.stats_parse_errors += 1
        elif error_type == "subnet_parse":
            self.subnet_parse_errors += 1
        elif error_type == "db":
            self.db_errors += 1

    def save_to_db(self, cur):
        """Save the monitoring summary to the database."""
        try:
            summary_record = self.get_summary_record()
            cur.execute("""
                INSERT INTO sensor_health_summary (
                    timestamp,
                    duration_seconds,
                    sensors_checked,
                    sensors_online,
                    sensors_offline,
                    sensors_degraded,
                    devices_total,
                    devices_online,
                    devices_offline,
                    devices_degraded,
                    avg_pcap_minutes,
                    avg_disk_usage_pct,
                    errors,
                    performance_metrics
                ) VALUES (
                    %(timestamp)s,
                    %(duration_seconds)s,
                    %(sensors_checked)s,
                    %(sensors_online)s,
                    %(sensors_offline)s,
                    %(sensors_degraded)s,
                    %(devices_total)s,
                    %(devices_online)s,
                    %(devices_offline)s,
                    %(devices_degraded)s,
                    %(avg_pcap_minutes)s,
                    %(avg_disk_usage_pct)s,
                    %(errors)s,
                    %(performance_metrics)s
                )
            """, summary_record)
            logger.info("Successfully saved health summary")
        except Exception as e:
            logger.error(f"Error saving health summary: {e}")
            raise

    def get_summary_record(self):
        """Generate the database record for this monitoring run."""
        end_time = datetime.now(timezone.utc)
        if end_time <= self.start_time:
            end_time = self.start_time + timedelta(microseconds=1)

        duration = (end_time - self.start_time).total_seconds()

        # Calculate average PCAP minutes and disk usage
        total_pcap_mins = 0
        total_disk_pct = 0
        sensor_count = 0

        for device in self.devices.values():
            if device.get('pcap_avail'):
                total_pcap_mins += device['pcap_avail']
            if device.get('usedspace'):
                try:
                    # Convert "45%" to 45
                    disk_pct = int(device['usedspace'].rstrip('%'))
                    total_disk_pct += disk_pct
                except (ValueError, AttributeError):
                    pass
            sensor_count += 1

        avg_pcap_mins = int(total_pcap_mins / sensor_count) if sensor_count > 0 else 0
        avg_disk_pct = int(total_disk_pct / sensor_count) if sensor_count > 0 else 0

        return {
            "timestamp": self.start_time,
            "duration_seconds": int(duration),
            "sensors_checked": self.total_sensors,
            "sensors_online": self.successful_sensors,
            "sensors_offline": self.failed_sensors,
            "sensors_degraded": self.degraded_devices,
            "devices_total": self.total_devices,
            "devices_online": self.online_devices,
            "devices_offline": self.offline_devices,
            "devices_degraded": self.degraded_devices,
            "avg_pcap_minutes": avg_pcap_mins,
            "avg_disk_usage_pct": avg_disk_pct,
            "errors": json.dumps(self.error_details) if self.error_details else None,
            "performance_metrics": json.dumps({
                "avg_processing_time": sum(self.sensor_times) / len(self.sensor_times) if self.sensor_times else 0,
                "peak_memory_mb": int(psutil.Process().memory_info().rss / (1024 * 1024)),
                "src_subnets": self.src_subnets,
                "dst_subnets": self.dst_subnets,
                "unique_subnets": len(self.unique_subnets)
            })
        }

class SensorMonitor:
    def __init__(self, config_path='/opt/pcapserver/config.ini'):
        logger.debug("Initializing SensorMonitor")
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
        logger.debug(f"Loaded config from {config_path}")

        self.db_params = {
            'host': self.config['DB']['hostname'],
            'database': self.config['DB']['database'],
            'user': self.config['DB']['username'],
            'password': self.config['DB']['password']
        }

        self.status_check_interval = self.config.getint('MONITOR', 'status_check_interval', fallback=60)
        self.info_update_interval = self.config.getint('MONITOR', 'info_update_interval', fallback=300)
        self.pcap_ctrl = self.config.get('SENSOR', 'pcapCtrl', fallback='/opt/pcapserver/bin/pcapCtrl')
        # Get subnet limits from config, 0 means no limit
        self.src_subnet_limit = self.config.getint('SENSOR', 'src_subnet_limit', fallback=0)
        self.dst_subnet_limit = self.config.getint('SENSOR', 'dst_subnet_limit', fallback=0)
        logger.debug(f"Monitor intervals: status={self.status_check_interval}s, info={self.info_update_interval}s")
        logger.debug(f"Subnet limits: src={self.src_subnet_limit}, dst={self.dst_subnet_limit}")

        # Initialize SSH keys list
        self.ssh_keys = []
        if 'SSH' in self.config:
            self.ssh_keys = [v for k, v in self.config['SSH'].items() if k.startswith('pubkey')]
            for key in self.ssh_keys:
                logger.debug(f'Added primary SSH pubkey: {key}')

        # Add fallback SSH keys from ~/.ssh
        ssh_dir = os.path.expanduser('~/.ssh')
        if os.path.exists(ssh_dir):
            for f in os.listdir(ssh_dir):
                if f.endswith('.pub'):
                    key = os.path.join(ssh_dir, f)
                    if key not in self.ssh_keys:
                        self.ssh_keys.append(key)
                        logger.debug(f'Added fallback SSH pubkey: {key}')

        self.running = True

    def run(self):
        """Main run loop"""
        logger.info("Starting SensorMonitor service")
        try:
            # Start threads for each monitoring task
            logger.debug("Creating monitoring threads")
            status_thread = threading.Thread(target=self.status_check_loop, name="StatusCheck")
            info_thread = threading.Thread(target=self.info_update_loop, name="InfoUpdate")
            maintenance_thread = threading.Thread(target=self.maintenance_loop, name="Maintenance")

            logger.debug("Starting monitoring threads")
            status_thread.start()
            info_thread.start()
            maintenance_thread.start()

            # Wait for threads to complete
            status_thread.join()
            info_thread.join()
            maintenance_thread.join()

        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            logger.error(traceback.format_exc())
            raise

    def status_check_loop(self):
        """Monitor sensor status"""
        logger.info("Starting status check loop")
        while self.running:
            try:
                logger.debug("Running sensor status checks")
                self.check_all_sensors_status()
                logger.debug("Completed sensor status checks")
            except Exception as e:
                logger.error(f"Error checking sensor status: {e}")
            time.sleep(self.status_check_interval)

    def info_update_loop(self):
        """Update detailed sensor information"""
        logger.info("Starting info update loop")
        while self.running:
            try:
                logger.debug("Running sensor info updates")
                self.update_all_sensors_info()
                logger.debug("Completed sensor info updates")
            except Exception as e:
                logger.error(f"Error updating sensor info: {e}")
            time.sleep(self.info_update_interval)

    def maintenance_loop(self):
        """Perform periodic maintenance tasks"""
        logger.info("Starting maintenance loop")
        while self.running:
            try:
                logger.debug("Running maintenance tasks")
                self.run_maintenance_tasks()
                logger.debug("Completed maintenance tasks")
            except Exception as e:
                logger.error(f"Error in maintenance tasks: {e}")
            time.sleep(3600)  # Run maintenance hourly

    def _create_offline_device_stats(self) -> Dict[str, Any]:
        """Create a default stats dictionary for offline devices"""
        return {
            'status': 'Offline',
            'runtime': 0,
            'workers': 0,
            'src_subnets': 0,
            'dst_subnets': 0,
            'uniq_subnets': 0,
            'avg_idle_time': 0,
            'avg_work_time': 0,
            'overflows': 0,
            'size': '0',
            'version': None,
            'output_path': None,
            'proc': '',
            'stats_date': datetime.now(timezone.utc),
            'pcap_avail': 0,
            'totalspace': 'n/a',
            'usedspace': 'n/a',
            'subnet_data': {'src_subnets': [], 'dst_subnets': []},
            'error': None
        }

    def get_device_stats(self, sensor_fqdn: str, port: int) -> Dict[str, Any]:
        """Get device statistics"""
        logger.debug(f"Getting device stats for {sensor_fqdn}:{port}")

        device_stats = self._create_offline_device_stats()

        try:
            # First get basic device stats (command 0)
            cmd = f"{self.pcap_ctrl} -h {sensor_fqdn} -p {port} -c 0"
            logger.debug(f"Running command: {cmd}")
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"pcapCtrl command failed: {result.stderr}")
                device_stats['error'] = f"pcapCtrl command failed: {result.stderr}"
                return device_stats

            # Parse JSON response
            try:
                stats = json.loads(result.stdout)
                logger.debug(f"Raw device stats: {stats}")

                if 'Location' in stats: stats['Location'] = stats['Location'].upper()

            except json.JSONDecodeError:
                logger.error(f"Invalid JSON from pcapCtrl: {result.stdout}")
                device_stats['error'] = f"Invalid JSON response: {result.stdout}"
                return device_stats

            # Convert stats to our format
            device_stats.update({
                'status': 'Online' if stats.get('Runtime') and int(stats.get('Runtime', 0)) > 0 else 'Offline',
                'runtime': int(stats.get('Runtime', 0)),
                'workers': int(stats.get('Workers', 0)),
                'src_subnets': int(stats.get('SrcSubnets', 0)),
                'dst_subnets': int(stats.get('DstSubnets', 0)),
                'uniq_subnets': int(stats.get('UniqSubnets', 0)),
                'avg_idle_time': int(stats.get('AvgIdleTime', 0)),
                'avg_work_time': int(stats.get('AvgWorkTime', 0)),
                'overflows': int(stats.get('Overflows', 0)),
                'size': stats.get('Size', '0'),
                'version': stats.get('Version'),
                'output_path': stats.get('Output_path', '/pcap/'),
                'proc': stats.get('Proc', ''),
                'stats_date': datetime.fromtimestamp(int(stats.get('Date', time.time())), timezone.utc),
                'subnet_data': {'src_subnets': [], 'dst_subnets': []}
            })

            # Now do all SSH operations in one block with proper cleanup
            ssh = None
            try:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                # Try each SSH key until one works
                connected = False
                for pubkey in self.ssh_keys:
                    try:
                        logger.debug(f'SSH {sensor_fqdn} using pubkey: {pubkey}')
                        ssh.connect(
                            sensor_fqdn,
                            username=self.config.get("SSH", "username", fallback="pcapuser"),
                            key_filename=pubkey,
                            timeout=self.config.getint("SSH", "timeout", fallback=10)
                        )
                        logger.info(f'SSH {sensor_fqdn} established with pubkey: {pubkey}')
                        connected = True
                        break
                    except Exception as e:
                        logger.debug(f'SSH {sensor_fqdn} failed with pubkey: {pubkey} - {str(e)}')
                        continue

                if not connected:
                    raise Exception("Failed to connect with any SSH key")

                # Run both agent check and disk space commands in one session
                cmd = "/opt/autopcap_client/latest/agent.py -e -O /var/tmp/autopcap/agent/ && echo '---SEP---' && df -hP /pcap | tail -1 | awk '{print $2,$5}'"
                _, stdout, stderr = ssh.exec_command(cmd)
                output = stdout.read().decode().strip()
                agent_out = stderr.read().decode().strip()  # Agent.py outputs to stderr by design

                # Process the output
                if output:
                    parts = output.split('---SEP---')
                    if len(parts) >= 2:
                        agent_output = parts[0].strip()
                        if agent_out:  # Use stderr if present for agent.py output
                            agent_output = agent_out
                        df_output = parts[1].strip()

                        # Parse agent.py output
                        if agent_output:
                            logger.debug(f'Agent output: [{agent_output}]')
                            for line in agent_output.split('\n'):
                                if line.startswith('AGENT_MINUTES_OF_PCAP_AVAILABLE'):
                                    device_stats['pcap_avail'] = int(line.split(' ')[1])
                                    break

                        # Parse df output
                        if df_output:
                            logger.debug(f'DF output: [{df_output}]')
                            try:
                                total, used = df_output.split()
                                device_stats['totalspace'] = total
                                device_stats['usedspace'] = used
                            except ValueError as e:
                                logger.error(f"Error parsing df output '{df_output}': {e}")

            except Exception as e:
                logger.error(f"SSH operations failed: {e}")
            finally:
                if ssh:
                    ssh.close()
                    logger.debug(f"Closed SSH connection to {sensor_fqdn}")

            # Now get subnet data
            # Source subnets (command 4,10)
            src_limit_param = f",{self.src_subnet_limit}" if self.src_subnet_limit > 0 else ",0"
            cmd = f"{self.pcap_ctrl} -h {sensor_fqdn} -p {port} -c 4{src_limit_param}"
            logger.debug(f"Running command: {cmd}")
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            if result.returncode == 0:
                parts = result.stdout.strip().split(',')
                logger.debug(f"Source subnet response: {parts}")
                if len(parts) > 3:  # Has subnet data
                    # Skip first 3 fields (4,count,0)
                    for i in range(3, len(parts), 3):
                        if i + 2 < len(parts):
                            # Add /24 to subnet if not present
                            subnet = parts[i] if parts[i].endswith('/24') else f"{parts[i]}/24"
                            device_stats['subnet_data']['src_subnets'].append({
                                'subnet': subnet,
                                'count': int(parts[i+1]),
                                'timestamp': int(parts[i+2])
                            })
                logger.debug(f"Parsed {len(device_stats['subnet_data']['src_subnets'])} source subnets")

            # Destination subnets (command 5,10)
            dst_limit_param = f",{self.dst_subnet_limit}" if self.dst_subnet_limit > 0 else ",0"
            cmd = f"{self.pcap_ctrl} -h {sensor_fqdn} -p {port} -c 5{dst_limit_param}"
            logger.debug(f"Running command: {cmd}")
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            if result.returncode == 0:
                parts = result.stdout.strip().split(',')
                logger.debug(f"Destination subnet response: {parts}")
                if len(parts) > 3:  # Has subnet data
                    # Skip first 3 fields (5,count,0)
                    for i in range(3, len(parts), 3):
                        if i + 2 < len(parts):
                            # Add /24 to subnet if not present
                            subnet = parts[i] if parts[i].endswith('/24') else f"{parts[i]}/24"
                            device_stats['subnet_data']['dst_subnets'].append({
                                'subnet': subnet,
                                'count': int(parts[i+1]),
                                'timestamp': int(parts[i+2])
                            })
                logger.debug(f"Parsed {len(device_stats['subnet_data']['dst_subnets'])} destination subnets")

            return device_stats

        except Exception as e:
            logger.error(f"Error getting device stats: {e}")
            logger.error(traceback.format_exc())
            return self._create_offline_device_stats()

    def update_device_status(self, cur, sensor_name: str, device_name: str,
                           port: int, new_stats: Dict[str, Any],
                           current_status: str) -> None:
        """Update device status and stats in database"""
        if new_stats['status'] != current_status:
            logger.info(f"Device {sensor_name}/{device_name} status changing from {current_status} to {new_stats['status']}")

        cur.execute("""
            UPDATE devices
            SET status = %s::device_status,
                last_checked = NOW(),
                runtime = %s,
                workers = %s,
                src_subnets = %s,
                dst_subnets = %s,
                uniq_subnets = %s,
                avg_idle_time = %s,
                avg_work_time = %s,
                overflows = %s,
                size = %s,
                version = %s,
                output_path = %s,
                proc = %s,
                stats_date = %s
            WHERE sensor = %s AND name = %s AND port = %s
        """, (
            new_stats['status'],
            new_stats['runtime'],
            new_stats['workers'],
            new_stats['src_subnets'],
            new_stats['dst_subnets'],
            new_stats['uniq_subnets'],
            new_stats['avg_idle_time'],
            new_stats['avg_work_time'],
            new_stats['overflows'],
            new_stats['size'],
            new_stats['version'],
            new_stats['output_path'],
            new_stats['proc'],
            new_stats['stats_date'],
            sensor_name,
            device_name,
            port
        ))

    def check_sensor_status(self, sensor_fqdn: str) -> str:
        """Check basic sensor connectivity and determine status"""
        logger.debug(f"Starting status check for sensor {sensor_fqdn}")
        try:
            # Try to ping the sensor first
            logger.debug(f"Pinging {sensor_fqdn}")
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", sensor_fqdn],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                logger.debug(f"Ping failed for {sensor_fqdn}: {result.stderr}")
                return 'Offline'

            logger.debug(f"Ping successful for {sensor_fqdn}, attempting SSH connection")
            # If ping succeeds, try SSH checks
            ssh = None
            try:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                # Try each SSH key until one works
                connected = False
                for pubkey in self.ssh_keys:
                    try:
                        logger.debug(f'Trying SSH key {pubkey} for {sensor_fqdn}')
                        ssh.connect(
                            sensor_fqdn,
                            username=self.config.get("SSH", "username", fallback="pcapuser"),
                            key_filename=pubkey,
                            timeout=self.config.getint("SSH", "timeout", fallback=10)
                        )
                        logger.debug(f'Successfully connected to {sensor_fqdn} with key {pubkey}')
                        connected = True
                        break
                    except Exception as e:
                        logger.debug(f'SSH connection failed with key {pubkey}: {str(e)}')
                        continue

                if not connected:
                    logger.debug(f"Failed to connect to {sensor_fqdn} with any SSH key")
                    return 'Offline'

                # Check if run_job.py is running and get disk space in one command
                # Using ps -wweo to get full command lines without truncation
                # Using grep to find run_job.py in the full command
                cmd = 'ps -wweo pid,cmd | grep "run_job.py" | grep -v grep | wc -l; df -hP /pcap | tail -n1 | awk \'{print $4,$5}\''
                logger.debug(f"Running status check command on {sensor_fqdn}: {cmd}")
                
                # Also get the actual process details for logging
                detail_cmd = 'ps -wweo pid,cmd | grep "run_job.py" | grep -v grep || true'
                _, stdout, stderr = ssh.exec_command(cmd, timeout=5)
                output = stdout.read().decode().strip()
                error = stderr.read().decode().strip()

                # Get process details if any exist
                _, detail_stdout, _ = ssh.exec_command(detail_cmd, timeout=5)
                process_details = detail_stdout.read().decode().strip()
                if process_details:
                    logger.debug(f"Found run_job.py processes on {sensor_fqdn}:\n{process_details}")

                logger.debug(f"Raw command output from {sensor_fqdn}: [{output}]")
                if error:
                    logger.debug(f"Command stderr from {sensor_fqdn}: [{error}]")

                if error:
                    logger.error(f"Error running status check command on {sensor_fqdn}: {error}")
                    return 'Degraded'

                if output:
                    lines = output.splitlines()
                    logger.debug(f"Command output lines from {sensor_fqdn}: {lines}")
                    
                    if len(lines) < 2:
                        logger.error(f"Unexpected command output format from {sensor_fqdn}: {output}")
                        return 'Degraded'

                    # First line is the count of run_job.py processes
                    try:
                        job_count = int(lines[0])
                        logger.debug(f"Found {job_count} run_job.py processes on {sensor_fqdn}")
                    except (ValueError, IndexError) as e:
                        logger.error(f"Error parsing job count from {sensor_fqdn} '{lines[0]}': {e}")
                        return 'Degraded'

                    # Last line is disk space
                    try:
                        disk_space = lines[-1]
                        logger.debug(f"Parsing disk space line from {sensor_fqdn}: [{disk_space}]")
                        avail, used_pct = disk_space.split()
                        used_pct = int(used_pct.rstrip('%'))
                        logger.debug(f"Disk space on {sensor_fqdn}: available={avail}, used={used_pct}%")

                        if job_count > 0:
                            logger.debug(f"Setting {sensor_fqdn} status to Busy ({job_count} run_job.py processes)")
                            return 'Busy'
                        elif used_pct >= 98:
                            logger.debug(f"Setting {sensor_fqdn} status to Degraded (disk usage {used_pct}%)")
                            return 'Degraded'
                        else:
                            logger.debug(f"Setting {sensor_fqdn} status to Online (no jobs, disk usage {used_pct}%)")
                            return 'Online'

                    except (ValueError, IndexError) as e:
                        logger.error(f"Error parsing disk space output from {sensor_fqdn} '{disk_space}': {e}")
                        return 'Degraded'
                else:
                    logger.error(f"No output from status check command on {sensor_fqdn}")
                    return 'Degraded'

            except Exception as e:
                logger.error(f"SSH operation failed for {sensor_fqdn}: {e}")
                logger.debug(f"SSH error details for {sensor_fqdn}: {traceback.format_exc()}")
                return 'Degraded'
            finally:
                if ssh:
                    ssh.close()
                    logger.debug(f"Closed SSH connection to {sensor_fqdn}")

        except Exception as e:
            logger.error(f"Status check failed for {sensor_fqdn}: {e}")
            logger.debug(f"Status check error details for {sensor_fqdn}: {traceback.format_exc()}")
            return 'Offline'

    def check_all_sensors_status(self):
        """Check basic connectivity and status of all sensors"""
        logger.info("Starting sensor status check")
        conn = psycopg2.connect(**self.db_params)
        try:
            cur = conn.cursor()
            # Get all sensors and their current status
            cur.execute("SELECT name, fqdn, status FROM sensors")
            sensors = cur.fetchall()
            logger.debug(f"Found {len(sensors)} sensors to check")

            for sensor_name, sensor_fqdn, current_status in sensors:
                try:
                    new_status = self.check_sensor_status(sensor_fqdn)

                    # Always update last_seen if we can reach the sensor
                    if new_status != 'Offline':
                        cur.execute("""
                            UPDATE sensors
                            SET last_seen = NOW()
                            WHERE name = %s
                        """, (sensor_name,))

                    # Only update status if it changed
                    if new_status != current_status:
                        # If going offline, also mark all devices offline
                        if new_status == 'Offline':
                            cur.execute("""
                                UPDATE devices
                                SET status = 'Offline'::device_status,
                                    last_checked = NOW()
                                WHERE sensor = %s
                            """, (sensor_name,))

                        cur.execute("""
                            UPDATE sensors
                            SET status = %s
                            WHERE name = %s
                        """, (new_status, sensor_name))
                        logger.info(f"Updated status for {sensor_name} from {current_status} to {new_status}")
                except Exception as e:
                    logger.error(f"Error checking sensor {sensor_name}: {e}")

            conn.commit()
            logger.info("Completed sensor status check")

        finally:
            cur.close()
            conn.close()

    def update_all_sensors_info(self):
        """Update detailed information for all sensors"""
        logger.info("Starting sensor info update")
        conn = psycopg2.connect(**self.db_params)
        try:
            cur = conn.cursor()
            # Get ALL sensors to properly count states
            cur.execute("SELECT name, fqdn, status FROM sensors")
            sensors = cur.fetchall()

            summary = ProcessingSummary()
            summary.total_sensors = len(sensors)

            # Count sensor states
            for _, _, status in sensors:
                if status == 'Online':
                    summary.successful_sensors += 1
                elif status == 'Offline':
                    summary.failed_sensors += 1
                elif status == 'Degraded':
                    summary.degraded_sensors += 1
                elif status == 'Busy':
                    summary.successful_sensors += 1

            # Get device counts - this is the only place we count devices
            cur.execute("""
                SELECT status, COUNT(*)
                FROM devices
                GROUP BY status
            """)
            device_counts = cur.fetchall()

            for status, count in device_counts:
                summary.total_devices += count
                if status == 'Online':
                    summary.online_devices += count
                elif status == 'Offline':
                    summary.offline_devices += count
                elif status == 'Degraded':
                    summary.degraded_devices += count

            # Only process active sensors for updates
            active_sensors = [s for s in sensors if s[2] in ('Online', 'Busy', 'Degraded')]
            logger.debug(f"Found {len(active_sensors)} active sensors to update")

            start_time = time.time()
            for sensor_name, sensor_fqdn, status in active_sensors:
                try:
                    sensor_start = time.time()
                    self.update_sensor_info(cur, sensor_name, sensor_fqdn, summary)
                    summary.add_sensor_time(time.time() - sensor_start)
                except Exception as e:
                    logger.error(f"Error updating sensor {sensor_name}: {e}")
                    summary.add_error("sensor_update", str(e))

            # Save the processing summary
            summary.save_to_db(cur)
            conn.commit()
            logger.info(f"Completed sensor info update in {time.time() - start_time:.2f} seconds")

        finally:
            cur.close()
            conn.close()

    def update_subnet_location_map(self, cur, location: str):
        """Update subnet_location_map based on loc_src and loc_dst tables for a location"""
        try:
            location = location.strip().upper()
            logger.debug(f"Updating subnet_location_map for location {location}")

            cur.execute("""
                SELECT site
                FROM locations
                WHERE site = %s
            """, (location,))
            src_loc_result = cur.fetchone()
            if not src_loc_result:
                logger.error(f"Source location {location} not found in locations table")
                return
            src_location = src_loc_result[0]

            cur.execute("""
                SELECT DISTINCT l.site
                FROM sensors s
                JOIN locations l ON l.site = s.location
                WHERE s.location != %s
                AND s.status != 'Offline'
            """, (location,))
            dst_locations = [row[0] for row in cur.fetchall()]

            current_time = int(time.time())
            for dst_location in dst_locations:
                logger.debug(f"Processing mappings from {src_location} to {dst_location}")
                cur.execute("SELECT update_subnet_mappings(%s, %s, %s)",
                          (src_location, dst_location, current_time))

            cur.execute("REFRESH MATERIALIZED VIEW network_traffic_summary")

        except Exception as e:
            logger.error(f"Error updating subnet location map: {e}")
            raise

    def update_device_subnets(self, cur, subnet_data: Dict, sensor_name: str, device_name: str, summary: ProcessingSummary):
        """Update subnet information for a device"""
        logger.debug(f"Updating subnets for device {device_name} on sensor {sensor_name}")
        try:
            cur.execute("""
                SELECT l.site
                FROM sensors s
                JOIN locations l ON l.site = s.location
                WHERE s.name = %s
            """, (sensor_name,))
            result = cur.fetchone()
            if not result:
                logger.error(f"Location not found for sensor {sensor_name}")
                return
            location = result[0]
            logger.debug(f"Device location: {location}")

            current_time = int(time.time())

            if 'src_subnets' in subnet_data:
                src_values = [(
                    subnet['subnet'],
                    subnet['count'],
                    subnet['timestamp'],
                    subnet['timestamp'],
                    sensor_name,
                    device_name
                ) for subnet in subnet_data['src_subnets']]

                if src_values:
                    logger.debug(f"Inserting {len(src_values)} source subnets")
                    psycopg2.extras.execute_values(
                        cur,
                        f"""
                        INSERT INTO loc_src_{location}
                            (subnet, count, first_seen, last_seen, sensor, device)
                        VALUES %s
                        ON CONFLICT (subnet, sensor, device) DO UPDATE
                        SET count = loc_src_{location}.count + EXCLUDED.count,
                            last_seen = GREATEST(loc_src_{location}.last_seen, EXCLUDED.last_seen)
                        """,
                        src_values
                    )
                    summary.src_subnets += len(src_values)
                    summary.unique_subnets.update(v[0] for v in src_values)

            if 'dst_subnets' in subnet_data:
                dst_values = [(
                    subnet['subnet'],
                    subnet['count'],
                    subnet['timestamp'],
                    subnet['timestamp'],
                    sensor_name,
                    device_name
                ) for subnet in subnet_data['dst_subnets']]

                if dst_values:
                    logger.debug(f"Inserting {len(dst_values)} destination subnets")
                    psycopg2.extras.execute_values(
                        cur,
                        f"""
                        INSERT INTO loc_dst_{location}
                            (subnet, count, first_seen, last_seen, sensor, device)
                        VALUES %s
                        ON CONFLICT (subnet, sensor, device) DO UPDATE
                        SET count = loc_dst_{location}.count + EXCLUDED.count,
                            last_seen = GREATEST(loc_dst_{location}.last_seen, EXCLUDED.last_seen)
                        """,
                        dst_values
                    )
                    summary.dst_subnets += len(dst_values)
                    summary.unique_subnets.update(v[0] for v in dst_values)

            cur.execute("""
                SELECT update_subnet_mappings(%s, %s, %s)
            """, (location, location, current_time))

            logger.debug(f"Successfully updated subnets for device {device_name}")

        except Exception as e:
            logger.error(f"Error updating subnets for device {device_name}: {e}")
            logger.error(traceback.format_exc())
            summary.add_error("subnet_update", str(e))
            raise

    def run_maintenance_tasks(self):
        """Run periodic maintenance tasks"""
        logger.info("Starting maintenance tasks")
        conn = psycopg2.connect(**self.db_params)
        try:
            cur = conn.cursor()

            logger.debug("Managing time-based partitions")
            manage_time_partitions(cur, self.config.getint('DB', 'retention_hours', fallback=24))

            logger.debug("Cleaning up old subnet mappings")
            cur.execute("SELECT cleanup_old_subnet_mappings()")

            logger.debug("Refreshing network traffic summary")
            cur.execute("SELECT refresh_network_traffic_summary()")

            conn.commit()
            logger.info("Completed maintenance tasks")

        finally:
            cur.close()
            conn.close()

    def update_sensor_info(self, cur, sensor_name: str, sensor_fqdn: str, summary: ProcessingSummary):
        """Update information for a single sensor and its devices"""
        cur.execute("""
            SELECT name, port, device_type
            FROM devices
            WHERE sensor = %s
        """, (sensor_name,))
        devices = cur.fetchall()
        logger.debug(f"Found {len(devices)} devices for sensor {sensor_name}")

        for device_name, port, device_type in devices:
            try:
                logger.debug(f"Updating device {device_name} on sensor {sensor_name}")
                stats = self.get_device_stats(sensor_fqdn, port)

                summary.add_device_stats(device_name, stats)

                cur.execute("""
                    UPDATE devices
                    SET status = %s,
                        last_checked = NOW(),
                        runtime = %s,
                        workers = %s,
                        src_subnets = %s,
                        dst_subnets = %s,
                        uniq_subnets = %s,
                        avg_idle_time = %s,
                        avg_work_time = %s,
                        overflows = %s,
                        size = %s,
                        version = %s,
                        output_path = %s,
                        proc = %s,
                        stats_date = %s,
                        fqdn = %s
                    WHERE sensor = %s AND name = %s
                """, (
                    stats['status'],
                    stats['runtime'],
                    stats['workers'],
                    stats['src_subnets'],
                    stats['dst_subnets'],
                    stats['uniq_subnets'],
                    stats['avg_idle_time'],
                    stats['avg_work_time'],
                    stats['overflows'],
                    stats['size'],
                    stats['version'],
                    stats['output_path'],
                    stats['proc'],
                    stats['stats_date'],
                    sensor_fqdn,
                    sensor_name,
                    device_name
                ))

                if device_name == devices[0][0]:
                    cur.execute("""
                        UPDATE sensors
                        SET version = %s,
                            last_update = NOW(),
                            pcap_avail = %s,
                            totalspace = %s,
                            usedspace = %s
                        WHERE name = %s
                    """, (
                        stats['version'],
                        stats.get('pcap_avail', 0),
                        stats.get('totalspace', '0'),
                        stats.get('usedspace', '0'),
                        sensor_name
                    ))

                if 'subnet_data' in stats:
                    logger.debug(f"Processing subnet data for device {device_name}")
                    self.update_device_subnets(cur, stats['subnet_data'], sensor_name, device_name, summary)

                if stats['status'] == 'Online':
                    summary.online_devices += 1
                elif stats['status'] == 'Offline':
                    summary.offline_devices += 1
                elif stats['status'] == 'Degraded':
                    summary.degraded_devices += 1

            except Exception as e:
                logger.error(f"Error updating device {device_name}: {e}")
                summary.add_error("device_update", str(e))

        logger.debug("Invalidating caches")
        invalidate_caches()

def main():
    monitor = SensorMonitor()
    try:
        monitor.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        monitor.running = False

if __name__ == '__main__':
    main()
