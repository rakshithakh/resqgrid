import { useEffect, useRef, useState } from 'react'
import { api } from '../lib'

const SAMPLES = [
  'WARD 7 40 PEOPLE NEED WATER AND MEDICINE',
  'Ward 5 mein 25 log chhat par fase hain, bachao',
  'STATUS',
  'HELP',
]

export default function SmsPage() {
  const [cfg, setCfg] = useState(null)
  const [num, setNum] = useState('9876543210')
  const [text, setText] = useState('')
  const [msgs, setMsgs] = useState([
    {
      me: false,
      t: 'Relief helpline. Text what you need, how many people and where. Text HELP for examples.',
    },
  ])
  const [busy, setBusy] = useState(false)
  const end = useRef()
  useEffect(() => {
    api('/config')
      .then(setCfg)
      .catch(() => {})
  }, [])
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'nearest' })
  }, [msgs])
  async function send(t = text) {
    if (!t.trim() || busy) return
    setMsgs((m) => [...m, { me: true, t }])
    setText('')
    setBusy(true)
    try {
      const r = await api('/public/sms-demo', { method: 'POST', body: { sender: num, text: t } })
      setMsgs((m) => [...m, { me: false, t: r.reply }])
    } catch (e) {
      setMsgs((m) => [...m, { me: false, t: 'Network error: ' + e.message, err: true }])
    }
    setBusy(false)
  }
  return (
    <div className="two sms">
      <div>
        <h1>Send relief request by SMS</h1>
        <p className="lead">
          No internet and no code needed. Your phone company attaches your number to every text, so the
          control room already knows who sent it.
        </p>
        <h2 className="sec">How to send</h2>
        <ol className="plain">
          <li>Open the messages app on any phone, including a basic keypad phone.</li>
          <li>Write what you need, how many people, and where. Any of English, Hindi or Kannada works.</li>
          <li>Send it to the relief number. You get a reference number back by SMS.</li>
        </ol>
        <table className="tbl">
          <tbody>
            <tr>
              <th scope="row">Request</th>
              <td>
                <code>WARD 7 40 PEOPLE NEED WATER</code>
              </td>
            </tr>
            <tr>
              <th scope="row">Check progress</th>
              <td>
                <code>STATUS</code>
              </td>
            </tr>
            <tr>
              <th scope="row">Examples</th>
              <td>
                <code>HELP</code>
              </td>
            </tr>
          </tbody>
        </table>
        <p className="small">
          Relief number: configured by the administrator with the SMS gateway. In danger, call 112.
        </p>
        <p className="small">
          The phone on the right is a simulator for this demo. A real deployment receives texts through an SMS
          gateway webhook at <code>/api/sms/inbound</code>.
        </p>
      </div>
      <div className="phone" aria-label="SMS simulator">
        <div className="phone-bar">
          Messages <span>Relief helpline</span>
        </div>
        <label className="phone-num">
          Your number (sender)
          <input
            value={num}
            onChange={(e) => setNum(e.target.value.replace(/\D/g, ''))}
            inputMode="numeric"
            maxLength={10}
          />
        </label>
        <div className="thread" aria-live="polite">
          {msgs.map((m, i) => (
            <p key={i} className={`bubble ${m.me ? 'me' : ''} ${m.err ? 'err' : ''}`}>
              {m.t}
            </p>
          ))}
          <div ref={end} />
        </div>
        <div className="samples tight">
          {SAMPLES.map((s) => (
            <button key={s} type="button" className="chip" onClick={() => setText(s)}>
              {s.length > 22 ? s.slice(0, 22) + '...' : s}
            </button>
          ))}
        </div>
        <div className="row">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send()}
            placeholder="Type a message"
            aria-label="Message"
          />
          <button
            className="btn primary"
            disabled={busy || num.length !== 10 || cfg?.demo === false}
            onClick={() => send()}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
