import { reactive } from 'vue'
import api from './api'

export const auth = reactive({ enabled: true, authenticated: false, csrf: '' })
export async function refreshSession() {
  try {
    const { data } = await api.get('/auth/session')
    auth.enabled = data.enabled
    auth.authenticated = data.authenticated
    auth.csrf = data.csrf_token || ''
  } catch (error) {
    auth.authenticated = false
    auth.csrf = ''
    if (error.response?.status !== 401) throw error
  }
}
export async function login(username, password) {
  const { data } = await api.post('/auth/login', { username, password }, {
    headers: { 'X-Requested-With': 'ai-project' }
  })
  auth.authenticated = true
  auth.csrf = data.csrf_token
}
export async function logout() {
  await api.post('/auth/logout')
  auth.authenticated = false
  auth.csrf = ''
}
api.interceptors.request.use(config => {
  if (auth.csrf && !['get', 'head', 'options'].includes(config.method)) {
    config.headers['X-CSRF-Token'] = auth.csrf
  }
  return config
})
api.interceptors.response.use(response => response, error => {
  if (error.response?.status === 401 && !error.config.url.startsWith('/auth/')) {
    auth.authenticated = false
    auth.csrf = ''
    window.dispatchEvent(new Event('auth-expired'))
  }
  return Promise.reject(error)
})
