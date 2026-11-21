import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, TYPE, clock } from '../lib'

export default function Track() {
  const [sp] = useSearchParams()
  const [ref, setRef] = useState(sp.get('ref') || '')
  const [r, setR] = useState(null)
  const [err, setErr] = useState('')
  async function go(e) {
    e?.preventDefault()
    setErr('')
    setR(null)
    try {
      setR(await api('/public/track/' + encodeURIComponent(ref.trim())))
    } catch (x) {
      setErr(x.message)
    }
  }
  const stage = !r ? -1 : r.eta_min != null ? 3 : r.status === 'verified' ? 2 : 1
  const stages = ['Received', 'Verification', 'In dispatch queue', 'Vehicle dispatched']
  return (
    <div className="narrow">
      <h1>Track a request</h1>
      <form onSubmit={go} className="form inline">
        <label>
          Reference number
          <input value={ref} onChange={(e) => setRef(e.target.value)} placeholder="RG-123456" />
        </label>
        <button className="btn primary" disabled={!ref.trim()}>
          Check status
        </button>
      </form>
      {err && (
        <p className="msg err" role="alert">
          {err}
        </p>
      )}
      {r && (
        <section className="receipt" aria-live="polite">
          <h2>{r.ticket}</h2>
          <ol className="stages">
            {stages.map((s, i) => (
              <li key={s} className={i < stage ? 'done' : i === stage ? 'now' : ''}>
                {s}
              </li>
            ))}
          </ol>
          <p className="big">{r.message}</p>
          <table className="tbl">
            <tbody>
              <tr>
                <th scope="row">Location</th>
                <td>{r.location}</td>
              </tr>
              <tr>
                <th scope="row">Needs</th>
                <td>{r.needs.map((t) => TYPE[t]).join(', ')}</td>
              </tr>
              <tr>
                <th scope="row">Received at</th>
                <td>{clock(r.received_at)}</td>
              </tr>
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}
