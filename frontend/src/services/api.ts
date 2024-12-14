import api from '../api/axios';

// Helper function for consistent error logging
const logApiError = (context: string, error: any) => {
    console.error(`${context}:`, {
        status: error.response?.status,
        data: error.response?.data,
        headers: error.response?.headers,
        config: {
            url: error.config?.url,
            method: error.config?.method,
            headers: error.config?.headers
        }
    });
    return error.response?.data || error;
};

export interface LoginResponse {
    access_token: string;
    refresh_token: string;
    role: string;
}

export interface Sensor {
    name: string;
    status: string;
    location: string;
    fqdn?: string;
    pcap_avail?: number;
    totalspace?: string;
    usedspace?: string;
    last_update?: string;
    version?: string;
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

export interface Task {
    id: number;
    sensor: string;
    status: string;
    started: string | null;
    completed: string | null;
    result_message?: string;
}

export interface Job {
    id: number;
    username: string;
    description: string;
    location: string;
    src_ip: string | null;
    dst_ip: string | null;
    event_time: string | null;
    start_time: string;
    end_time: string;
    status: string;
    started: string | null;
    completed: string | null;
    result: string | null;
    filename: string | null;
    analysis: string | null;
    tz: string;
    tasks: Task[];
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
    color: string;
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

export interface SensorsResponse {
    sensors: Sensor[];
}

export interface Device {
    name: string;
    port: number;
    type: string;
    status: string;
    last_checked: string;
    runtime: number;
    workers: number;
    src_subnets: number;
    dst_subnets: number;
    uniq_subnets: number;
    avg_idle_time: number;
    avg_work_time: number;
    overflows: number;
    size: string;
    version: string;
    output_path?: string;
    proc?: string;
    stats_date?: string;
}

export interface DevicesResponse {
    count: number;
    devices: Device[];
    sensor: string;
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

    getSensors: async (): Promise<SensorsResponse> => {
        try {
            console.log('Fetching sensors with auth token');
            const response = await api.get('/sensors');
            return response.data;
        } catch (error: any) {
            throw logApiError('Error fetching sensors', error);
        }
    },

    getSensorDetails: async (sensorName: string): Promise<Sensor> => {
        try {
            const response = await api.get(`/sensors/${sensorName}/status`);
            return response.data;
        } catch (error: any) {
            throw logApiError('Error fetching sensor details', error);
        }
    },

    getSensorStatus: async (sensorName: string): Promise<any> => {
        try {
            const response = await api.get(`/sensors/${sensorName}/status`);
            return response.data;
        } catch (error: any) {
            throw logApiError('Error fetching sensor status', error);
        }
    },

    getSensorDevices: async (sensorName: string): Promise<DevicesResponse> => {
        try {
            console.log(`Fetching devices for sensor: ${sensorName}`);
            const response = await api.get(`/sensors/${sensorName}/devices`);
            console.log('Devices response:', response.data);
            return response.data;
        } catch (error: any) {
            throw logApiError(`Error fetching devices for sensor ${sensorName}`, error);
        }
    },

    refreshSensor: async (sensorName: string): Promise<void> => {
        try {
            await api.get(`/sensors/${sensorName}/status`);
        } catch (error: any) {
            throw logApiError(`Error refreshing sensor ${sensorName}`, error);
        }
    },

    logout: () => {
        // Clear all auth-related items from localStorage
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('role');
        localStorage.removeItem('isAdmin');
        localStorage.removeItem('username');
        
        // Clear auth header
        delete api.defaults.headers.common['Authorization'];
        
        // Redirect to login page
        window.location.href = '/login';
    },

    getJobs: async (params?: { username?: string }): Promise<Job[]> => {
        try {
            const response = await api.get('/jobs', { params });
            return response.data;
        } catch (error: any) {
            throw logApiError('Error fetching jobs', error);
        }
    },

    getJobDetails: async (jobId: number): Promise<Job> => {
        try {
            const response = await api.get(`/jobs/${jobId}`);
            return response.data;
        } catch (error: any) {
            throw logApiError(`Error fetching job details for job ${jobId}`, error);
        }
    },

    getJobAnalysis: async (jobId: number): Promise<any> => {
        try {
            const response = await api.get(`/jobs/${jobId}/analysis`);
            return response.data;
        } catch (error: any) {
            throw logApiError(`Error fetching job analysis for job ${jobId}`, error);
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
            throw logApiError(`Error cancelling job ${jobId}`, error);
        }
    },

    deleteJob: async (jobId: number): Promise<void> => {
        try {
            await api.delete(`/jobs/${jobId}`);
        } catch (error: any) {
            throw logApiError(`Error deleting job ${jobId}`, error);
        }
    },

    refreshToken: async (): Promise<LoginResponse> => {
        try {
            const response = await api.post('/refresh');
            // Update stored tokens
            localStorage.setItem('access_token', response.data.access_token);
            localStorage.setItem('refresh_token', response.data.refresh_token);
            return response.data;
        } catch (error: any) {
            console.error('Token refresh error:', error.response?.data || error.message);
            // If refresh fails, force logout
            localStorage.removeItem('access_token');
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
            throw logApiError('Health check error', error);
        }
    },

    getVersion: async () => {
        try {
            const response = await api.get('/version');
            return response.data;
        } catch (error: any) {
            throw logApiError('Version check error', error);
        }
    },

    getStorage: async () => {
        try {
            console.log('Fetching storage status...');
            const response = await api.get('/storage');
            console.log('Storage response:', response.data);
            return response.data;
        } catch (error: any) {
            throw logApiError('Storage check error', error);
        }
    },

    // Cache operations
    clearCache: async (cacheType: string) => {
        try {
            const response = await api.post('/admin/cache/clear', { type: cacheType });
            return response.data;
        } catch (error: any) {
            throw logApiError('Cache clear error', error);
        }
    },

    refreshCache: async (cacheType: string) => {
        try {
            const response = await api.post('/admin/cache/refresh', { type: cacheType });
            return response.data;
        } catch (error: any) {
            throw logApiError('Cache refresh error', error);
        }
    },

    getCacheMetrics: async () => {
        try {
            const response = await api.get('/admin/cache/metrics');
            return response.data;
        } catch (error: any) {
            throw logApiError('Cache metrics error', error);
        }
    },

    analyzeStorage: async () => {
        try {
            const response = await api.post('/storage/analyze');
            return response.data;
        } catch (error: any) {
            console.error('Storage analysis error:', {
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

    // Log endpoints
    getLogFiles: async () => {
        try {
            const response = await api.get('/logs/list');
            return response.data;
        } catch (error: any) {
            throw logApiError('Log files list error', error);
        }
    },

    getLogContent: async (filename: string, lines: number = 100) => {
        try {
            const response = await api.get(`/logs/content/${filename}`, {
                params: { lines }
            });
            return response.data;
        } catch (error: any) {
            throw logApiError('Log content error', error);
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
        } catch (error: any) {
            throw logApiError('Log streaming error', error);
        }
    },

    getLogs: async (): Promise<LogsResponse> => {
        try {
            console.log('Fetching logs...');
            const response = await api.get('/logs');
            console.log('Logs response:', response.data);
            return response.data;
        } catch (error: any) {
            throw logApiError('Logs fetch error', error);
        }
    },

    submitJob: async (jobData: {
        location: string;
        src_ip?: string;
        dst_ip?: string;
        start_time: string;
        end_time: string;
        description: string;
        event_time?: string;
        tz: string;
    }): Promise<{ job_id: number }> => {
        try {
            const response = await api.post('/submit', jobData);
            return response.data;
        } catch (error: any) {
            throw logApiError('Error submitting job', error);
        }
    },

    getLocations: async (): Promise<LocationsResponse> => {
        try {
            console.log('Fetching locations...');
            const response = await api.get('/network/locations');
            console.log('Locations response:', response.data);
            return response.data;
        } catch (error: any) {
            console.error('Error fetching locations:', error.response?.data || error.message);
            throw error.response?.data || error;
        }
    },

    getConnections: async (): Promise<ConnectionsResponse> => {
        try {
            console.log('Fetching connections...');
            const response = await api.get('/network/connections');
            console.log('Connections response:', response.data);
            return response.data;
        } catch (error: any) {
            console.error('Error fetching connections:', error.response?.data || error.message);
            throw error.response?.data || error;
        }
    }
};

export default apiService; 