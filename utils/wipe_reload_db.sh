#!/bin/bash

# Terminal color setup
if [ -t 1 ]; then
    YELLOW='\033[1;33m'
    BLUE='\033[1;34m'
    GREEN='\033[1;32m'
    RED='\033[1;31m'
    NC='\033[0m'
else
    YELLOW='' BLUE='' GREEN='' RED='' NC=''
fi

error_check() {
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ ERROR during $1 ]${NC}"
        exit 1
    fi
}

if [[ "$1" != "-f" ]]; then
    echo -e "${YELLOW}WARNING: This will delete and recreate the pcapdb database."
    echo -e "*** Press ENTER to continue or Ctrl+C to abort ***${NC}"
    read -r
fi

echo -e "${BLUE}[ PROCEEDING WITH DATABASE RECREATION ]${NC}"

POSTGRES_HOME=$(getent passwd postgres | cut -d: -f6)
PG_PASSWORD=${1:-postgres}

if ! sudo -u postgres test -f "$POSTGRES_HOME/.pgpass"; then
   echo -e "${BLUE}[ POSTGRES LINUX USER IS MISSING ~/.pgpass ]${NC}"
   sudo touch "$POSTGRES_HOME/.pgpass"
   error_check "pgpass creation"
   echo -e "${BLUE}[ WROTE $POSTGRES_HOME/.pgpass ]${NC}"
   sudo chown postgres:postgres "$POSTGRES_HOME/.pgpass"
   sudo chmod 600 "$POSTGRES_HOME/.pgpass"
   sudo -u postgres bash -c "echo 'localhost:5432:*:postgres:$PG_PASSWORD' > $POSTGRES_HOME/.pgpass"
   error_check "pgpass setup"
fi

echo -e "${BLUE}[ DELETING ]${NC}"
echo -e "${GREEN}"
sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='pcapdb';"|cat
error_check "connection termination"
sudo -u postgres psql -c "DROP DATABASE IF EXISTS pcapdb;"|cat
error_check "database deletion"
echo -e "${NC}"

echo -e "${BLUE}[ CREATING ]${NC}"
echo -e "${GREEN}"
sudo -u postgres psql -c "CREATE DATABASE pcapdb OWNER pcapuser;"|cat
error_check "database creation"
echo -e "${NC}"

echo -e "${BLUE}[ IMPORTING ]${NC}"
echo -e "${GREEN}"
sudo -u postgres psql pcapdb < /opt/pcapserver/sql/init_1.sql|cat
error_check "schema import"
sudo -u postgres psql pcapdb < /opt/pcapserver/sql/init_2.sql|cat
error_check "schema import"
sudo -u postgres psql pcapdb < /opt/pcapserver/sql/init_3.sql|cat
error_check "schema import"
sudo -u postgres psql pcapdb < /opt/pcapserver/sql/locations.sql|cat
error_check "locations import"
sudo -u postgres psql pcapdb < /opt/pcapserver/sql/init_4.sql|cat
error_check "schema import"
echo -e "${NC}"

echo -e "${BLUE}[ COMPLETE ]${NC}"
sudo -u postgres psql -c "\l pcapdb"|cat
sudo -u postgres psql pcapdb -c "\dt"|cat

echo -e "${BLUE}[ VERIFYING DATABASE SETUP ]${NC}"
echo -e "${GREEN}"

# Check tables
psql -U pcapuser -d pcapdb -c "\dt"|cat

# Check devices table
echo -e "\n${BLUE}[ VERIFYING DEVICES TABLE ]${NC}"
echo "Checking devices table structure..."
psql -U pcapuser -d pcapdb -c "\d+ devices"|cat

# Check sensor_health_summary table
echo -e "\n${BLUE}[ VERIFYING SENSOR_HEALTH_SUMMARY TABLE ]${NC}"
echo "Checking sensor_health_summary table structure..."
psql -U pcapuser -d pcapdb -c "\d+ sensor_health_summary"|cat

# Check maintenance_operations table
echo -e "\n${BLUE}[ VERIFYING MAINTENANCE_OPERATIONS TABLE ]${NC}"
echo "Checking maintenance_operations table structure..."
psql -U pcapuser -d pcapdb -c "\d+ maintenance_operations"|cat

# Check functions
echo -e "\n${BLUE}[ VERIFYING FUNCTIONS ]${NC}"
psql -U pcapuser -d pcapdb -c "\df"|cat

# Check user permissions
echo -e "\n${BLUE}[ VERIFYING USER PERMISSIONS ]${NC}"
psql -U pcapuser -d pcapdb -c "\du"|cat

echo -e "\n${BLUE}[ VERIFYING PARTITIONING ]${NC}"

# Check if subnet_location_map is partitioned
psql -U pcapuser -d pcapdb -c "\d+ subnet_location_map"|cat

# Check partition creation function
psql -U pcapuser -d pcapdb -c "\df+ create_hourly_partition"|cat

# List any existing partitions
psql -U pcapuser -d pcapdb -c "
SELECT c.relname as partition_name,
       pg_size_pretty(pg_total_relation_size(c.oid)) as size
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r' 
    AND n.nspname = 'public'
    AND c.relname ~ '^subnet_location_map_\d+$'
ORDER BY c.relname;"|cat

echo -e "${NC}"
