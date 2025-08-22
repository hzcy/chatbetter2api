import axios from 'axios';

// 直接指向后端服务器地址，不再使用代理
const baseURL = import.meta.env.VITE_API_BASE_URL || '/api';

export const api = axios.create({
  baseURL,
  timeout: 10000,
}); 