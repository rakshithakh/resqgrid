import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import Crumbs from '../components/Crumbs'
import { api, setOfficer } from '../lib'

export default function Login() {
  const nav = useNavigate()
  const [sp] = useSearchParams()
  const [f, setF] = useState({ username: '', password: '' })
  const [err, setErr] = useState(sp.get('expired') ? 'Your session expired. Please sign in again.' : '')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      const r = await api('/auth/login', { method: 'POST', body: f })
      setOfficer(r.token, r.user)
      nav('/control-room')
    } catch (x) {
      setErr(x.message)
    }
    setBusy(false)
  }
  return (
    <>
      <Crumbs trail={[['Login', '/login'], ['Officer']]} />
      <div className="login-wrap">
        <section className="login">
          <h1>Officer login</h1>
          <p className="small">For authorised control room staff. Activity on this system is logged.</p>
          <form onSubmit={submit} className="form" noValidate>
            <label>
              User ID
              <input
                value={f.username}
                onChange={(e) => setF({ ...f, username: e.target.value })}
                autoComplete="username"
                autoFocus
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={f.password}
                onChange={(e) => setF({ ...f, password: e.target.value })}
                autoComplete="current-password"
              />
            </label>
            {err && (
              <p className="msg err" role="alert">
                {err}
              </p>
            )}
            <button className="btn primary" disabled={busy || !f.username || !f.password}>
              {busy ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
        </section>
        <aside className="demo-creds">
          <h2>Demo access</h2>
          <p>This prototype has a sample account for judges and reviewers.</p>
          <table className="tbl">
            <tbody>
              <tr>
                <th scope="row">User ID</th>
                <td>
                  <code>controlroom</code>
                </td>
              </tr>
              <tr>
                <th scope="row">Password</th>
                <td>
                  <code>Relief@2026</code>
                </td>
              </tr>
            </tbody>
          </table>
          <button
            type="button"
            className="btn"
            onClick={() => setF({ username: 'controlroom', password: 'Relief@2026' })}
          >
            Fill demo credentials
          </button>
        </aside>
      </div>
    </>
  )
}
