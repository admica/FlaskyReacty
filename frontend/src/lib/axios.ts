import axios, { AxiosInstance } from 'axios';

// Debug logging function
const debug = (message: string, data?: any) => {
  const timestamp = new Date().toISOString();
  const logMessage = data 
    ? `[Axios] ${message} | ${JSON.stringify(data)}`
    : `[Axios] ${message}`;
  console.debug(`${timestamp} ${logMessage}`);
  // If we have a debug message handler from the app, use it
  const debugHandler = (window as any).addDebugMessage;
  if (typeof debugHandler === 'function') {
    debugHandler(logMessage);
  }
};

// Base axios instance creator for internal use
export const createAxiosInstance = (options = {}): AxiosInstance => {
  const instance = axios.create({
    baseURL: (import.meta.env.VITE_API_URL || 'https://localhost:3000') + '/api/v1',
    headers: {
      'Content-Type': 'application/json',
    },
    ...options
  });

  // Add basic auth interceptor
  instance.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
      debug('Adding auth token to request', { url: config.url });
    }
    return config;
  }, (error) => {
    debug('Request interceptor error', { error: error.message });
    return Promise.reject(error);
  });

  return instance;
}; 