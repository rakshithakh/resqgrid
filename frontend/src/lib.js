import { useEffect, useState } from 'react'

export const getToken = () => sessionStorage.getItem('rg_token')
export const getUser = () => JSON.parse(sessionStorage.getItem('rg_user') || 'null')
// When the website and server are on different hosts (Vercel + Render), set VITE_API_URL at build time.
const API = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
export const wsUrl = () =>
  (API
    ? API.replace(/^http/, 'ws')
    : (location.protocol === 'https:' ? 'wss' : 'ws') + '://' + location.host) + '/ws'
const ping = () => window.dispatchEvent(new Event('rg-auth'))
export const getOfficer = () => (getToken() ? getUser() : null)
export const setOfficer = (token, user) => {
  sessionStorage.setItem('rg_token', token)
  sessionStorage.setItem('rg_user', JSON.stringify(user))
  ping()
}
export const clearOfficer = () => {
  sessionStorage.removeItem('rg_token')
  sessionStorage.removeItem('rg_user')
  ping()
}
export const getDriver = () => (sessionStorage.getItem('rg_driver') ? sessionStorage.getItem('rg_vid') : null)
export const setDriver = (token, vid) => {
  sessionStorage.setItem('rg_driver', token)
  sessionStorage.setItem('rg_vid', vid)
  ping()
}
export const clearDriver = () => {
  sessionStorage.removeItem('rg_driver')
  sessionStorage.removeItem('rg_vid')
  ping()
}

const CKEY = 'rg_reporter'
export const getCitizen = () => {
  try {
    const s = JSON.parse(localStorage.getItem(CKEY))
    return s && s.exp > Date.now() ? s : null
  } catch {
    return null
  }
}
export const setCitizen = (s) => {
  localStorage.setItem(CKEY, JSON.stringify(s))
  window.dispatchEvent(new Event('rg-auth'))
}
export const clearCitizen = () => {
  localStorage.removeItem(CKEY)
  window.dispatchEvent(new Event('rg-auth'))
}
export function useCitizen() {
  const [c, setC] = useState(getCitizen())
  useEffect(() => {
    const f = () => setC(getCitizen())
    window.addEventListener('rg-auth', f)
    return () => window.removeEventListener('rg-auth', f)
  }, [])
  return c
}
export function useSessions() {
  const read = () => ({ citizen: getCitizen(), officer: getOfficer(), driver: getDriver() })
  const [s, setS] = useState(read)
  useEffect(() => {
    const f = () => setS(read())
    window.addEventListener('rg-auth', f)
    return () => window.removeEventListener('rg-auth', f)
  }, [])
  return s
}
export const mask = (p) => (p ? p.slice(0, 2) + 'XXXXX' + p.slice(7) : '')

export async function api(path, { method = 'GET', body, auth = false } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (auth === 'citizen') headers.Authorization = 'Bearer ' + (getCitizen()?.token || '')
  else if (auth === 'driver') headers.Authorization = 'Bearer ' + (sessionStorage.getItem('rg_driver') || '')
  else if (auth) headers.Authorization = 'Bearer ' + getToken()
  let r
  try {
    r = await fetch(API + '/api' + path, { method, headers, body: body ? JSON.stringify(body) : undefined })
  } catch {
    throw new Error(
      'Cannot reach the server. If it was idle (free hosting) it may be waking up: wait a minute and refresh. Running locally? Check the backend is on port 8000.',
    )
  }
  if (r.status === 401 && auth === 'citizen') {
    clearCitizen()
    throw new Error('Please sign in again.')
  }
  if (r.status === 401 && auth === 'driver') {
    clearDriver()
    throw new Error('Driver session expired. Sign in again.')
  }
  if (r.status === 401 && auth) {
    clearOfficer()
    window.location.href = '/login/officer?expired=1'
    throw new Error('Session expired')
  }
  let d
  try {
    d = await r.json()
  } catch {
    throw new Error('The server returned a non-JSON response. Set VITE_API_URL to the deployed backend URL, then redeploy.')
  }
  if (!r.ok)
    throw new Error(
      typeof d.detail === 'string'
        ? d.detail
        : d.detail?.[0]?.msg ||
            ([502, 503, 504].includes(r.status)
              ? 'The server is waking up (free hosting). Wait about a minute and try again.'
              : 'Request failed'),
    )
  return d
}

export const TYPE = {
  water: 'Drinking water',
  food: 'Food',
  medical: 'Medical',
  rescue: 'Rescue',
  shelter: 'Shelter',
  other: 'Other',
}
export const STATUS = { verified: 'Verified', review: 'Under review', rejected: 'Rejected' }
export const prioColor = (p) => (p >= 60 ? '#b3261e' : p >= 40 ? '#d9730d' : p >= 20 ? '#a07800' : '#2e7d32')
export const prioLabel = (p) => (p >= 60 ? 'Critical' : p >= 40 ? 'High' : p >= 20 ? 'Moderate' : 'Routine')
export const mins = (s) => Math.round(s / 60)
export const clock = (ts) =>
  new Date(ts * 1000).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

export function usePoll(path, ms = 5000) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let alive = true
    const run = () =>
      api(path)
        .then((d) => {
          if (alive) {
            setData(d)
            setError('')
          }
        })
        .catch((e) => alive && setError(e.message))
    run()
    const t = setInterval(run, ms)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [path, ms])
  return { data, error }
}
