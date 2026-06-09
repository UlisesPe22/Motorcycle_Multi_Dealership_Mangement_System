import axios from 'axios'
import { getToken, clearAuth } from './store/auth'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

api.interceptors.request.use(config => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      clearAuth()
      window.location.href = '/login?expired=true'
    }
    return Promise.reject(error)
  }
)

export default api
