#!/bin/bash

# Default to prod if no argument provided
MODE=${1:-prod}

# Base directory for the project
BASE_DIR="/opt/pcapserver"

case $MODE in
  "dev")
    echo "Running in development mode..."
    export NODE_ENV="development"
    npm run dev
    ;;
  "reset")
    echo "Resetting Apache config hostname to placeholder..."
    sed -i 's/.*SetEnvIf Origin.*/    SetEnvIf Origin "^https:\/\/(VAR_PRODUCTION\.DOMAIN)$" ORIGIN=$0/' "${BASE_DIR}/etc/99-pcapserver.conf"
    echo "Apache config restored to placeholder value."
    ;;
  "build"|"prod"|"production")
    echo "Running production build..."
    export NODE_ENV="production"
    npm run build
    
    # Ensure the Apache directory exists and is writable
    if [ -L "/var/www/html/pcapserver" ]; then
      echo "Symlink to dist directory exists, skipping."
    else
      echo "Creating symlink to dist directory"
      sudo ln -s "${BASE_DIR}/frontend/dist" /var/www/html/pcapserver
    fi

    # Update Apache config with hostname
    echo "Updating Apache config with hostname..."
    sed -i "s/VAR_PRODUCTION\.DOMAIN/$(hostname)/g" "${BASE_DIR}/etc/99-pcapserver.conf"
    sudo systemctl reload apache2
    ;;
  *)
    echo "Invalid mode: $MODE"
    echo "==========================="
    echo "Usage: $0 [dev|build|reset]"
    echo "  dev   - Run in development mode"
    echo "  build - Build for production"
    echo "  reset - Reset Apache config to use placeholder"
    echo "Default: build"
    echo "==========================="
    exit 1
    ;;
esac
