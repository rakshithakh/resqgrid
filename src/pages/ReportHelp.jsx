import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import OtpBox from '../components/OtpBox'
import { api, useCitizen, clearCitizen, mask, TYPE, STATUS } from '../lib'

const SAMPLES = [
  ['Hindi', 'Ward 5 mein 25 log chhat par fase hain, paani aur dawai chahiye. Bachche bhi hain'],
  ['Kannada', 'ವಾರ್ಡ್ 8 ನಲ್ಲಿ 30 ಜನ ಆಹಾರ ಮತ್ತು ನೀರು ಬೇಕು'],
  ['English', 'Need shelter and blankets for 12 families, elderly people with us'],
]
const LANG = {
  en: 'English',
  hi: 'Hindi',
  kn: 'Kannada',
  'hi-Latn': 'Hindi (Roman script)',
  'kn-Latn': 'Kannada (Roman script)',
}

export default function ReportHelp() {
  const cit = useCitizen()
  const [f, setF] = useState({ name: '', phone: '', ward: '', text: '' })
  const [skip, setSkip] = useState(false)
  const [loc, setLoc] = useState(null)
  const [locMsg, setLocMsg] = useState('')
  const [places, setPlaces] = useState([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [res, setRes] = useState(null)
  useEffect(() => {
    api('/config')
      .then((c) => setPlaces(c.places))
      .catch(() => {})
  }, [])
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const phone = cit ? cit.phone : f.phone

  function getLoc() {
    setLocMsg('Getting your location...')
    if (!navigator.geolocation)
      return setLocMsg('This browser cannot share location. You can still type your ward.')
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setLoc({ lat: p.coords.latitude, lng: p.coords.longitude, acc: Math.round(p.coords.accuracy) })
        setLocMsg('')
      },
      (e) =>
        setLocMsg(
          e.code === 1
            ? 'Location permission was denied. You can still type your ward.'
            : 'Could not get a location fix. Try near a window, or type your ward.',
        ),
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 },
    )
  }
  async function submit(e) {
    e.preventDefault()
    setErr('')
    setRes(null)
    if (!/^[6-9]\d{9}$/.test(phone)) return setErr('Enter a valid 10-digit mobile number.')
    if (!cit && !skip) return setErr('Verify your mobile number first, or tick the emergency option.')
    setBusy(true)
    try {
      setRes(
        await api('/public/report', {
          method: 'POST',
          body: {
            name: f.name,
            ward: f.ward,
            text: f.text,
            phone,
            token: cit ? cit.token : '',
            unverified: !cit && skip,
            lat: loc?.lat ?? null,
            lng: loc?.lng ?? null,
            acc: loc?.acc ?? null,
          },
        }),
      )
    } catch (x) {
      setErr(x.message)
      if (/expired|verify/i.test(x.message)) clearCitizen()
    }
    setBusy(false)
  }
  return (
    <div className="narrow">
      <h1>Request relief</h1>
      <p className="lead">
        Write in your own language. Say what you need, how many people, and where. No Aadhaar, password or
        account is needed. No signal for a code? <Link to="/sms">Send an SMS instead</Link>.
      </p>
      <form onSubmit={submit} className="form" noValidate>
        <fieldset>
          <legend>Step 1. Confirm your mobile number</legend>
          {cit ? (
            <p className="ok-box">
              <b>Signed in:</b> {mask(cit.phone)} is verified on this device.{' '}
              <button type="button" className="linkbtn" onClick={clearCitizen}>
                Use a different number
              </button>
            </p>
          ) : (
            <>
              <OtpBox phone={f.phone} setPhone={(p) => setF((x) => ({ ...x, phone: p }))} />
              <label className="check">
                <input type="checkbox" checked={skip} onChange={(e) => setSkip(e.target.checked)} />I cannot
                receive a code right now. Send as an emergency request. It will be checked by an officer and
                may take longer.
              </label>
            </>
          )}
        </fieldset>
        <fieldset>
          <legend>Step 2. Tell us what you need</legend>
          <div className="grid2">
            <label>
              Your name (optional)
              <input value={f.name} onChange={set('name')} autoComplete="name" />
            </label>
            <label>
              Nearest ward or landmark (optional)
              <select value={f.ward} onChange={set('ward')}>
                <option value="">Select if known</option>
                {places.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="locrow">
            {loc ? (
              <p className="ok-box">
                Location captured (accuracy about {loc.acc} m).{' '}
                <button type="button" className="linkbtn" onClick={() => setLoc(null)}>
                  Remove
                </button>
              </p>
            ) : (
              <button type="button" className="btn" onClick={getLoc}>
                Use my current location
              </button>
            )}
            <span className="small">
              Optional. Helps officers confirm where you are and speeds up verification. Only sent with this
              request.
            </span>
            {locMsg && (
              <span className="small" role="status">
                {locMsg}
              </span>
            )}
          </div>
          <label>
            What do you need? <span className="req">required</span>
            <textarea
              rows={5}
              value={f.text}
              onChange={set('text')}
              placeholder="Example: Ward 7, 40 people on a rooftop, need drinking water and medicine, children with us"
            />
          </label>
          <div className="samples">
            <span>Try a sample:</span>
            {SAMPLES.map(([l, t]) => (
              <button type="button" key={l} className="chip" onClick={() => setF({ ...f, text: t })}>
                {l}
              </button>
            ))}
          </div>
        </fieldset>
        {err && (
          <p className="msg err" role="alert">
            {err}
          </p>
        )}
        <button className="btn primary" disabled={busy || f.text.trim().length < 5}>
          {busy ? 'Sending...' : 'Send request'}
        </button>
      </form>
      {res && (
        <section className="receipt" aria-live="polite">
          <h2>Request received</h2>
          <p className="ref">
            Reference number <b>{res.ticket}</b>
          </p>
          <p className="small">
            Save this number. Track it on the <Link to={`/track?ref=${res.ticket}`}>tracking page</Link>
            {cit && (
              <>
                {' '}
                or under <Link to="/my-requests">My requests</Link>
              </>
            )}
            .
          </p>
          <h3>What the system understood</h3>
          <table className="tbl">
            <tbody>
              <tr>
                <th scope="row">Understood by</th>
                <td>{res.extraction_source === 'gemini' ? 'Gemini AI' : 'Built-in language rules'}</td>
              </tr>
              <tr>
                <th scope="row">Language</th>
                <td>{LANG[res.language] || res.language}</td>
              </tr>
              <tr>
                <th scope="row">Location</th>
                <td>
                  {res.label}
                  {res.gps === 1 && ' (confirmed by phone GPS)'}
                  {res.gps === -1 && ' (phone GPS does not match, an officer will check)'}
                </td>
              </tr>
              <tr>
                <th scope="row">Needs</th>
                <td>{res.types.map((t) => TYPE[t]).join(', ')}</td>
              </tr>
              <tr>
                <th scope="row">People</th>
                <td>{res.people || 'Not stated'}</td>
              </tr>
              <tr>
                <th scope="row">Mobile number</th>
                <td>{res.verified ? 'Verified' : 'Not verified. An officer will check this request.'}</td>
              </tr>
              <tr>
                <th scope="row">Status</th>
                <td>
                  {STATUS[res.status]}
                  {res.status === 'review' && ' (an officer will verify your request)'}
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}
