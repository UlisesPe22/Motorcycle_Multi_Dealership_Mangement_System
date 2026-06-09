const TOKEN_KEY = 'bajaj_token'
const USER_KEY  = 'bajaj_user'

export function saveAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function getUser() {
  const raw = localStorage.getItem(USER_KEY)
  return raw ? JSON.parse(raw) : null
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function isAuthenticated() {
  return !!getToken()
}

const INTERFACE_KEY = 'bajaj_interface'

export function saveInterface(role) {
  localStorage.setItem(INTERFACE_KEY, role)
}

export function getSavedInterface() {
  return localStorage.getItem(INTERFACE_KEY) || null
}
