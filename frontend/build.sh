#!/bin/bash

# Default to prod if no argument provided
MODE=${1:-prod}

case $MODE in
  "dev")
    echo "Running in development mode..."
    export NODE_ENV="development"
    npm run dev
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
      sudo ln -s "$(pwd)/dist" /var/www/html/pcapserver
    fi
    ;;
  *)
    echo "Invalid mode: $MODE"
    echo "Usage: $0 [dev|build]"
    echo "Default: build"
    exit 1
    ;;
esac
