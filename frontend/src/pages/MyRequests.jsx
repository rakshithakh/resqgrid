import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, useCitizen, clearCitizen, mask, TYPE, clock } from '../lib'

export default function MyRequests() {
  const nav = useNavigate(),
    cit = useCitizen()
  const [data, setData] = useState(null),
    [error, setError] = useState('')
  useEffect(() => {
    if (!cit) {
      nav('/login/citizen?next=/my-requests')
      return
    }
    let alive = true
    const run = () =>
      api('/me/requests', { auth: 'citizen' })
        .then((d) => alive && (setData(d), setError('')))
        .catch((e) => alive && setError(e.message))
    run()
    const t = setInterval(run, 8000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [cit])
  if (!cit) return null
  return (
    <>
      <h1>My requests</h1>
      <p className="small">
        Signed in as {mask(cit.phone)}.{' '}
        <button className="linkbtn" onClick={clearCitizen}>
          Sign out
        </button>
      </p>
      {error && <p className="msg err">{error}</p>}
      {data && data.requests.length === 0 && (
        <p>
          No requests yet. <Link to="/report">Request relief</Link> or <Link to="/sms">send an SMS</Link>.
        </p>
      )}
      {data?.requests.map((r) => (
        <article key={r.ticket} className="receipt tight">
          <p className="ref">
            <b>{r.ticket}</b> <span className="tag">{r.source === 'sms' ? 'SMS' : 'Web'}</span>
          </p>
          <p className="big">{r.message}</p>
          <p className="small">
            {r.location} | {r.needs.map((t) => TYPE[t]).join(', ')} | received {clock(r.received_at)}
          </p>
          <p className="quote">{r.text}</p>
        </article>
      ))}
    </>
  )
}
