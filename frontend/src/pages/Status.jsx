import { usePoll, TYPE, STATUS } from '../lib'

export default function Status() {
  const { data: s, error } = usePoll('/public/status', 4000)
  if (error) return <p className="msg err">Status unavailable. {error}</p>
  if (!s) return <p>Loading current status...</p>
  const byType = s.by_type && typeof s.by_type === 'object' ? s.by_type : {}
  const max = Math.max(1, ...Object.values(byType))
  return (
    <>
      <h1>Public status board</h1>
      <p className="lead">
        A transparent view of open needs, closed roads and whether vehicles have been released. Locations are
        shown at ward level only.
      </p>
      <div className="stats row">
        <div className="stat">
          <b>{s.reports}</b>
          <span>Reports received</span>
        </div>
        <div className="stat">
          <b>{s.open_needs}</b>
          <span>Open relief needs</span>
        </div>
        <div className="stat">
          <b>{s.people_affected}</b>
          <span>People awaiting help</span>
        </div>
        <div className="stat">
          <b>{s.plan_approved ? 'Released' : 'Preparing'}</b>
          <span>Vehicle dispatch</span>
        </div>
      </div>
      <section className="two">
        <div>
          <h2 className="sec">Open needs by type</h2>
          {Object.keys(byType).length === 0 ? (
            <p>No open needs at this time.</p>
          ) : (
            <ul className="bars">
              {Object.entries(byType).map(([k, v]) => (
                <li key={k}>
                  <span>{TYPE[k]}</span>
                  <i style={{ width: `${(v / max) * 100}%` }} />
                  <b>{v}</b>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h2 className="sec">Road closures and hazards</h2>
          {s.hazards.length === 0 ? (
            <p>No closures reported.</p>
          ) : (
            <table className="tbl">
              <tbody>
                {s.hazards.map((h, i) => (
                  <tr key={i}>
                    <th scope="row">{h.label}</th>
                    <td>{h.kind === 'blocked' ? 'Closed' : 'Slow traffic'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
      <h2 className="sec">Largest verified needs by area</h2>
      <div className="scroll">
        <table className="tbl full">
          <thead>
            <tr>
              <th>Area</th>
              <th>Needs</th>
              <th>People</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {s.wards.map((w, i) => (
              <tr key={i}>
                <td>{w.label}</td>
                <td>{w.types.map((t) => TYPE[t]).join(', ')}</td>
                <td>{w.people}</td>
                <td>{STATUS[w.status]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
