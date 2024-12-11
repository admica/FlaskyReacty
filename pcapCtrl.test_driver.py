#!/opt/pcapserver/venv_linux/bin/python3
# Remote sensor simulator driver for pcapCtrl
# PATH: ./pcapCtrl
import argparse
import json
import sys
import time
import random
import paramiko
from typing import Dict, Any, List, Tuple, Set

def check_sensor_status(hostname: str) -> bool:
    """Check if sensor is up by SSH'ing and checking control file contents"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname, timeout=5) # Don't include the user

        # Try to read the control file
        fqdn = hostname  # Use the full hostname
        cmd = f"cat /opt/pcapserver/latest/{fqdn}.pcapCtrl | grep = | sed 's/.*=//'"
        stdin, stdout, stderr = ssh.exec_command(cmd)

        # Read the output and error
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        exit_status = stdout.channel.recv_exit_status()

        ssh.close()

        # Check if content is exactly "0"
        if output in [ "1", "true", "True", "TRUE", "yes", "Yes", "YES", "y", "Y" ]:
            print("KABOOM: Host reached but failure to talk to something on the other end")
            return False
        return True

    except Exception as e:
        print(f"SSH connection failed: {str(e)}", file=sys.stderr)
        return False

class SensorTopology:
    """Defines the network topology and relationships between sensors"""

    # Map hostnames to sensor profiles
    SENSOR_MAPPINGS = {
        "ksc1.domain.com": "sensor1",
        "sensor1.domain.com": "sensor2",
        "gsfc1.domain.com": "sensor3",
        "gsfc2.domain.com": "sensor4"
    }

    # Define known subnets for each sensor
    SENSOR_SUBNETS = {
        "sensor1": {
            "internal_sources": [
                "192.168.10.0",
                "192.168.11.0",
                "192.168.12.0",
                "192.168.13.0",
                "192.168.14.0",
                "192.168.15.0",
                "192.168.16.0",
                "192.168.17.0",
                "192.168.18.0",
                "192.168.19.0",
                "10.1.1.0",
                "10.1.2.0",
                "10.1.3.0",
                "10.1.4.0",
                "10.1.5.0"
            ],
            "internal_destinations": [
                "172.16.50.0",  # Routes to sensor2
                "172.16.51.0",  # Routes to sensor2
                "172.16.52.0",  # Routes to sensor2
                "172.16.53.0",  # Routes to sensor2
                "172.16.54.0",  # Routes to sensor2
                "10.2.1.0",     # Routes to sensor3
                "10.2.2.0",     # Routes to sensor3
                "10.2.3.0",     # Routes to sensor3
                "10.2.4.0",     # Routes to sensor3
                "10.2.5.0"      # Routes to sensor3
            ]
        },
        "sensor2": {
            "internal_sources": [
                "172.16.50.0",
                "172.16.51.0",
                "172.16.52.0",
                "172.16.53.0",
                "172.16.54.0",
                "172.16.55.0",
                "172.16.56.0",
                "172.16.57.0",
                "172.16.58.0",
                "172.16.59.0",
                "172.16.60.0",
                "172.16.61.0",
                "172.16.62.0",
                "172.16.63.0",
                "172.16.64.0"
            ],
            "internal_destinations": [
                "192.168.50.0",
                "192.168.51.0",
                "192.168.52.0",
                "192.168.53.0",
                "192.168.54.0",
                "192.168.55.0",
                "192.168.56.0",
                "192.168.57.0",
                "192.168.58.0",
                "192.168.59.0"
            ]
        },
        "sensor3": {
            "internal_sources": [
                "10.2.1.0",     # Overlaps with sensor1 destinations
                "10.2.2.0",     # Overlaps with sensor1 destinations
                "10.2.3.0",
                "10.2.4.0",
                "10.2.5.0",
                "10.2.6.0",
                "10.2.7.0",
                "10.2.8.0",
                "10.2.9.0",
                "10.2.10.0",
                "10.2.11.0",
                "10.2.12.0",
                "10.2.13.0",
                "10.2.14.0",
                "10.2.15.0"
            ],
            "internal_destinations": [
                "192.168.100.0",
                "192.168.101.0",
                "192.168.102.0",
                "192.168.103.0",
                "192.168.104.0",
                "192.168.105.0",
                "192.168.106.0",
                "192.168.107.0",
                "192.168.108.0",
                "192.168.109.0"
            ]
        },
        "sensor4": {
            "internal_sources": [
                "172.16.50.0",  # Appears in sensor2's sources
                "172.16.51.0",
                "172.16.52.0",
                "10.2.1.0",     # Appears in sensor3's sources
                "10.2.2.0",
                "10.2.3.0",
                "192.168.10.0", # Appears in sensor1's sources
                "192.168.11.0",
                "192.168.12.0",
                "192.168.13.0",
                "192.168.14.0",
                "192.168.15.0",
                "192.168.16.0",
                "192.168.17.0",
                "192.168.18.0"
            ],
            "internal_destinations": [
                "192.168.200.0",
                "192.168.201.0",
                "192.168.202.0",
                "192.168.203.0",
                "192.168.204.0",
                "192.168.205.0",
                "192.168.206.0",
                "192.168.207.0",
                "192.168.208.0",
                "192.168.209.0"
            ]
        }
    }

    @classmethod
    def get_sensor_profile(cls, hostname: str) -> str:
        """Map hostname to sensor profile"""
        return cls.SENSOR_MAPPINGS.get(hostname, "sensor1")

    @classmethod
    def generate_internet_ips(cls, count: int) -> List[str]:
        """Generate random public IP subnets, avoiding RFC1918"""
        public_ips = []
        for _ in range(count):
            while True:
                first = random.randint(1, 223)
                if first not in [10, 172, 192]:  # Avoid private ranges
                    break
            second = random.randint(0, 255)
            third = random.randint(0, 255)
            public_ips.append(f"{first}.{second}.{third}.0")
        return public_ips

class MockPcapCtrl:
    def __init__(self, hostname, port, device=None):
        self.port = str(port)
        self.current_epoch = str(int(time.time()))
        self.sensor_profile = SensorTopology.get_sensor_profile(hostname)

        # Use provided device name or fallback based on port
        if device:
            self.device = device
        else:
            if self.port == "12340":
                self.device = "napa0"
            elif self.port == "12341":
                self.device = "napa1"
            else:
                self.device = "unknown"

        # Generate worker data
        self.workers_data = self._generate_worker_data()

        # Generate subnet data
        self.all_subnets, self.src_subnets, self.dst_subnets = self._generate_subnet_data()

        # Build responses
        self.responses = self._build_responses()

    def _generate_worker_data(self) -> List[Dict[str, str]]:
        """Generate random worker statistics"""
        workers_data = []
        for _ in range(4):
            min_idle = random.randint(800, 1000)
            avg_idle = random.randint(min_idle, 1100)
            max_idle = random.randint(avg_idle, 1200)
            workers_data.append({
                "min_idle": str(min_idle),
                "avg_idle": str(avg_idle),
                "max_idle": str(max_idle)
            })
        return workers_data

    def _generate_subnet_data(self) -> Tuple[List[Tuple[str, int]], List[Tuple[str, int]], List[Tuple[str, int]]]:
        """Generate subnet data based on sensor profile"""
        src_subnets = []
        dst_subnets = []

        # Always include corresponding internal sources/destinations
        topology = SensorTopology.SENSOR_SUBNETS[self.sensor_profile]

        if self.sensor_profile == "sensor1":
            # Sources are specifically internal networks
            src_subnets.extend([
                ("192.168.10.0", random.randint(1000000000, 35000000000)),
                ("192.168.11.0", random.randint(1000000000, 35000000000)),
                ("192.168.12.0", random.randint(1000000000, 35000000000)),
                ("192.168.13.0", random.randint(1000000000, 35000000000)),
                ("192.168.14.0", random.randint(1000000000, 35000000000)),
                ("192.168.15.0", random.randint(1000000000, 35000000000)),
                ("192.168.16.0", random.randint(1000000000, 35000000000)),
                ("192.168.17.0", random.randint(1000000000, 35000000000)),
                ("192.168.18.0", random.randint(1000000000, 35000000000)),
                ("192.168.19.0", random.randint(1000000000, 35000000000)),
                ("10.1.1.0", random.randint(1000000000, 35000000000)),
                ("10.1.2.0", random.randint(1000000000, 35000000000)),
                ("10.1.3.0", random.randint(1000000000, 35000000000)),
                ("10.1.4.0", random.randint(1000000000, 35000000000)),
                ("10.1.5.0", random.randint(1000000000, 35000000000))
            ])
            # Destinations include networks that MUST appear as sources in sensor2/3
            dst_subnets.extend([
                ("172.16.50.0", random.randint(1000000000, 35000000000)),  # Will be source in sensor2
                ("172.16.51.0", random.randint(1000000000, 35000000000)),  # Will be source in sensor2
                ("172.16.52.0", random.randint(1000000000, 35000000000)),  # Will be source in sensor2
                ("172.16.53.0", random.randint(1000000000, 35000000000)),  # Will be source in sensor2
                ("172.16.54.0", random.randint(1000000000, 35000000000)),  # Will be source in sensor2
                ("10.2.1.0", random.randint(1000000000, 35000000000)),     # Will be source in sensor3
                ("10.2.2.0", random.randint(1000000000, 35000000000)),     # Will be source in sensor3
                ("10.2.3.0", random.randint(1000000000, 35000000000)),     # Will be source in sensor3
                ("10.2.4.0", random.randint(1000000000, 35000000000)),     # Will be source in sensor3
                ("10.2.5.0", random.randint(1000000000, 35000000000))      # Will be source in sensor3
            ])

        elif self.sensor_profile == "sensor2":
            # Sources MUST include the subnets that appear as destinations in sensor1
            src_subnets.extend([
                ("172.16.50.0", random.randint(1000000000, 35000000000)),
                ("172.16.51.0", random.randint(1000000000, 35000000000)),
                ("172.16.52.0", random.randint(1000000000, 35000000000)),
                ("172.16.53.0", random.randint(1000000000, 35000000000)),
                ("172.16.54.0", random.randint(1000000000, 35000000000))
            ])
            # Plus some random internet sources
            src_subnets.extend([(ip, random.randint(1000000000, 35000000000))
                               for ip in SensorTopology.generate_internet_ips(15)])

        elif self.sensor_profile == "sensor3":
            # Sensor 3: Sources overlap with Sensor 1's destinations
            src_subnets.extend([(ip, random.randint(1000000000, 35000000000))
                               for ip in topology["internal_sources"]])
            # Include some subnets that appear in sensor1's destinations
            src_subnets.extend([
                (ip, random.randint(1000000000, 35000000000))
                for ip in SensorTopology.SENSOR_SUBNETS["sensor1"]["internal_destinations"][:2]
            ])

        elif self.sensor_profile == "sensor4":
            # Sensor 4: Sources appear in destinations of sensors 1,2,3
            src_subnets.extend([
                (ip, random.randint(1000000000, 35000000000))
                for ip in SensorTopology.SENSOR_SUBNETS["sensor1"]["internal_destinations"][:1]
            ])
            src_subnets.extend([
                (ip, random.randint(1000000000, 35000000000))
                for ip in SensorTopology.SENSOR_SUBNETS["sensor2"]["internal_destinations"][:1]
            ])
            src_subnets.extend([
                (ip, random.randint(1000000000, 35000000000))
                for ip in SensorTopology.SENSOR_SUBNETS["sensor3"]["internal_destinations"][:1]
            ])

        # Add some random internet sources/destinations for variety
        internet_sources = [(ip, random.randint(1000000000, 35000000000))
                           for ip in SensorTopology.generate_internet_ips(15)]
        internet_dests = [(ip, random.randint(1000000000, 35000000000))
                         for ip in SensorTopology.generate_internet_ips(15)]

        # Deduplicate while preserving order
        seen = set()
        src_subnets = [(subnet, count) for subnet, count in src_subnets
                       if subnet not in seen and not seen.add(subnet)]

        seen = set()
        internet_sources = [(subnet, count) for subnet, count in internet_sources
                          if subnet not in seen and not seen.add(subnet)]
        src_subnets.extend(internet_sources)

        seen = set()
        dst_subnets = [(subnet, count) for subnet, count in dst_subnets
                       if subnet not in seen and not seen.add(subnet)]

        seen = set()
        internet_dests = [(subnet, count) for subnet, count in internet_dests
                         if subnet not in seen and not seen.add(subnet)]
        dst_subnets.extend(internet_dests)

        # Combine for total subnets (no duplicates)
        seen = set()
        all_subnets = [(subnet, count) for subnet, count in (src_subnets + dst_subnets)
                       if subnet not in seen and not seen.add(subnet)]

        return all_subnets, src_subnets, dst_subnets

    def _build_responses(self) -> Dict[str, Any]:
        """Build all response data"""
        responses = {
            "0": {
                "Request": "0",
                "Name": "pcapCollect",
                "Version": "2.7",
                "Date": self.current_epoch,
                "Runtime": str(random.randint(800000, 1200000)),
                "Location": "test",
                "Device": self.device,
                "Workers": "4",
                "Port": self.port,
                "Size": "2G",
                "Output_path": "/pcap/",
                "Proc": f"/usr/local/bin/pcapCollect -d {self.device} -s 2G -w 4 -p {self.port}",
                "Overflows": "0",
                "SrcSubnets": str(len(self.src_subnets)),
                "DstSubnets": str(len(self.dst_subnets)),
                "UniqSubnets": str(len(set(s[0] for s in self.all_subnets))),
                "AvgIdleTime": str(sum(int(w["avg_idle"]) for w in self.workers_data) // 4),
                "AvgWorkTime": "1"
            },
            "6": {
                **{f"worker-{i}": {
                    "MinIdle": w["min_idle"],
                    "MaxIdle": w["max_idle"],
                    "AvgIdle": w["avg_idle"],
                    "MinWork": "1",
                    "MaxWork": "2",
                    "AvgWork": "1"
                } for i, w in enumerate(self.workers_data)},
                "MinIdle": min(w["min_idle"] for w in self.workers_data),
                "MaxIdle": max(w["max_idle"] for w in self.workers_data),
                "AvgIdle": str(sum(int(w["avg_idle"]) for w in self.workers_data) // 4),
                "MinWork": "0",
                "MaxWork": "3",
                "AvgWork": "1"
            }
        }

        # Add subnet responses
        responses["3,0"] = self._format_subnet_response("3", self.all_subnets)
        responses["4,0"] = self._format_subnet_response("4", self.src_subnets)
        responses["5,0"] = self._format_subnet_response("5", self.dst_subnets)

        return responses

    def _format_subnet_response(self, cmd: str, subnets: List[Tuple[str, int]]) -> str:
        """Format subnet data into the expected response string"""
        parts = [f"{cmd},{len(subnets)},0"]
        for subnet, bytes_count in subnets:
            parts.append(f"{subnet},{bytes_count},{self.current_epoch}")
        return ",".join(parts)

    def get_response(self, command: str) -> str:
        """Return the mock response for a given command."""
        if command not in self.responses:
            return f"Error: Unknown command '{command}'"

        response = self.responses[command]
        if isinstance(response, dict):
            return json.dumps(response)
        return response

def parse_args(args):
    # Create parser without help option
    parser = argparse.ArgumentParser(description='pcapCtrl simulator', add_help=False)

    # Add arguments including -h for host
    parser.add_argument('-h', dest='host', required=True, help='Host to connect to')
    parser.add_argument('-c', '--command', required=True, help='Command to send')
    parser.add_argument('-p', '--port', required=True, type=int, help='Port number')
    parser.add_argument('-d', '--device', help='Device name')
    parser.add_argument('--help', action='help', help='Show this help message')

    try:
        return vars(parser.parse_args(args))
    except argparse.ArgumentError:
        parser.print_help()
        sys.exit(1)

def main():
    args = parse_args(sys.argv[1:])

    # Check if sensor is up via SSH
    if not check_sensor_status(args['host']):
        print(f"Error: Sensor {args['host']} is not available - control file not found", file=sys.stderr)
        sys.exit(1)

    # If we get here, sensor is up - proceed with mock data
    pcap_ctrl = MockPcapCtrl(args['host'], args['port'], args.get('device'))
    print(pcap_ctrl.get_response(args['command']))

if __name__ == "__main__":
    main()
