import type { AxiosRequestConfig } from 'axios';
import axios from 'axios';
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});
// Attach JWT token to requests automatically
api.interceptors.request.use((config: AxiosRequestConfig) => {
    const token = localStorage.getItem('access_token');
    if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});
// Handle 401 responses (refresh token logic can go here later)
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('access_token');
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);
export default api;