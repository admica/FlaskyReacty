#!/bin/bash

# Set environment variables for production build
export VITE_API_URL="/api"
export NODE_ENV="production"

# Run the build
npm run build 