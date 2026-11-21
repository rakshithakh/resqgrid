import { Link } from 'react-router-dom'

const I = {
  width: 30,
  height: 30,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.7,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
}
const ROLES = [
  {
    to: '/login/citizen',
    title: 'Citizen',
    text: 'Request relief, share your location, track requests and see your history.',
    how: 'Mobile number and one-time code',
    icon: (
      <svg {...I}>
        <circle cx="12" cy="8" r="3.5" />
        <path d="M5 20c0-3.9 3.1-6 7-6s7 2.1 7 6" />
      </svg>
    ),
  },
  {
    to: '/login/officer',
    title: 'Control room officer',
    text: 'Verify reports, review routes and approve dispatch.',
    how: 'User ID and password',
    icon: (
      <svg {...I}>
        <path d="M12 3l8 3v6c0 4.5-3.2 7.8-8 9-4.8-1.2-8-4.5-8-9V6z" />
        <path d="M9 12l2 2 4-4" />
      </svg>
    ),
  },
  {
    to: '/login/driver',
    title: 'Relief vehicle driver',
    text: 'Share live location and follow your assigned route.',
    how: 'Vehicle and PIN',
    icon: (
      <svg {...I}>
        <path d="M3 16V7h11v9M14 10h4l3 3v3h-7" />
        <circle cx="7" cy="17.5" r="1.8" />
        <circle cx="17" cy="17.5" r="1.8" />
      </svg>
    ),
  },
]

export default function RoleCards({ heading = 'Sign in as' }) {
  return (
    <section aria-labelledby="signin-h">
      <h2 id="signin-h" className="sec">
        {heading}
      </h2>
      <div className="roles">
        {ROLES.map((r) => (
          <Link key={r.to} to={r.to} className="role">
            <span className="role-ic">{r.icon}</span>
            <span className="role-tx">
              <b>{r.title}</b>
              <small>{r.text}</small>
              <em>{r.how}</em>
            </span>
            <span className="role-go" aria-hidden="true">
              &rsaquo;
            </span>
          </Link>
        ))}
      </div>
      <p className="small">
        You do not need to sign in to ask for help. Use <Link to="/report">Request relief</Link> or{' '}
        <Link to="/sms">Send by SMS</Link>.
      </p>
    </section>
  )
}
