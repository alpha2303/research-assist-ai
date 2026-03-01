import axios from 'axios';
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { emitToast } from './toastEvents';

/**
 * Centralized API client configuration
 * Base URL is read from environment variable VITE_API_BASE_URL
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/** Retry configuration */
const MAX_RETRIES = 1;
const RETRY_DELAY_MS = 2000;

/** Check if an error is retryable (network error or 5xx). */
function isRetryable(error: unknown): boolean {
  if (!axios.isAxiosError(error)) return false;
  // Network errors (no response)
  if (!error.response) return true;
  // Server errors
  return error.response.status >= 500;
}

// Extend AxiosRequestConfig to track retry count
interface RetryConfig extends InternalAxiosRequestConfig {
  __retryCount?: number;
}

// Create axios instance with default configuration
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 seconds
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for adding auth tokens (future use)
apiClient.interceptors.request.use(
  (config) => {
    // Future: Add authentication token here
    // const token = localStorage.getItem('authToken');
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for handling errors globally (with auto-retry)
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    return response;
  },
  async (error) => {
    const config = error.config as RetryConfig | undefined;

    // ── Auto-retry for retryable errors ──────────────────────────────
    if (config && isRetryable(error)) {
      const retryCount = config.__retryCount ?? 0;
      if (retryCount < MAX_RETRIES) {
        config.__retryCount = retryCount + 1;
        await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
        return apiClient(config);
      }
    }

    // ── Build user-friendly message ──────────────────────────────────
    let userMessage = 'An unexpected error occurred.';

    if (error.response) {
      const data = error.response.data;
      if (data?.message && typeof data.message === 'string') {
        userMessage = data.message;
      } else if (typeof data?.error === 'string') {
        userMessage = data.error;
      }
      console.error('API Error:', error.response.status, data);
    } else if (error.request) {
      userMessage = 'Network error \u2014 the server may be unreachable.';
      console.error('Network Error: No response received');
    } else {
      userMessage = error.message || userMessage;
      console.error('Request Error:', error.message);
    }

    // Emit toast for server errors (5xx) and network failures.
    const status = error.response?.status;
    if (!status || status >= 500) {
      emitToast({ type: 'error', message: userMessage });
    }

    return Promise.reject(error);
  }
);

/**
 * Generic API request wrapper
 */
export const api = {
  get: <T = unknown>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> => {
    return apiClient.get<T>(url, config);
  },

  post: <T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> => {
    return apiClient.post<T>(url, data, config);
  },

  put: <T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> => {
    return apiClient.put<T>(url, data, config);
  },

  delete: <T = unknown>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> => {
    return apiClient.delete<T>(url, config);
  },

  patch: <T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> => {
    return apiClient.patch<T>(url, data, config);
  },
};

export default apiClient;
