# PCAP Server Frontend

## Development with Self-Signed Certificates

When developing locally with self-signed certificates, you'll need to:

1. Access the backend directly first:
   ```bash
   # Visit the backend URL and accept the certificate
   https://localhost:3000
   ```
   - Click "Advanced"
   - Click "Proceed to localhost (unsafe)"

2. Then access the frontend:
   ```bash
   # Visit the frontend URL and accept the certificate
   https://localhost:5173
   ```
   - Click "Advanced"
   - Click "Proceed to localhost (unsafe)"

3. After accepting both certificates, the application should work normally.

## Development Commands

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Structure

- `src/` - Source code
  - `api/` - API client configuration
  - `components/` - React components
  - `lib/` - Utility functions
  - `App.tsx` - Main application component
  - `main.tsx` - Application entry point
