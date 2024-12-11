#!/usr/bin/env python3
import sys
sys.path.append('/opt/pcapserver/')

import argparse
import random
import time
from simpleLogger import SimpleLogger

def main():
    logger = SimpleLogger("dummy_agent")

    logger.debug("Parsing command line arguments")
    parser = argparse.ArgumentParser(description='Dummy PCAP Agent')
    parser.add_argument('-e', '--export', action='store_true', help='Export mode')
    parser.add_argument('-O', '--output-dir', help='Output directory')
    args = parser.parse_args()
    logger.debug(f"Arguments parsed: export={args.export}, output_dir={args.output_dir}")

    # Simulate some processing time
    logger.debug("Simulating processing time")
    time.sleep(0.1)

    # Generate random minutes of PCAP available (between 1000 and 1500 minutes)
    pcap_minutes = random.randint(1000, 1500)
    logger.debug(f"Generated random PCAP minutes: {pcap_minutes}")

    # Print EXACTLY the format that sensor_monitor.py expects
    logger.debug("Outputting PCAP minutes in expected format")
    print(f"AGENT_MINUTES_OF_PCAP_AVAILABLE {pcap_minutes}\n")

    logger.debug("Agent execution completed successfully")
    # Exit with success
    sys.exit(0)

if __name__ == "__main__":
    main()
