import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Crumbs from '../components/Crumbs'
import { api, getDriver, setDriver } from '../lib'

export default function DriverLogin() {
  const nav = useNavigate()
  const [cfg, setCfg] = useState(null)
  const [vid, setVid] = useState(''),
    [pin, setPin] = useState(''),
    [err, setErr] = useState(''),
    [busy, setBusy] = useState(false)
  useEffect(() => {
    if (getDriver()) nav('/driver')
    api('/config')
      .then((c) => {
        setCfg(c)
        setVid(c.vehicles[0]?.id || '')
      })
      .catch((e) => setErr(e.message))
  }, [])
  async function submit(e) {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      const r = await api('/driver/login', { method: 'POST', body: { vehicle_id: vid, pin } })
      setDriver(r.token, vid)
      nav('/driver')
    } catch (x) {
      setErr(x.message)
    }
    setBusy(false)
  }
  return (
    <>
      <Crumbs trail={[['Login', '/login'], ['Driver']]} />
      <div className="login-wrap">
        <section className="login">
          <h1>Driver sign in</h1>
          <p className="small">
            For relief vehicle crews. After sign in you can share this phone's live location with the control
            room.
          </p>
          <form onSubmit={submit} className="form" noValidate>
            <label>
              Vehicle
              <select value={vid} onChange={(e) => setVid(e.target.value)}>
                {(cfg?.vehicles || []).map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              PIN
              <input
                type="password"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                inputMode="numeric"
                autoComplete="off"
              />
            </label>
            {err && (
              <p className="msg err" role="alert">
                {err}
              </p>
            )}
            <button className="btn primary" disabled={busy || !pin || !vid}>
              {busy ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
        </section>
        {cfg?.demo && (
          <aside className="demo-creds">
            <h2>Demo access</h2>
            <p>
              Any vehicle works with PIN <code>1234</code>.
            </p>
            <button type="button" className="btn" onClick={() => setPin('1234')}>
              Fill demo PIN
            </button>
          </aside>
        )}
      </div>
    </>
  )
}
