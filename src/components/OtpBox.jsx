import { useState } from 'react'
import { api, setCitizen } from '../lib'

export default function OtpBox({ phone, setPhone, onVerified }) {
  const [otp, setOtp] = useState({ sent: false, code: '', demo: '' })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  async function send() {
    setErr('')
    if (!/^[6-9]\d{9}$/.test(phone)) return setErr('Enter a valid 10-digit mobile number.')
    setBusy(true)
    try {
      const r = await api('/public/otp/request', { method: 'POST', body: { phone } })
      setOtp({ sent: true, code: '', demo: r.demo_code || '' })
    } catch (x) {
      setErr(x.message)
    }
    setBusy(false)
  }
  async function check() {
    setErr('')
    setBusy(true)
    try {
      const r = await api('/public/otp/verify', { method: 'POST', body: { phone, code: otp.code } })
      const s = { phone: r.phone, token: r.token, exp: Date.now() + r.days * 864e5 }
      setCitizen(s)
      onVerified && onVerified(s)
    } catch (x) {
      setErr(x.message)
    }
    setBusy(false)
  }
  return (
    <div className="otpbox">
      <label>
        Mobile number
        <span className="row">
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value.replace(/\D/g, ''))}
            inputMode="numeric"
            maxLength={10}
            autoComplete="tel"
            placeholder="10 digits"
          />
          <button type="button" className="btn" disabled={busy || phone.length !== 10} onClick={send}>
            {otp.sent ? 'Resend code' : 'Send code'}
          </button>
        </span>
      </label>
      {otp.sent && (
        <>
          {!otp.demo && (
            <p className="ok-box">
              A code was sent by SMS to the number ending {phone.slice(-3)}. It can take up to a minute. Not
              received? Press Resend, or <a href="/sms">send an SMS request</a> instead.
            </p>
          )}
          {otp.demo && (
            <p className="sms-demo">
              <b>Demo SMS:</b> your code is <code>{otp.demo}</code>. In production this arrives by text
              message.
            </p>
          )}
          <label>
            6-digit code
            <span className="row">
              <input
                value={otp.code}
                onChange={(e) => setOtp({ ...otp, code: e.target.value.replace(/\D/g, '') })}
                inputMode="numeric"
                maxLength={6}
                autoComplete="one-time-code"
              />
              <button
                type="button"
                className="btn primary"
                disabled={busy || otp.code.length !== 6}
                onClick={check}
              >
                Verify
              </button>
            </span>
          </label>
        </>
      )}
      {err && (
        <p className="msg err" role="alert">
          {err}
        </p>
      )}
    </div>
  )
}
