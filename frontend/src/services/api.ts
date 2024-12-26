import axios from 'axios';

// Debug logging function
const debug = (message: string, data?: any) => {
  const timestamp = new Date().toISOString();
  const logMessage = data 
    ? `[API] ${message} | ${JSON.stringify(data)}`
    : `[API] ${message}`;
  console.debug(`${timestamp} ${logMessage}`);
  // If we have a debug message handler from the app, use it
  const debugHandler = (window as any).addDebugMessage;
  if (typeof debugHandler === 'function') {
    debugHandler(logMessage);
  }
};

// Interfaces
export interface Sensor {
  name: string;
  fqdn: string;
  status: string;
  pcap_avail: number;
  totalspace: string;
  usedspace: string;
  last_update: string;
  version: string | null;
  location: string;
}

export interface Job {
  id: number;
  username: string;
  status: string;
  description: string;
  location: string;
  src_ip: string | null;
  dst_ip: string | null;
  event_time: string | null;
  start_time: string;
  end_time: string;
  started: string | null;
  completed: string | null;
  result: string | null;
  filename: string | null;
  analysis: string | null;
  tz: string;
  result_size: string | null;
  result_path: string | null;
  result_message: string | null;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  tasks: Task[];
}

export interface Task {
  id: number;
  job_id: number;
  task_id: string;
  sensor: string;
  status: string;
  pcap_size: string | null;
  temp_path: string | null;
  result_message: string | null;
  start_time: string | null;
  end_time: string | null;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface Admin {
  username: string;
  created_at: string;
  last_active: string;
}

export interface Location {
  site: string;
  name: string;
  latitude: number;
  longitude: number;
  description: string;
  color: string;
}

export interface ApiConnection {
  src_location: string;
  dst_location: string;
  packet_count: number;
  latest_seen: number;
  earliest_seen: number;
}

export interface JobSubmitData {
  location: string;
  params: {
    description?: string;
    src_ip?: string;
    dst_ip?: string;
    event_time?: string;
    start_time?: string;
    end_time?: string;
    tz: string;
  };
}

export interface HealthSummary {
  timestamp: string;
  duration_seconds: number;
  sensors: {
    total: number;
    online: number;
    offline: number;
    degraded: number;
  };
  devices: {
    total: number;
    online: number;
    offline: number;
    degraded: number;
  };
  metrics: {
    avg_pcap_minutes: number;
    avg_disk_usage_pct: number;
  };
  errors: string[];
  performance_metrics: Record<string, any>;
}

// Create axios instance
export const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Token refresh state
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
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor
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

// Add response interceptor
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      debug('Received 401 error, attempting token refresh', {
        url: originalRequest.url,
        isRefreshing
      });

      if (isRefreshing) {
        debug('Token refresh already in progress, queueing request');
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

      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        debug('No refresh token found, redirecting to login');
        processQueue(error);
        clearAuthData();
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        debug('Sending refresh token request');
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

        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
        originalRequest.headers['Authorization'] = `Bearer ${access_token}`;

        processQueue(null, access_token);
        isRefreshing = false;
        debug('Token refresh complete, retrying original request');

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

// API Service methods
const apiService = {
  // Auth
  async login(username: string, password: string) {
    debug('Attempting login', { username });
    const response = await api.post('/login', { username, password });
    const { access_token, refresh_token, role } = response.data;
    
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);
    localStorage.setItem('role', role);
    localStorage.setItem('isAdmin', role === 'admin' ? 'true' : 'false');
    localStorage.setItem('username', username);
    
    debug('Login successful', { role });
    return response.data;
  },

  async logout() {
    debug('Logging out');
    clearAuthData();
    window.location.href = '/login';
  },

  async refreshToken() {
    debug('Refreshing token');
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await refreshApi.post('/refresh', {}, {
      headers: {
        'Authorization': `Bearer ${refreshToken}`
      }
    });

    const { access_token, refresh_token, role } = response.data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);
    localStorage.setItem('role', role);
    localStorage.setItem('isAdmin', role === 'admin' ? 'true' : 'false');

    return response.data;
  },

  // Sensors
  async getSensors() {
    debug('Fetching sensors');
    const response = await api.get<{ sensors: Sensor[] }>('/sensors');
    debug(`Fetched ${response.data.sensors.length} sensors`);
    return response.data;
  },

  async addSensor(sensor: Sensor) {
    debug('Adding new sensor', sensor);
    const response = await api.post('/sensors', sensor);
    return response.data;
  },

  async getSensorDevices(sensorName: string) {
    debug(`Fetching devices for sensor: ${sensorName}`);
    const response = await api.get(`/sensors/${sensorName}/devices`);
    return response.data;
  },

  // Jobs
  async getJobs(params?: { username?: string }) {
    debug('Fetching jobs', params);
    const response = await api.get<{ jobs: Job[] }>('/jobs', { params });
    debug(`Fetched ${response.data.jobs.length} jobs`);
    return response.data.jobs;
  },

  async getJobDetails(jobId: number) {
    debug(`Fetching job details: ${jobId}`);
    const response = await api.get<Job>(`/jobs/${jobId}`);
    return response.data;
  },

  async getJobAnalysis(jobId: number) {
    debug(`Fetching job analysis: ${jobId}`);
    const response = await api.get(`/jobs/${jobId}/analysis`);
    return response.data;
  },

  async submitJob(jobData: JobSubmitData) {
    debug('Submitting job', jobData);
    // Ensure all undefined values are removed from the params object
    const cleanedParams = Object.fromEntries(
      Object.entries(jobData.params)
        .filter(([_, value]) => value !== undefined)
    );
    const cleanedData = {
      ...jobData,
      params: cleanedParams
    };
    debug('Cleaned job data', cleanedData);
    const response = await api.post('/jobs/submit', cleanedData);
    return response.data;
  },

  async cancelJob(jobId: number) {
    debug(`Cancelling job: ${jobId}`);
    await api.post(`/jobs/${jobId}/cancel`);
  },

  async deleteJob(jobId: number) {
    debug(`Deleting job: ${jobId}`);
    await api.delete(`/jobs/${jobId}`);
  },

  // Network
  async getLocations() {
    debug('Fetching network locations');
    const response = await api.get<{ locations: Location[] }>('/network/locations');
    debug(`Fetched ${response.data.locations.length} locations`);
    return response.data;
  },

  async getConnections() {
    debug('Fetching network connections');
    const response = await api.get<{ connections: ApiConnection[] }>('/network/connections');
    debug(`Fetched ${response.data.connections.length} connections`);
    return response.data;
  },

  // Admin
  async getAdmins() {
    debug('Fetching admin users');
    const response = await api.get<{ admins: Admin[] }>('/admin/users');
    return response.data.admins || [];
  },

  async addAdmin(username: string) {
    debug(`Adding admin user: ${username}`);
    await api.post('/admin/users', { username });
  },

  async removeAdmin(username: string) {
    debug(`Removing admin user: ${username}`);
    await api.delete(`/admin/users/${username}`);
  },

  // System
  async getHealth() {
    debug('Fetching health status');
    const response = await api.get('/health');
    return response.data;
  },

  async getStorage() {
    debug('Fetching storage status');
    const response = await api.get('/storage');
    return response.data;
  },

  async getLogs() {
    debug('Fetching logs');
    const response = await api.get('/logs');
    return response.data;
  },

  // Cache
  async clearCache(cacheType: string) {
    debug(`Clearing cache: ${cacheType}`);
    const response = await api.post('/admin/cache/clear', { type: cacheType });
    return response.data;
  },

  async refreshCache(cacheType: string) {
    debug(`Refreshing cache: ${cacheType}`);
    const response = await api.post('/admin/cache/refresh', { type: cacheType });
    return response.data;
  },

  // Preferences
  async getPreferences() {
    debug('Fetching user preferences');
    const response = await api.get('/preferences');
    return response.data;
  },

  async savePreferences(data: any) {
    debug('Saving user preferences', data);
    const response = await api.post('/preferences', data);
    return response.data;
  },

  async getHealthSummary(params?: { start_time?: string; end_time?: string }) {
    debug('Fetching health summary data', params);
    const queryParams = new URLSearchParams();
    if (params?.start_time) queryParams.append('start_time', params.start_time);
    if (params?.end_time) queryParams.append('end_time', params.end_time);
    const url = `/health/summary${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;
    const response = await api.get(url);
    return response.data;
  },
};

export default apiService; 