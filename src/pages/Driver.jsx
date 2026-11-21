import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Crumbs from '../components/Crumbs'
import { api, getDriver, clearDriver } from '../lib'

export default function Driver() {
  const nav = useNavigate(),
    me = getDriver()
  const [mode, setMode] = useState('off'),
    [log, setLog] = useState([]),
    [err, setErr] = useState('')
  const timer = useRef(),
    watch = useRef(),
    last = useRef(0)
  const note = (t) => setLog((l) => [new Date().toLocaleTimeString('en-IN') + '  ' + t, ...l].slice(0, 8))
  useEffect(() => {
    if (!me) nav('/login/driver')
    return stop
  }, [])

  function stop() {
    clearInterval(timer.current)
    if (watch.current != null) navigator.geolocation?.clearWatch(watch.current)
    watch.current = null
    setMode('off')
  }
  const push = (lat, lng, acc) =>
    api('/driver/location', { method: 'POST', auth: 'driver', body: { lat, lng, acc } })
      .then(() => note(`sent ${lat.toFixed(5)}, ${lng.toFixed(5)}`))
      .catch((x) => {
        note(x.message)
        stop()
      })

  function share() {
    if (!navigator.geolocation) return setErr('This browser has no GPS support.')
    setErr('')
    setMode('gps')
    watch.current = navigator.geolocation.watchPosition(
      (p) => {
        if (Date.now() - last.current < 3000) return
        last.current = Date.now()
        push(p.coords.latitude, p.coords.longitude, p.coords.accuracy)
      },
      (e) => {
        setErr('Location error: ' + e.message)
        stop()
      },
      { enableHighAccuracy: true, maximumAge: 2000, timeout: 15000 },
    )
  }
  async function simulate() {
    setErr('')
    try {
      const { route } = await api('/driver/route', { auth: 'driver' })
      if (!route)
        return setErr('No route assigned to this vehicle yet. Load the scenario and wait for a plan.')
      const pts = route.points
      const step = Math.max(1, Math.floor(pts.length / 90))
      let i = 0
      setMode('sim')
      note(`simulating ${pts.length} route points`)
      timer.current = setInterval(() => {
        const p = pts[Math.min(i, pts.length - 1)]
        push(p[0], p[1], 5)
        i += step
        if (i > pts.length + step) {
          stop()
          note('route finished')
        }
      }, 1000)
    } catch (x) {
      setErr(x.message)
    }
  }
  if (!me) return null
  return (
    <div className="narrow">
      <Crumbs trail={[['Driver console']]} />
      <h1>Vehicle {me}</h1>
      <p className="small">The control room map shows this vehicle's real position while you share it.</p>
      {err && (
        <p className="msg err" role="alert">
          {err}
        </p>
      )}
      <div className="btn-row">
        {mode === 'off' ? (
          <>
            <button className="btn primary" onClick={share}>
              Share my live location
            </button>
            <button className="btn" onClick={simulate}>
              Simulate drive along my route (demo)
            </button>
          </>
        ) : (
          <button className="btn danger" onClick={stop}>
            Stop sharing
          </button>
        )}
        <button
          className="btn"
          onClick={() => {
            stop()
            clearDriver()
            nav('/')
          }}
        >
          Sign out
        </button>
      </div>
      <p className="ok-box">
        {mode === 'gps'
          ? 'Sharing live GPS from this phone.'
          : mode === 'sim'
            ? 'Simulating a drive along the planned route.'
            : 'Not sharing.'}
      </p>
      <pre className="logbox">{log.join('\n') || 'No updates sent yet.'}</pre>
    </div>
  )
}
