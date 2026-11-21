import { useEffect, useState } from 'react'
import { NavLink, Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useSessions, clearCitizen, clearOfficer, clearDriver } from '../lib'
import ThemeToggle from './ThemeToggle'

export function Emblem({ size = 56 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="ResQGrid emblem">
      <circle cx="32" cy="32" r="30" fill="#fff" stroke="#16325c" strokeWidth="3" />
      <path d="M12 26h40M12 38h40M26 12v40M38 12v40" stroke="#c9d3e0" strokeWidth="2" />
      <path
        d="M10 40c6-6 10 6 16 0s10 6 16 0 8 4 12 0"
        fill="none"
        stroke="#1b6fb8"
        strokeWidth="4"
        strokeLinecap="round"
      />
      <path d="M32 11l5 9h-10z" fill="#e07b00" />
      <circle cx="32" cy="29" r="4" fill="#16325c" />
    </svg>
  )
}

export default function Layout() {
  const [size, setSize] = useState(() => Number(localStorage.getItem('rg_font') || 100))
  const loc = useLocation()
  const s = useSessions(),
    nav = useNavigate()
  const any = s.citizen || s.officer || s.driver
  const signOut = () => {
    clearCitizen()
    clearOfficer()
    clearDriver()
    nav('/')
  }
  useEffect(() => {
    document.documentElement.style.fontSize = size + '%'
    localStorage.setItem('rg_font', size)
  }, [size])
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [loc.pathname])
  const step = (d) => setSize((s) => Math.max(90, Math.min(130, s + d)))

  return (
    <>
      <a href="#main" className="skip">
        Skip to main content
      </a>
      <div className="topbar">
        <div className="wrap topbar-in">
          <span>
            {new Date().toLocaleDateString('en-IN', {
              weekday: 'long',
              day: 'numeric',
              month: 'long',
              year: 'numeric',
            })}
          </span>
          <span className="tools">
            <button onClick={() => step(-10)} aria-label="Decrease text size">
              A-
            </button>
            <button onClick={() => setSize(100)} aria-label="Default text size">
              A
            </button>
            <button onClick={() => step(10)} aria-label="Increase text size">
              A+
            </button>
            <span className="sep" />
            <ThemeToggle />
          </span>
        </div>
      </div>
      <div className="tricolor" aria-hidden="true">
        <i />
        <i />
        <i />
      </div>
      <header className="masthead">
        <div className="wrap masthead-in">
          <Link to="/" className="brand" aria-label="Home">
            <Emblem />
            <span>
              <small className="dept">Disaster Relief Coordination Cell</small>
              <strong>Flood Relief Coordination Portal</strong>
              <span className="langs">
                <span lang="hi">बाढ़ राहत समन्वय पोर्टल</span>
                <span lang="kn">ಪ್ರವಾಹ ಪರಿಹಾರ ಸಮನ್ವಯ ಪೋರ್ಟಲ್</span>
              </span>
            </span>
          </Link>
          <div className="emergency" role="note">
            <span>Life in danger?</span>
            <strong>Call 112</strong>
          </div>
        </div>
      </header>
      <nav className="mainnav" aria-label="Primary">
        <div className="wrap">
          <NavLink to="/" end>
            Home
          </NavLink>
          <NavLink to="/report">Request relief</NavLink>
          <NavLink to="/sms">Send by SMS</NavLink>
          <NavLink to="/track">Track a request</NavLink>
          <NavLink to="/status">Public status</NavLink>
          <span className="navright">
            {!any && (
              <NavLink to="/login" className="loginbtn">
                Login
              </NavLink>
            )}
            {s.citizen && <NavLink to="/my-requests">My requests</NavLink>}
            {s.officer && <NavLink to="/control-room">Control room</NavLink>}
            {s.driver && <NavLink to="/driver">Driver console</NavLink>}
            {any && (
              <button className="navbtn" onClick={signOut}>
                Sign out
              </button>
            )}
          </span>
        </div>
      </nav>
      <main id="main" className="wrap page">
        <Outlet />
      </main>
      <footer className="footer">
        <div className="wrap foot-grid">
          <div>
            <h3>About this portal</h3>
            <p>
              ResQGrid turns flood help requests into verified needs, then plans relief vehicle routes around
              closed roads. Every dispatch is approved by an officer.
            </p>
          </div>
          <div>
            <h3>Quick links</h3>
            <ul>
              <li>
                <Link to="/report">Request relief</Link>
              </li>
              <li>
                <Link to="/sms">Send by SMS</Link>
              </li>
              <li>
                <Link to="/track">Track a request</Link>
              </li>
              <li>
                <Link to="/status">Public status</Link>
              </li>
              <li>
                <Link to="/login">Login</Link>
              </li>
            </ul>
          </div>
        </div>
      </footer>
    </>
  )
}
