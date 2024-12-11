#!/bin/bash

# This script simulates the start_pcapCollect.sh that would run on a sensor
# It can run in two modes:
# 1. Manager mode (no args) - Just sleeps to simulate the manager process
# 2. Worker mode (device + port args) - Starts multiple worker processes

if [ $# -eq 0 ]; then
    # Manager mode - just sleep
    echo "Started pcapCollect manager process"
    while true; do sleep 999999; done
else
    # Worker mode - start multiple processes
    device=$1
    port=$2

    # Start multiple worker processes
    for i in {1..6}; do
        ./fake_pcapCollect -d "$device" -s 2G -w 4 -p "$port" &
    done
fi
