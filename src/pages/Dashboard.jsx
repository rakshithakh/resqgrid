import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Emblem } from '../components/Layout'
import ThemeToggle from '../components/ThemeToggle'
import MapView, { ROUTE_COLORS } from '../components/MapView'
import { api, wsUrl, getToken, getUser, clearOfficer, TYPE, prioColor, prioLabel, mins, clock } from '../lib'

const ROWS = [
  ['Needs covered', (m) => `${m.needs_served} / ${m.needs_total}`, (m) => m.needs_served, 1],
  ['People reached', (m) => m.people_reached, (m) => m.people_reached, 1],
  [
    'Urgent needs reached (priority 40+)',
    (m) => `${m.high_priority_served} / ${m.high_priority_total}`,
    (m) => m.high_priority_served,
    1,
  ],
  ['Urgent needs, avg arrival (min)', (m) => m.avg_eta_high_min, (m) => m.avg_eta_high_min, -1],
  ['Priority-weighted arrival (min)', (m) => m.weighted_eta_min, (m) => m.weighted_eta_min, -1],
  ['Total vehicle time (min)', (m) => m.total_travel_min, (m) => m.total_travel_min, -1],
]

export default function Dashboard() {
  const nav = useNavigate(),
    user = getUser(),
    fetchedAt = useRef(0)
  const [geo, setGeo] = useState(null),
    [st, setSt] = useState(null),
    [live, setLive] = useState(false)
  const [tab, setTab] = useState('needs'),
    [ptab, setPtab] = useState('plan')
  const [placing, setPlacing] = useState(false),
    [kind, setKind] = useState('blocked'),
    [radius, setRadius] = useState(350)
  const [showBase, setShowBase] = useState(false),
    [busy, setBusy] = useState(''),
    [err, setErr] = useState('')
  const [ev, setEv] = useState(null),
    [loc, setLoc] = useState({}),
    [focus, setFocus] = useState(null)

  const load = useCallback(async () => {
    const s = await api('/state', { auth: true })
    fetchedAt.current = performance.now()
    setSt(s)
  }, [])
  useEffect(() => {
    if (!getToken()) {
      nav('/login/officer')
      return
    }
    api('/map', { auth: true })
      .then((g) => {
        setGeo(g)
        setRadius(g.default_radius)
      })
      .catch((e) => setErr(e.message))
    load().catch((e) => setErr(e.message))
    const t = setInterval(() => load().catch(() => {}), 6000)
    let ws,
      closed = false
    const open = () => {
      ws = new WebSocket(wsUrl())
      ws.onopen = () => setLive(true)
      ws.onmessage = () => load().catch(() => {})
      ws.onclose = () => {
        setLive(false)
        if (!closed) setTimeout(open, 2000)
      }
    }
    open()
    return () => {
      closed = true
      clearInterval(t)
      ws && ws.close()
    }
  }, [])

  const act = async (name, fn) => {
    setBusy(name)
    setErr('')
    try {
      await fn()
      await load()
    } catch (e) {
      setErr(e.message)
    }
    setBusy('')
  }
  const post = (p, body) => api(p, { method: 'POST', auth: true, body })
  const addHazard = (lat, lng, label) =>
    act('hazard', () =>
      post('/hazards', {
        lat,
        lng,
        radius,
        kind,
        label: label || (kind === 'blocked' ? 'Flooded road' : 'Waterlogged road'),
      }),
    )

  const plan = st?.plan
  const asg = useMemo(() => {
    const m = {}
    plan?.optimized.routes.forEach((r) =>
      r.stops.forEach((s) => (m[s.need_id] = { v: r.vehicle_id, eta: s.eta_s })),
    )
    return m
  }, [plan])
  const needs = useMemo(
    () => (st?.needs || []).filter((n) => n.status === 'verified').sort((a, b) => b.priority - a.priority),
    [st],
  )
  const review = (st?.needs || []).filter((n) => n.status === 'review')
  const state = !plan
    ? 'No plan yet'
    : st.stale
      ? 'Replanning'
      : plan.approved
        ? 'Dispatched'
        : 'Awaiting approval'

  return (
    <div className="dash">
      <div className="tricolor" aria-hidden="true">
        <i />
        <i />
        <i />
      </div>
      <header className="dash-top">
        <Link to="/" className="brand sm">
          <Emblem size={38} />
          <span>
            <small className="dept">Disaster Relief Coordination Cell</small>
            <strong>Control Room</strong>
          </span>
        </Link>
        <div className="dash-meta">
          <span className={`pill ${live ? 'ok' : 'off'}`}>{live ? 'Live' : 'Reconnecting'}</span>
          <span className={`pill st-${state.split(' ')[0].toLowerCase()}`}>{state}</span>
          <span className="who">{user?.title}</span>
          <a className="small" href="/driver" target="_blank" rel="noreferrer">
            Driver app
          </a>
          <ThemeToggle />
          <button
            className="btn sm"
            onClick={() => {
              clearOfficer()
              nav('/')
            }}
          >
            Sign out
          </button>
        </div>
      </header>
      {err && (
        <p className="msg err bar" role="alert">
          {err}
        </p>
      )}

      <div className="dash-grid">
        <section className="col left" aria-label="Needs">
          <div className="tabs" role="tablist">
            {[
              ['needs', `Needs (${needs.length})`],
              ['review', `Review (${review.length})`],
              ['eval', 'Accuracy'],
            ].map(([k, l]) => (
              <button
                key={k}
                role="tab"
                aria-selected={tab === k}
                className={tab === k ? 'on' : ''}
                onClick={() => setTab(k)}
              >
                {l}
              </button>
            ))}
          </div>
          <div className="scrollbox">
            {tab === 'needs' &&
              (needs.length === 0 ? (
                <p className="empty">
                  No verified needs yet. Send a test request from the Request relief page or by SMS, and it
                  appears here.
                </p>
              ) : (
                needs.map((n) => (
                  <article
                    key={n.id}
                    className="need clickable"
                    tabIndex={0}
                    role="button"
                    aria-label={`Show ${n.label} on map`}
                    onClick={() =>
                      n.lat &&
                      setFocus({ lat: n.gps_at?.lat ?? n.lat, lng: n.gps_at?.lng ?? n.lng, t: Date.now() })
                    }
                    onKeyDown={(e) =>
                      e.key === 'Enter' &&
                      n.lat &&
                      setFocus({ lat: n.gps_at?.lat ?? n.lat, lng: n.gps_at?.lng ?? n.lng, t: Date.now() })
                    }
                  >
                    <div className="need-h">
                      <b>{n.label}</b>
                      <span className="prio" style={{ background: prioColor(n.priority) }}>
                        {prioLabel(n.priority)} {n.priority}
                      </span>
                    </div>
                    <p className="small">
                      {n.types.map((t) => TYPE[t]).join(', ')} | {n.people} people
                      {n.vulnerable.length ? ` | ${n.vulnerable.join(', ')}` : ''}
                    </p>
                    <p className="small">
                      {n.reports} report{n.reports > 1 ? 's' : ''} | trust {Math.round(n.trust * 100)}%{' '}
                      {n.gps && <span className="tag">GPS confirmed</span>}{' '}
                      {n.sms && <span className="tag sms">SMS</span>}
                    </p>
                    <p className="msgline">
                      &ldquo;{n.summary}&rdquo; <span className="small">reported {clock(n.first_at)}</span>
                    </p>
                    {n.gps_at && (
                      <p className="small gpsline">
                        Phone GPS: {n.gps_at.lat.toFixed(5)}, {n.gps_at.lng.toFixed(5)}
                        {n.gps_at.acc != null && ` (about ${Math.round(n.gps_at.acc)} m)`}{' '}
                        <a
                          href={`https://www.google.com/maps?q=${n.gps_at.lat},${n.gps_at.lng}`}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                        >
                          Open in Google Maps
                        </a>
                      </p>
                    )}
                    {asg[n.id] ? (
                      <p className="served">
                        Vehicle {asg[n.id].v}, arrival in {mins(asg[n.id].eta)} min
                      </p>
                    ) : (
                      plan && <p className="unserved">Not covered by the current plan</p>
                    )}
                  </article>
                ))
              ))}
            {tab === 'review' &&
              (review.length === 0 ? (
                <p className="empty">Nothing waiting for review.</p>
              ) : (
                review.map((n) => (
                  <article key={n.id} className="need review">
                    <div className="need-h">
                      <b>{n.label}</b>
                      <span className="small">trust {Math.round(n.trust * 100)}%</span>
                    </div>
                    <p className="quote">{n.summary}</p>
                    <ul className="flags">
                      {n.flags.map((f) => (
                        <li key={f}>{f}</li>
                      ))}
                    </ul>
                    {!n.lat && (
                      <div className="inline-in">
                        <input
                          placeholder="e.g. Ward 5"
                          value={loc[n.id] || ''}
                          onChange={(e) => setLoc({ ...loc, [n.id]: e.target.value })}
                          aria-label="Set location"
                        />
                        <button
                          className="btn sm"
                          onClick={() =>
                            act('loc', () => post(`/needs/${n.id}/locate`, { place: loc[n.id] || '' }))
                          }
                        >
                          Set location
                        </button>
                      </div>
                    )}
                    <div className="btn-row tight">
                      <button
                        className="btn sm primary"
                        onClick={() => act('v', () => post(`/needs/${n.id}/verify`))}
                      >
                        Verify
                      </button>
                      <button
                        className="btn sm danger"
                        onClick={() => act('r', () => post(`/needs/${n.id}/reject`))}
                      >
                        Reject
                      </button>
                    </div>
                  </article>
                ))
              ))}
            {tab === 'eval' && (
              <div className="evalbox">
                <p className="small">
                  Runs the extractor on 14 labelled messages (English, Hindi, Kannada, Roman script) and
                  reports field-level accuracy.
                </p>
                <button
                  className="btn sm"
                  onClick={() => act('e', async () => setEv(await api('/eval/extraction', { auth: true })))}
                >
                  Run evaluation
                </button>
                {ev && (
                  <>
                    <table className="tbl">
                      <tbody>
                        <tr>
                          <th scope="row">Engine</th>
                          <td>{ev.source}</td>
                        </tr>
                        <tr>
                          <th scope="row">Need type</th>
                          <td>{Math.round(ev.need_type_accuracy * 100)}%</td>
                        </tr>
                        <tr>
                          <th scope="row">People count</th>
                          <td>{Math.round(ev.people_accuracy * 100)}%</td>
                        </tr>
                        <tr>
                          <th scope="row">Location</th>
                          <td>{Math.round(ev.location_accuracy * 100)}%</td>
                        </tr>
                      </tbody>
                    </table>
                    <p className="small">
                      The test set was written by the project team. Treat it as a regression check, not a
                      field-accuracy claim.
                    </p>
                  </>
                )}
              </div>
            )}
          </div>
        </section>

        <section className="col center" aria-label="Map">
          <div className="toolbar">
            <button
              className="btn sm"
              disabled={!!busy}
              onClick={() => act('s', () => post('/simulate/scenario'))}
            >
              Load sample data
            </button>
            <button
              className="btn sm danger"
              disabled={!!busy}
              onClick={() =>
                window.confirm('Delete ALL reports, needs, hazards and plans? This cannot be undone.') &&
                act('c', () => post('/admin/clear'))
              }
            >
              Clear all data
            </button>
            <button
              className={`btn sm ${placing ? 'primary' : ''}`}
              aria-pressed={placing}
              onClick={() => setPlacing(!placing)}
            >
              {placing ? 'Click map to place...' : 'Mark flood hazard'}
            </button>
            <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Hazard type">
              <option value="blocked">Road closed</option>
              <option value="slow">Slow (3x time)</option>
            </select>
            <select value={radius} onChange={(e) => setRadius(+e.target.value)} aria-label="Hazard radius">
              {(geo?.radii || [200, 350, 600, 900]).map((r) => (
                <option key={r} value={r}>
                  {r} m
                </option>
              ))}
            </select>
            {geo?.bridges.map((b) => (
              <button
                key={b.id}
                className="btn sm"
                disabled={!!busy}
                onClick={() => addHazard(b.lat, b.lng, `${b.label} flooded`)}
              >
                Flood {b.label}
              </button>
            ))}
          </div>
          {geo?.mode === 'synthetic' && (
            <p className="mapnote">
              Demo grid map: ward names and roads are fictional. Run <code>python -m app.fetch_osm</code> to
              use real streets.
            </p>
          )}
          <MapView
            geo={geo}
            st={st}
            showBase={showBase}
            placing={placing}
            fetchedAt={fetchedAt}
            focus={focus}
            onPlace={(ll) => {
              setPlacing(false)
              addHazard(ll.lat, ll.lng)
            }}
          />
          <div className="legend">
            <span>
              <i style={{ background: '#b3261e' }} />
              Critical
            </span>
            <span>
              <i style={{ background: '#d9730d' }} />
              High
            </span>
            <span>
              <i style={{ background: '#a07800' }} />
              Moderate
            </span>
            <span>
              <i style={{ background: '#2e7d32' }} />
              Routine
            </span>
            <span>
              <i className="dashed" />
              Under review
            </span>
            <span>
              <i className="gpsdot" />
              Phone GPS
            </span>
            <span>
              <i className="sq" />
              Depot
            </span>
          </div>
          {st?.hazards.length > 0 && (
            <div className="hz">
              {st.hazards.map((h) => (
                <span key={h.id} className="chip">
                  {h.label}
                  <button
                    aria-label={`Clear ${h.label}`}
                    onClick={() => act('d', () => api('/hazards/' + h.id, { method: 'DELETE', auth: true }))}
                  >
                    x
                  </button>
                </span>
              ))}
            </div>
          )}
        </section>

        <section className="col right" aria-label="Dispatch plan">
          <div className="tabs" role="tablist">
            {[
              ['plan', 'Plan'],
              ['orders', `Orders (${plan?.orders.length || 0})`],
              ['log', 'Activity'],
            ].map(([k, l]) => (
              <button
                key={k}
                role="tab"
                aria-selected={ptab === k}
                className={ptab === k ? 'on' : ''}
                onClick={() => setPtab(k)}
              >
                {l}
              </button>
            ))}
          </div>
          <div className="scrollbox">
            {!plan && <p className="empty">The agent will build a plan as soon as verified needs exist.</p>}
            {plan && ptab === 'plan' && (
              <>
                <p className="small">
                  Plan #{plan.id} | triggered by {plan.trigger} | solver: {plan.engine}
                </p>
                <p className="summary">{plan.summary}</p>
                <div className="btn-row tight">
                  <button
                    className="btn primary"
                    disabled={plan.approved || st.stale || busy}
                    onClick={() => act('a', () => post('/plan/approve'))}
                  >
                    {plan.approved ? 'Dispatch approved' : 'Approve dispatch'}
                  </button>
                  <button className="btn sm" onClick={() => act('p', () => post('/plan/solve'))}>
                    Replan now
                  </button>
                </div>
                {plan.approved && (
                  <p className="small">Vehicle movement on the map is sped up 40x for demonstration.</p>
                )}
                <table className="tbl cmp">
                  <thead>
                    <tr>
                      <th>Measure</th>
                      <th>ResQGrid</th>
                      <th>Nearest-truck</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ROWS.map(([l, show, val, dir]) => {
                      const a = val(plan.optimized.metrics),
                        b = val(plan.baseline.metrics)
                      const win = a === b ? 0 : (a - b) * dir > 0 ? 1 : -1
                      return (
                        <tr key={l}>
                          <th scope="row">{l}</th>
                          <td className={win > 0 ? 'win' : ''}>{show(plan.optimized.metrics)}</td>
                          <td className={win < 0 ? 'win' : ''}>{show(plan.baseline.metrics)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                <label className="check">
                  <input type="checkbox" checked={showBase} onChange={(e) => setShowBase(e.target.checked)} />{' '}
                  Show nearest-truck routes (dotted grey)
                </label>
                <h3>Vehicles</h3>
                {plan.optimized.routes.map((r, i) => (
                  <div key={r.vehicle_id} className="veh">
                    <b>
                      <i style={{ background: ROUTE_COLORS[i % 5] }} />
                      {r.vehicle_id} {st.live?.[r.vehicle_id] && <span className="tag live">LIVE GPS</span>}
                    </b>
                    <span className="small">{r.load_kg} kg</span>
                    <ol>
                      {r.stops.map((s) => (
                        <li key={s.need_id}>
                          {s.label}, {s.people} people, {mins(s.eta_s)} min
                        </li>
                      ))}
                    </ol>
                  </div>
                ))}
              </>
            )}
            {plan &&
              ptab === 'orders' &&
              (plan.orders.length === 0 ? (
                <p className="empty">Stock is sufficient for every assigned need.</p>
              ) : (
                plan.orders.map((o) => (
                  <article key={o.id} className="order">
                    <b>{o.id}</b> {o.kind}
                    <p>
                      {o.qty_kg} kg of {o.item}
                    </p>
                    <p className="small">
                      From {o.from} to {o.to}
                    </p>
                    <p className="small">{o.reason}</p>
                  </article>
                ))
              ))}
            {ptab === 'log' &&
              (st?.events || []).map((e) => (
                <p key={e.id} className={`log ${e.level}`}>
                  <time>{clock(e.ts)}</time> {e.msg}
                </p>
              ))}
          </div>
        </section>
      </div>
    </div>
  )
}
