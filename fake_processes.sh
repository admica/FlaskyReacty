#!/bin/bash

stop_processes() {
    echo "Stopping all fake processes..."
    pkill -f "fake_pcapCollect"
    pkill -f "fake_tcpdump"
    pkill -f "start_pcapCollect.sh"
    rm -f fake_pcapCollect fake_tcpdump
    echo "All fake processes stopped"
    exit 0
}

start_processes() {
    # Kill any existing fake processes
    pkill -f "fake_pcapCollect"
    pkill -f "fake_tcpdump"
    pkill -f "start_pcapCollect.sh"
    rm -f fake_pcapCollect fake_tcpdump

    # Create fake pcapCollect script
    cat > fake_pcapCollect << 'EOF'
#!/bin/bash
device=""
port=""

# Parse command line arguments
while (( "$#" )); do
  case "$1" in
    -d|--device)
      device=$2
      shift 2
      ;;
    -p|--port)
      port=$2
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

# Print process info for debugging
echo "Started fake_pcapCollect for device $device on port $port"

while true; do sleep 999999; done
EOF
    chmod +x fake_pcapCollect

    # Create fake tcpdump script
    cat > fake_tcpdump << 'EOF'
#!/bin/bash
echo "Started fake_tcpdump"
while true; do sleep 999999; done
EOF
    chmod +x fake_tcpdump

    # Start fake processes for each sensor

    # KSC1
    # Start the manager processes
    ./start_pcapCollect.sh &  # napa0 manager
    ./start_pcapCollect.sh &  # napa1 manager
    # Start the worker processes
    ./start_pcapCollect.sh napa0 12340 &  # napa0 workers
    ./start_pcapCollect.sh napa1 12341 &  # napa1 workers

    # GSFC1 (commented out for now)
    #./start_pcapCollect.sh &  # napa0 manager
    #./start_pcapCollect.sh &  # napa1 manager
    #./start_pcapCollect.sh napa0 12340 &  # napa0 workers
    #./start_pcapCollect.sh napa1 12341 &  # napa1 workers

    # GSFC2 (commented out for now)
    #./start_pcapCollect.sh &  # napa0 manager
    #./start_pcapCollect.sh napa0 12340 &  # napa0 workers
    #./fake_tcpdump -i eth0 &

    # JPL1 (commented out for now)
    #./start_pcapCollect.sh &  # napa0 manager
    #./start_pcapCollect.sh napa0 12340 &  # napa0 workers

    echo "All fake processes started."
    echo "To verify processes, run: ps -ef | grep -E \"pcapCollect|tcpdump\""
    echo "To stop all processes, run: $0 stop"
}

case "$1" in
    stop)
        stop_processes
        ;;
    start|"")
        start_processes
        ;;
    *)
        echo "Usage: $0 {start|stop}"
        exit 1
        ;;
esac 
