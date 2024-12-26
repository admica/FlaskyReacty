$ cat README.md
# PCAP Server & Sensors Infrastructure

A comprehensive system for managing PCAP capture jobs, sensor monitoring, and network analysis.

## Version
- Version: 3.0.0
- Build Date: 2024-12-11

## Project Structure

### Backend Components (Flask + Python)
```
├── server.py             # Main API server implementation
├── core.py              # Shared resources and utilities
├── sensor_monitor.py    # Sensor monitoring service
├── partition_manager.py # Database partition management
├── api/                 # API endpoint implementations
│   ├── auth.py          # Authentication endpoints
│   ├── jobs.py          # Job management
│   ├── sensors.py       # Sensor management
│   ├── preferences.py   # User preferences
│   ├── health.py        # Health monitoring
│   ├── search.py        # Search functionality
│   ├── network.py       # Network operations
│   ├── analytics.py     # Analytics endpoints
│   ├── storage.py       # Storage management
│   └── admin.py         # Admin operations
├── sql/                 # Database schemas and migrations
│   ├── init_1.sql       # Core schema
│   ├── init_2.sql       # Sensor schema
│   ├── init_3.sql       # Triggers
│   ├── init_5.sql       # Jobs schema
│   ├── init_6_network_mapping.sql  # Jobs schema
│   └── init_7_user_preferences.sql # User preferences
├── utils/              # Utility scripts
│   └── wipe_reload_db.sh # Database reset tool
└── config.ini          # Configuration file
```

### Frontend Components (React + TypeScript + Vite)
```
frontend/
├── src/
│   ├── components/       # React components
│   │   ├── admin/       # Admin interface
│   │   │   ├── AdminPage.tsx
│   │   │   ├── UsersPage.tsx
│   │   │   └── LogViewer.tsx
│   │   ├── auth/        # Authentication
│   │   │   ├── LoginPage.tsx
│   │   │   └── SessionTimeoutProvider.tsx
│   │   ├── dashboard/   # Main dashboard
│   │   ├── jobs/        # Job management
│   │   │   ├── JobsPage.tsx
│   │   │   └── JobAnalysis.tsx
│   │   ├── layout/      # Layout components
│   │   │   └── AppLayout.tsx
│   │   ├── network/     # Network visualization
│   │   │   └── NetworkPage.tsx
│   │   ├── preferences/ # User preferences
│   │   │   └── PreferencesPage.tsx
│   │   ├── sensors/     # Sensor monitoring
│   │   │   └── SensorsPage.tsx
│   │   └── ui/          # Base UI components
│   │       ├── avatar.tsx
│   │       ├── button.tsx
│   │       ├── card.tsx
│   │       ├── dropdown-menu.tsx
│   │       ├── input.tsx
│   │       ├── label.tsx
│   │       └── tabs.tsx
│   ├── services/        # API service layers
│   ├── hooks/           # Custom React hooks
│   ├── lib/             # Utility functions
│   │   └── utils.ts     # Shared utilities
│   └── api/             # API client code
├── public/              # Static assets
└── dist/                # Production build
```

## Tech Stack

### Backend
- Python 3.11+
- Flask 3.1 with blueprints
- Flask-SocketIO 5.4.1 (WebSocket support)
- Redis 5 (for token mgmt and caching)
- JWT for authentication
- PostgreSQL 16 with raw SQL (no ORM)
- asyncpg 0.30 (async database operations)
- Scapy 2.6.1 (packet analysis)
- simpleLogger (custom logging)
- eventlet (async networking)

### Frontend
- React 18.2
- TypeScript 5.2
- Vite 5.0
- Mantine 7.3 (core UI components)
  - @mantine/core - Base components
  - @mantine/hooks - Custom hooks
  - @mantine/dates - Date/time components
  - @mantine/notifications - Toast notifications
  - @mantine/modals - Modal dialogs
- Radix UI (low-level primitives)
  - Avatar
  - Dropdown Menu
  - Label
  - Slot
  - Tabs
- shadcn/ui (component patterns)
- Tailwind CSS with plugins
  - tailwind-merge
  - tailwindcss-animate
- Icon Libraries
  - @tabler/icons-react
  - lucide-react
- React Router 6.20
- Three.js and react-globe.gl (for network visualization)
- Axios for API calls
- WebSocket client for real-time updates
- date-fns for date manipulation

## Features

### Core Features
- Real-time sensor monitoring and health tracking
- Automated sensor discovery and status updates
- PCAP capture job management
- Network traffic analysis
- Subnet mapping and location tracking
- Time-based data partitioning for flexible scalability
- Health monitoring and system status
- User preferences and customization
- Role-based access control with admin capabilities
- WebSocket-based real-time updates
- Redis-based caching and token management

### Frontend Features
- Interactive sensor monitoring dashboard
- Real-time status updates via WebSocket
- 3D network traffic visualization
- Job submission and management interface
- Responsive design with dark/light themes
- Role-based access control
- Session timeout management
- User preferences with avatar support
- Admin dashboard with system metrics
- Real-time health monitoring
- Toast notifications for user feedback
- Modal dialogs for complex interactions
- Date/time picking for job scheduling

## Services

### Sensor Monitor Service
- Continuous sensor health monitoring
- Device status tracking
- PCAP availability monitoring
- Disk space monitoring
- Subnet mapping updates
- Performance metrics collection
- WebSocket event broadcasting
- Real-time status updates

### Database Management
- Automated partition management
- Time-based data retention
- Performance optimization
- Data cleanup and maintenance
- Connection pooling
- Transaction management
- Async operations support

## API Endpoints

### Authentication
- `POST /api/v1/login` - User authentication
- `POST /api/v1/refresh` - Refresh JWT token
- `POST /api/v1/logout` - User logout

### Sensor Management
- `GET /api/v1/sensors` - List all sensors
- `GET /api/v1/sensors/{name}/status` - Get sensor status
- `GET /api/v1/sensors/{name}/devices` - List sensor devices
- `GET /api/v1/sensors/activity` - Get sensor activity metrics
- `GET /api/v1/locations` - Get available locations

### Job Management
- `GET /api/v1/jobs` - List all jobs
- `POST /api/v1/jobs` - Submit new job
- `GET /api/v1/jobs/{id}` - Get job details
- `GET /api/v1/jobs/{id}/tasks` - List job tasks
- `GET /api/v1/jobs/{id}/analysis` - Get job analysis

### Network Analysis
- `GET /api/v1/network/traffic` - Get network traffic summary
- `GET /api/v1/network/subnets` - List active subnets
- `GET /api/v1/network/locations` - Get location mappings
- `POST /api/v1/network/locations/clear-cache` - Clear location cache

### System Management
- `GET /api/v1/health` - Basic health check
- `GET /api/v1/health/summary` - Detailed health summary
- `GET /api/v1/admin/system/status` - System status (admin only)
- `GET /api/v1/admin/storage` - Storage status (admin only)

### User Management
- `GET /api/v1/preferences` - Get user preferences
- `PUT /api/v1/preferences` - Update preferences
- `GET /api/v1/admin/users` - List users (admin only)
- `POST /api/v1/admin/users` - Add user (admin only)

## Database Schema

### Core Tables
- `admin_users` - Admin user management
- `admin_audit_log` - Admin action auditing
- `user_preferences` - User settings and preferences
- `user_sessions` - Active user sessions

### Sensor Management
- `sensors` - Sensor information and status
- `devices` - Device details and metrics
- `sensor_status_history` - Status change tracking
- `sensor_health_summary` - Health monitoring data
- `maintenance_operations` - System maintenance logs

### Job Management
- `jobs` - PCAP capture job details
- `tasks` - Individual sensor tasks
- `locations` - Site locations and metadata

### Network Data
- `subnet_location_map` - Network topology data
- Location-specific tables (dynamically created):
  - `loc_src_{location}` - Source traffic data
  - `loc_dst_{location}` - Destination traffic data

## Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 16+
- Redis 5+
- Node.js 18+ (for frontend)
- OpenLDAP development libraries (for LDAP authentication)

### Backend Setup
```bash
# Start in app base directory
cd /opt/pcapserver

# Create virtual environment
python3 -m venv venv_linux
source venv_linux/bin/activate

# Install system dependencies
sudo dnf install python3-devel openldap-devel -y

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Configure environment
cp config.ini.example config.ini
# Edit config.ini with your settings

# Initialize database
./utils/wipe_reload_db.sh -f

# Start backend server
./server.py

# Start sensor monitor service (in a separate terminal)
./sensor_monitor.py
```

### Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start development server
npm run dev

# For production build
npm run build
```

## Development

### Backend Development
```bash
# Monitor logs
tail -f /opt/pcapserver/logs/*.log

# Run tests
python -m pytest tests/

# Check code style
flake8 api/
mypy api/

# Format code
black api/
```

### Frontend Development
```bash
# Start development server with hot reload
npm run dev

# Type checking
npm run type-check

# Lint code
npm run lint

# Format code
npm run format

# Build for production
npm run build
```

## Deployment

### Production Deployment

#### Backend Deployment
1. System Requirements:
   - 4+ CPU cores
   - 8GB+ RAM
   - 100GB+ storage
   - RHEL8+ or Ubuntu 22.04 LTS

2. Installation:
   ```bash
   # Install system dependencies
   sudo apt-get update
   sudo apt-get install python3.11 python3.11-dev
   sudo apt-get install postgresql-16 redis-server
   sudo apt-get install libldap2-dev libsasl2-dev

   # Configure PostgreSQL
   sudo -u postgres createuser pcapuser
   sudo -u postgres createdb pcapdb

   # Configure Redis
   sudo systemctl enable redis-server
   sudo systemctl start redis-server
   ```

3. Application Setup:
   ```bash
   # Clone repository
   git clone <url>/pcapserver.git /opt/pcapserver
   cd /opt/pcapserver

   # Set up Python environment
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

   # Configure application
   cp config.ini.example config.ini
   # Edit config.ini with production settings
   ```

4. Service Configuration:
   ```bash
   # Install systemd service files
   sudo cp deploy/pcapserver.service /etc/systemd/system/
   sudo cp deploy/pcapmonitor.service /etc/systemd/system/

   # Start services
   sudo systemctl enable pcapserver pcapmonitor
   sudo systemctl start pcapserver pcapmonitor
   ```

#### Frontend Deployment
1. Build the frontend:
   ```bash
   cd frontend
   npm install
   npm run build
   ```

2. Configure web server (nginx example):
   ```nginx
   server {
       listen 443 ssl http2;
       server_name pcapserver.example.com;

       ssl_certificate /etc/ssl/certs/pcapserver.crt;
       ssl_certificate_key /etc/ssl/private/pcapserver.key;

       root /opt/pcapserver/frontend/dist;
       index index.html;

       # API proxy
       location /api {
           proxy_pass https://localhost:3000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
           proxy_cache_bypass $http_upgrade;
       }

       # WebSocket proxy
       location /socket.io {
           proxy_pass https://localhost:3000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "Upgrade";
           proxy_set_header Host $host;
       }

       # Static files
       location / {
           try_files $uri $uri/ /index.html;
       }
   }
   ```

### Security Considerations
- Enable SSL/TLS encryption for all communications
- Configure proper firewall rules
- Set up fail2ban for brute force protection
- Regular security updates
- Implement proper backup strategy
- Monitor system logs
- Use strong passwords and key-based authentication
- Regular security audits
- Compliance with security standards

### Monitoring
- Set up log aggregation
- Configure system monitoring
- Enable performance metrics collection
- Set up alerts for critical events
- Monitor disk usage
- Track system resources
- Monitor database performance
- Check service health status

# License

This repository contains proprietary software. Unauthorized use, distribution, or reproduction is strictly prohibited. All rights reserved.
