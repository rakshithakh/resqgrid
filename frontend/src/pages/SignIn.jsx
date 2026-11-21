import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import Crumbs from '../components/Crumbs'
import OtpBox from '../components/OtpBox'
import { useCitizen, clearCitizen, mask } from '../lib'

export default function SignIn() {
  const nav = useNavigate(),
    [sp] = useSearchParams(),
    cit = useCitizen()
  const [phone, setPhone] = useState('')
  const crumbs = <Crumbs trail={[['Login', '/login'], ['Citizen']]} />
  if (cit)
    return (
      <div className="narrow">
        {crumbs}
        <h1>You are signed in</h1>
        <p className="ok-box">
          Signed in as <b>{mask(cit.phone)}</b>. This device stays signed in for 7 days.
        </p>
        <div className="btn-row">
          <Link className="btn primary" to="/report">
            Request relief
          </Link>
          <Link className="btn" to="/my-requests">
            My requests
          </Link>
          <button className="btn" onClick={clearCitizen}>
            Sign out
          </button>
        </div>
      </div>
    )
  return (
    <>
      {crumbs}
      <div className="login-wrap">
        <section className="login">
          <h1>Citizen sign in</h1>
          <p className="small">
            No password, Aadhaar or account needed. Confirm your mobile number once and you can send requests
            and see your history for 7 days.
          </p>
          <div className="form">
            <OtpBox
              phone={phone}
              setPhone={setPhone}
              onVerified={() => nav(sp.get('next') || '/my-requests')}
            />
          </div>
        </section>
        <aside className="demo-creds">
          <h2>No signal for a code?</h2>
          <p>Codes need a mobile network. If you cannot receive one, you can still ask for help:</p>
          <ul className="plain">
            <li>
              Send an <Link to="/sms">SMS request</Link>. Your phone number is your identity, so no code is
              needed.
            </li>
            <li>
              Or use the emergency option on the <Link to="/report">request form</Link>.
            </li>
            <li>
              In immediate danger, call <b>112</b>.
            </li>
          </ul>
        </aside>
      </div>
    </>
  )
}
