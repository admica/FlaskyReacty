import axios from 'axios';

const API_BASE_URL = '/api/v1';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Add request interceptor to add auth token
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Add response interceptor to handle token refresh
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;
        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;
            try {
                // Clear tokens and redirect to login
                localStorage.removeItem('token');
                window.location.href = '/login';
            } catch (refreshError) {
                return Promise.reject(refreshError);
            }
        }
        return Promise.reject(error);
    }
);

export interface LoginResponse {
    access_token: string;
    refresh_token: string;
    role: string;
}

export interface Sensor {
    name: string;
    status: string;
    pcap_avail: number;
    totalspace: number;
    last_update: string;
    fqdn?: string;
    usedspace?: number;
    location?: string;
}

export interface SensorSummary {
    total: number;
    online: number;
    byLocation: {
        location: string;
        total: number;
        online: number;
    }[];
}

export interface Job {
    id: number;
    username: string;
    description: string;
    sensor: string;
    src_ip: string;
    dst_ip: string;
    event_time: string;
    start_time: string;
    end_time: string;
    status: string;
    started: string;
    completed: string;
    result: string;
    filename: string;
    analysis: string;
    tz: string;
    created_at: string;
}

export interface SystemStatus {
    server_status: string;
    system_info: {
        cpu: {
            per_cpu: number[];
            average: number;
        };
        memory: {
            total: number;
            available: number;
            used: number;
            percent: number;
        };
        disk: {
            total: number;
            used: number;
            free: number;
            percent: number;
        };
        threads: {
            name: string;
            id: number;
            alive: boolean;
            daemon: boolean;
        }[];
    };
    application_stats: {
        active_jobs: number;
        queued_jobs: number;
        total_sensors: number;
        sensor_status: {
            online: number;
            offline: number;
            maintenance: number;
            total: number;
        };
        request_count: number;
    };
}

export interface ActiveUser {
    username: string;
    last_activity: string;
}

export interface Location {
    site: string;
    name: string;
    latitude: number;
    longitude: number;
    description: string;
}

export interface ApiConnection {
    src_location: string;
    dst_location: string;
    packet_count: number;
    latest_seen: number;
    earliest_seen: number;
}

export interface LocationsResponse {
    locations: Location[];
    cached: boolean;
    timestamp: string;
}

export interface ConnectionsResponse {
    connections: ApiConnection[];
    cached: boolean;
    timestamp: string;
}

export interface LogFile {
    name: string;
    size: number;
    modified: string;
}

export interface LogsResponse {
    files: LogFile[];
    timestamp: string;
}

const apiService = {
    login: async (username: string, password: string): Promise<LoginResponse> => {
        console.log('Attempting login for user:', username);
        try {
            const response = await api.post('/login', { username, password });
            console.log('Login response:', response.data);
            
            // Store tokens and user info
            localStorage.setItem('access_token', response.data.access_token);
            localStorage.setItem('refresh_token', response.data.refresh_token);
            localStorage.setItem('role', response.data.role);
            localStorage.setItem('isAdmin', response.data.role === 'admin' ? 'true' : 'false');
            localStorage.setItem('username', username);
            
            return response.data;
        } catch (error: any) {
            console.error('Login error:', error.response?.data || error.message);
            if (error.response?.data) {
                throw error.response.data;
            }
            throw error;
        }
    },

    setAuthToken: (token: string) => {
        console.log('Setting auth token');
        api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    },

    clearAuthToken: () => {
        console.log('Clearing auth token');
        delete api.defaults.headers.common['Authorization'];
    },

    getSensors: async (): Promise<{ sensors: Sensor[] }> => {
        try {
            const response = await api.get('/sensors');
            return response.data;
        } catch (error: any) {
            console.error('Error fetching sensors:', error.response?.data || error.message);
            throw error.response?.data || error;
        }
    },

    getSensorDetails: async (sensorName: string): Promise<Sensor> => {
        try {
            const response = await api.get(`/sensors/${sensorName}/status`);
            return response.data;
        } catch (error: any) {
            console.error('Error fetching sensor details:', error.response?.data || error.message);
            throw error.response?.data || error;
        }
    },

    getSensorDevices: async (sensorName: string): Promise<{ devices: { name: string; port: number; }[] }> => {
        try {
            const response = await api.get(`/sensors/${sensorName}/devices`);
            return response.data;
        } catch (error: any) {
            console.error('Error fetching sensor devices:', error.response?.data || error.message);
            const errorMessage = error.response?.data?.error || error.response?.data || error.message || 'Unknown error';
            throw errorMessage;
        }
    },

    refreshSensor: async (sensorName: string): Promise<void> => {
        try {
            await api.get(`/sensors/${sensorName}/status`);
        } catch (error: any) {
            console.error('Refresh sensor error:', error.response?.data || error.message);
            if (error.response?.data) {
                throw error.response.data;
            }
            throw error;
        }
    },

    logout: async (): Promise<void> => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('role');
        localStorage.removeItem('isAdmin');
        localStorage.removeItem('username');
        localStorage.removeItem('lastActivity');
    },

    getJobs: async (): Promise<Job[]> => {
        try {
            const response = await api.post('/jobs', {});
            return response.data;
        } catch (error: any) {
            console.error('Error fetching jobs:', error.response?.data || error.message);
            throw error.response?.data || error;
        }
    },

    getJobAnalysis: async (jobId: number): Promise<any> => {
        try {
            const response = await api.get(`/jobs/${jobId}/analysis`);
            return response.data;
        } catch (error: any) {
            console.error('Error fetching job analysis:', error.response?.data || error.message);
            throw error.response?.data || error;
        }
    },

    getNetworkLocations: async (): Promise<LocationsResponse> => {
        try {
            const response = await api.get<LocationsResponse>('/network/locations');
            return response.data;
        } catch (error: any) {
            console.error('Error fetching network locations:', error.response?.data || error.message);
            throw error.response?.data || error;
        }
    },

    getNetworkConnections: async (hours?: string): Promise<ConnectionsResponse> => {
        try {
            const url = hours ? `/network/connections?hours=${hours}` : '/network/connections';
            const response = await api.get<ConnectionsResponse>(url);
            return response.data;
        } catch (error: any) {
            console.error('Error fetching network connections:', error.response?.data || error.message);
            throw error.response?.data || error;
        }
    },

    getSystemStatus: async (): Promise<SystemStatus> => {
        try {
            const response = await api.get('/admin/system/status');
            return response.data;
        } catch (error: any) {
            console.error('Error fetching system status:', error.response?.data || error.message);
            throw error.response?.data || error;
        }
    },

    getActiveUsers: async (): Promise<{ users: ActiveUser[] }> => {
        try {
            const response = await api.get('/admin/users');
            return response.data;
        } catch (error: any) {
            console.error('Error fetching active users:', error.response?.data || error.message);
            throw error.response?.data || error;
        }
    },

    cancelJob: async (jobId: number): Promise<void> => {
        try {
            await api.post(`/jobs/${jobId}/cancel`);
        } catch (error: any) {
            console.error('Error cancelling job:', error.response?.data || error.message);
            throw error.response?.data || error;
        }
    },

    deleteJob: async (jobId: number): Promise<void> => {
        try {
            await api.delete(`/jobs/${jobId}`);
        } catch (error: any) {
            console.error('Error deleting job:', error.response?.data || error.message);
            throw error.response?.data || error;
        }
    },

    refreshToken: async (): Promise<LoginResponse> => {
        try {
            const response = await api.post('/refresh');
            // Update stored tokens
            localStorage.setItem('token', response.data.access_token);
            localStorage.setItem('refresh_token', response.data.refresh_token);
            return response.data;
        } catch (error: any) {
            console.error('Token refresh error:', error.response?.data || error.message);
            // If refresh fails, force logout
            localStorage.removeItem('token');
            localStorage.removeItem('refresh_token');
            window.location.href = '/login';
            throw error;
        }
    },

    // Health endpoints
    getHealth: async () => {
        try {
            console.log('Fetching health status...');
            const response = await api.get('/health');
            console.log('Health response:', response.data);
            return response.data;
        } catch (error: any) {
            console.error('Health check error:', {
                status: error.response?.status,
                data: error.response?.data,
                headers: error.response?.headers,
                config: {
                    url: error.config?.url,
                    method: error.config?.method,
                    headers: error.config?.headers
                }
            });
            throw error.response?.data || error;
        }
    },

    getVersion: async () => {
        try {
            const response = await api.get('/version');
            return response.data;
        } catch (error) {
            console.error('Version check error:', error);
            throw error;
        }
    },

    getStorage: async () => {
        try {
            console.log('Fetching storage status...');
            const response = await api.get('/storage');
            console.log('Storage response:', response.data);
            return response.data;
        } catch (error: any) {
            console.error('Storage check error:', {
                status: error.response?.status,
                data: error.response?.data,
                headers: error.response?.headers,
                config: {
                    url: error.config?.url,
                    method: error.config?.method,
                    headers: error.config?.headers
                }
            });
            throw error.response?.data || error;
        }
    },

    // Cache operations
    clearCache: async (cacheType: string) => {
        try {
            const response = await api.post('/api/v1/admin/cache/clear', { type: cacheType });
            return response.data;
        } catch (error) {
            console.error('Cache clear error:', error);
            throw error;
        }
    },

    refreshCache: async (cacheType: string) => {
        try {
            const response = await api.post('/api/v1/admin/cache/refresh', { type: cacheType });
            return response.data;
        } catch (error) {
            console.error('Cache refresh error:', error);
            throw error;
        }
    },

    getCacheMetrics: async () => {
        try {
            const response = await api.get('/api/v1/admin/cache/metrics');
            return response.data;
        } catch (error) {
            console.error('Cache metrics error:', error);
            throw error;
        }
    },

    analyzeStorage: async () => {
        const response = await api.post('/api/v1/storage/analyze');
        return response.data;
    },

    // Log endpoints
    getLogFiles: async () => {
        try {
            const response = await api.get('/logs/list');
            return response.data;
        } catch (error) {
            console.error('Log files list error:', error);
            throw error;
        }
    },

    getLogContent: async (filename: string, lines: number = 100) => {
        try {
            const response = await api.get(`/logs/content/${filename}`, {
                params: { lines }
            });
            return response.data;
        } catch (error) {
            console.error('Log content error:', error);
            throw error;
        }
    },

    streamLog: async (filename: string, callback: (line: string) => void) => {
        try {
            const response = await api.get(`/logs/stream/${filename}`, {
                responseType: 'text',
                onDownloadProgress: (progressEvent) => {
                    const lines = (progressEvent as any).currentTarget.response.split('\n');
                    callback(lines[lines.length - 1]);
                }
            });
            return response.data;
        } catch (error) {
            console.error('Log streaming error:', error);
            throw error;
        }
    },

    getLogs: async (): Promise<LogsResponse> => {
        try {
            console.log('Fetching logs...');
            const response = await api.get('/logs');
            console.log('Logs response:', response.data);
            return response.data;
        } catch (error: any) {
            console.error('Logs fetch error:', {
                status: error.response?.status,
                data: error.response?.data,
                headers: error.response?.headers,
                config: {
                    url: error.config?.url,
                    method: error.config?.method,
                    headers: error.config?.headers
                }
            });
            throw error.response?.data || error;
        }
    },

    submitJob: async (data: {
        sensor: string;
        src_ip?: string;
        dst_ip?: string;
        description?: string;
        start_time: string;
        end_time: string;
    }) => {
        try {
            // Only include IPs if they're not empty strings
            const jobData = {
                ...data,
                src_ip: data.src_ip?.trim() || null,
                dst_ip: data.dst_ip?.trim() || null,
            };

            const response = await api.post('/api/v1/submit', jobData);
            return response.data;
        } catch (error: any) {
            console.error('Job submission error:', error);
            throw error.response?.data || error;
        }
    }
};

export default apiService; 