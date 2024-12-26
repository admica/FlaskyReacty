import axios from 'axios';

// Create axios instance for direct API calls
const api = axios.create({
  baseURL: (import.meta.env.VITE_API_URL || 'https://localhost:3000') + '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for authentication
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

export default api; 