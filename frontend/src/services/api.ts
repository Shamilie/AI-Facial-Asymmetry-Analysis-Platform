import axios from 'axios';

export const api = axios.create({
  baseURL: '/api/v1',
  timeout: 60_000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('fa_access_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !window.location.pathname.startsWith('/login')) {
      localStorage.removeItem('fa_access_token');
      localStorage.removeItem('fa_user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export function withAuthTokenUrl(url: string): string {
  const token = localStorage.getItem('fa_access_token');
  if (!token) return url;
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}access_token=${encodeURIComponent(token)}`;
}

export function extractErrorMessage(err: any, fallback = 'An unexpected error occurred'): string {
  if (!err) return fallback;
  const data = err.response?.data;
  if (typeof data?.detail === 'string') return data.detail;
  if (typeof data?.error?.message === 'string') return data.error.message;
  if (typeof err.message === 'string') return err.message;
  return fallback;
}
