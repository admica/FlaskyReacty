$ cat README.md
# Atlas Horizon

A comprehensive system for managing PCAP capture jobs, sensor monitoring, and network analysis.

## Version
- Version: 2.1.0
- Build Date: 2024-12-06

## Project Structure

### Backend Components
```
├── server.py             # Main API server implementation
├── core.py               # Shared resources and utilities
├── sensor_monitor.py     # Sensor monitoring service
├── partition_manager.py  # Database partition management
├── api/                  # API endpoint implementations
│   ├── auth.py           # Authentication endpoints
│   ├── jobs.py           # Job management
│   ├── sensors.py        # Sensor management
│   ├── health.py         # Health monitoring
│   ├── search.py         # Search functionality
│   └── admin.py          # Admin operations
├── sql/                  # Database schemas and migrations
│   ├── create_tables.sql    # Initial schema
│   ├── schema_updates.sql   # Schema migrations
│   ├── setup_partitions.sql # Partition setup
│   └── locations.sql        # Location data
├── utils/                   # Utility scripts
│   └── wipe_reload_db.sh    # Database reset tool
└── config.ini               # Configuration file
```

### Frontend Components (React + TypeScript + Vite)
```
frontend/
├── src/
│   ├── components/  # React components
│   │   ├── jobs/    # Job management UI
│   │   ├── sensors/ # Sensor monitoring UI
│   │   ├── network/ # Network visualization
│   │   └── common/  # Shared components
│   ├── services/    # API service layers
│   ├── routes/      # Route definitions
│   ├── lib/         # Utility functions
│   └── api/         # API client code
├── public/          # Static assets
└── dist/            # Production build
```

## Features

### Core Features
- Real-time sensor monitoring and health tracking
- Automated sensor discovery and status updates
- PCAP capture job management
- Network traffic analysis
- Subnet mapping and location tracking
- Time-based data partitioning for flexible scalability
- Health monitoring and system status

### Frontend Features
- Interactive sensor monitoring dashboard
- Real-time status updates
- Network traffic visualization
- Job submission and management interface
- Responsive design with dark/light themes
- Role-based access control

## Services

### Sensor Monitor Service
- Continuous sensor health monitoring
- Device status tracking
- PCAP availability monitoring
- Disk space monitoring
- Subnet mapping updates
- Performance metrics collection

### Database Management
- Automated partition management
- Time-based data retention
- Performance optimization
- Data cleanup and maintenance

## API Endpoints

### Sensor Management
- `GET /api/v1/sensors` - List all sensors
- `GET /api/v1/sensors/{name}/status` - Get sensor status
- `GET /api/v1/sensors/{name}/devices` - List sensor devices
- `GET /api/v1/sensors/activity` - Get sensor activity metrics

### Network Analysis
- `GET /api/v1/network/traffic` - Get network traffic summary
- `GET /api/v1/network/subnets` - List active subnets
- `GET /api/v1/network/locations` - Get location mappings

### System Management
- `GET /api/v1/system/health` - System health check
- `GET /api/v1/system/metrics` - System performance metrics
- `GET /api/v1/system/storage` - Storage status

## Database Schema

### Key Tables
- `sensors` - Sensor information and status
- `devices` - Device details and metrics
- `sensor_health_summary` - Health monitoring data
- `maintenance_operations` - System maintenance logs
- `subnet_location_map` - Network topology data

## Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 16+
- Node.js 18+ (for frontend)

### Backend Setup
```bash
# Create virtual environment
python3 -m venv venv_linux
source venv_linux/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
./utils/wipe_reload_db.sh -f

# Start sensor monitor service
python sensor_monitor.py
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

## Development

### Backend Development
```bash
# Run tests
python api_test.py
python test_server.py

# Monitor logs
tail -f logs/sensor_monitor.log
```

### Frontend Development
```bash
# Start development server
npm run dev

# Build for production
npm run build
```

## Deployment Options

### On-Premise Deployment
- Full stack deployment within customer infrastructure
- Server components and database hosted on customer hardware
- Sensor clients distributed across customer network
- Complete data sovereignty and security control
- Recommended for high-security environments

### Cloud-Hosted Option
- Core server and database hosted in secure cloud infrastructure
- Web console access provided to customer teams
- Sensor clients deployed on customer infrastructure
- Reduced maintenance overhead
- Automatic updates and scaling
- Built-in redundancy and backup

### Hybrid Deployment
- Flexible mix of cloud and on-premise components
- Customizable based on security and performance needs
- Data storage location configurable per requirements

### Hardware Requirements

#### Server (On-Premise)
- CPU: 8+ cores recommended
- RAM: 32GB minimum, 64GB+ recommended
- Storage: SSD with 1TB+ capacity
- Network: 10Gbps recommended

#### Sensor Clients
- CPU: 4+ cores
- RAM: 16GB minimum
- Storage: Based on retention requirements
- Network: 1Gbps minimum, 10Gbps recommended

### Security Considerations
- End-to-end encryption for all communications
- Role-based access control
- Data encryption at rest
- Regular security audits
- Compliance with industry standards

## About Atlas Labs

Atlas Labs is a pioneering network intelligence company founded in 2024. We specialize in developing enterprise-grade network monitoring, analysis, and security solutions that enable organizations to gain unprecedented visibility into their network infrastructure.

Our flagship product, Atlas Horizon, represents the culmination of extensive research and development in network packet capture, real-time analysis, and advanced visualization technologies. Through our innovative approach to network monitoring, we're helping organizations transform raw network data into actionable intelligence.

Atlas Labs: "Engineering Tomorrow's Network Intelligence"
Atlas Horizon: "Total Network Awareness"

### Our Mission
To empower organizations with comprehensive network visibility and intelligence through innovative, scalable solutions that evolve with tomorrow's challenges.

### Core Values
- Innovation in Network Intelligence
- Commitment to Security
- Enterprise Reliability
- Continuous Evolution

## License
Proprietary - All rights reserved
