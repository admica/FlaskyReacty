import axios from 'axios';

// Debug logging function
const debug = (message: string, data?: any) => {
  const timestamp = new Date().toISOString();
  const logMessage = data 
    ? `[Auth] ${message} | ${JSON.stringify(data)}`
    : `[Auth] ${message}`;
  console.debug(`${timestamp} ${logMessage}`);
  // If we have a debug message handler from the app, use it
  const debugHandler = (window as any).addDebugMessage;
  if (typeof debugHandler === 'function') {
    debugHandler(logMessage);
  }
};

const api = axios.create({
  baseURL: (import.meta.env.VITE_API_URL || 'https://localhost:3000') + '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Flag to prevent multiple refresh attempts
let isRefreshing = false;
let failedQueue: any[] = [];

const processQueue = (error: any, token: string | null = null) => {
  debug(`Processing queued requests (${failedQueue.length} requests)${error ? ' with error' : ''}`);
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Create a separate axios instance for refresh requests
const refreshApi = axios.create({
  baseURL: (import.meta.env.VITE_API_URL || 'https://localhost:3000') + '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
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

// Add response interceptor to handle errors and token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If the error is 401 and we haven't tried refreshing yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      debug('Received 401 error, attempting token refresh', {
        url: originalRequest.url,
        isRefreshing
      });

      if (isRefreshing) {
        debug('Token refresh already in progress, queueing request');
        // If we're already refreshing, add this request to the queue
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(token => {
            debug('Retrying queued request with new token', { url: originalRequest.url });
            originalRequest.headers['Authorization'] = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch(err => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;
      debug('Starting token refresh process');

      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        debug('No refresh token found, redirecting to login');
        // No refresh token available, redirect to login
        processQueue(error);
        clearAuthData();
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        debug('Sending refresh token request');
        // Attempt to refresh the token
        const response = await refreshApi.post('/refresh', {}, {
          headers: {
            'Authorization': `Bearer ${refreshToken}`
          }
        });

        const { access_token, refresh_token, role } = response.data;
        debug('Token refresh successful', { role });
        
        localStorage.setItem('access_token', access_token);
        localStorage.setItem('refresh_token', refresh_token);
        localStorage.setItem('role', role);
        localStorage.setItem('isAdmin', role === 'admin' ? 'true' : 'false');

        // Update auth header
        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
        originalRequest.headers['Authorization'] = `Bearer ${access_token}`;

        // Process queued requests
        processQueue(null, access_token);
        isRefreshing = false;
        debug('Token refresh complete, retrying original request');

        // Retry the original request
        return api(originalRequest);
      } catch (refreshError: any) {
        debug('Token refresh failed', { 
          error: refreshError.message,
          status: refreshError.response?.status,
          data: refreshError.response?.data 
        });
        processQueue(refreshError);
        clearAuthData();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

const clearAuthData = () => {
  debug('Clearing all auth data');
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('role');
  localStorage.removeItem('isAdmin');
  localStorage.removeItem('username');
  delete api.defaults.headers.common['Authorization'];
};

export default api;
