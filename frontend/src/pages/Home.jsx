import { Link } from 'react-router-dom'
import { usePoll, TYPE } from '../lib'
import RoleCards from '../components/RoleCards'

const STEPS = [
  ['You report', 'Send a message in English, Hindi or Kannada. No app or account is needed.'],
  [
    'We verify',
    'The system reads the message, finds the location and cross-checks it against other reports and flood data.',
  ],
  ['Routes are planned', 'Relief vehicles are assigned by urgency, load and which roads are open.'],
  ['An officer approves', 'The control room approves each dispatch. You can track your reference number.'],
]
const NOTICES = [
  ['15 Nov 2026', 'Control room operating round the clock during the flood advisory.'],
  ['15 Nov 2026', 'Old Bridge Road and the river crossings are monitored. Avoid flooded roads.'],
  ['14 Nov 2026', 'Relief depots on both river banks have been stocked with water, food and medical kits.'],
  ['14 Nov 2026', 'Reports sent more than three times in ten minutes are held for manual review.'],
]

export default function Home() {
  const { data: s, error } = usePoll('/public/status')
  const stat = (v, l) => (
    <div className="stat">
      <b>{v ?? '-'}</b>
      <span>{l}</span>
    </div>
  )
  return (
    <>
      <section className="hero">
        <div className="hero-text">
          <h1>Ask for flood relief. Track it. See where help is going.</h1>
          <p className="lead">
            Send one message about what you need and where you are. The control room verifies it and plans the
            fastest safe route for the nearest vehicle.
          </p>
          <div className="btn-row">
            <Link className="btn primary" to="/report">
              Request relief
            </Link>
            <Link className="btn" to="/track">
              Track a request
            </Link>
          </div>
          <p className="hint">You do not need to log in to ask for help.</p>
        </div>
        <aside className="glance" aria-label="Current situation">
          <h2>Current situation</h2>
          {error ? (
            <p className="msg err">Live figures unavailable. {error}</p>
          ) : (
            <div className="stats">
              {stat(s?.reports, 'Reports received')}
              {stat(s?.open_needs, 'Open relief needs')}
              {stat(s?.people_affected, 'People awaiting help')}
              {stat(s ? `${s.vehicles} / ${s.depots}` : null, 'Vehicles / depots')}
            </div>
          )}
          <p className="small">
            Figures refresh every few seconds.{' '}
            {s?.plan_approved ? 'Vehicles are on the road.' : 'A dispatch plan is being prepared.'}
          </p>
        </aside>
      </section>

      <RoleCards />

      <section>
        <h2 className="sec">What happens after you send a request</h2>
        <ol className="steps">
          {STEPS.map(([t, d], i) => (
            <li key={t}>
              <span className="n">{i + 1}</span>
              <div>
                <h3>{t}</h3>
                <p>{d}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="two">
        <div>
          <h2 className="sec">Services</h2>
          <ul className="svc">
            <li>
              <Link to="/report">Request relief</Link>
              <span>Water, food, medicine, rescue or shelter</span>
            </li>
            <li>
              <Link to="/track">Track a request</Link>
              <span>Use the reference number you received</span>
            </li>
            <li>
              <Link to="/status">Public status board</Link>
              <span>Open needs, closed roads, dispatch state</span>
            </li>
            <li>
              <Link to="/login">Login</Link>
              <span>Sign in as citizen, officer or driver</span>
            </li>
          </ul>
        </div>
        <div>
          <h2 className="sec">Notices</h2>
          <table className="tbl">
            <tbody>
              {NOTICES.map(([d, t]) => (
                <tr key={t}>
                  <th scope="row">{d}</th>
                  <td>{t}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="alert-strip" role="note">
        <strong>If someone is in immediate danger, call 112 first.</strong>
        <span>This portal supports coordination. It does not replace emergency services.</span>
      </section>
      {s && Object.keys(s.by_type).length > 0 && (
        <p className="small">
          Open needs by type:{' '}
          {Object.entries(s.by_type)
            .map(([k, v]) => `${TYPE[k]} ${v}`)
            .join(', ')}
          .
        </p>
      )}
    </>
  )
}
