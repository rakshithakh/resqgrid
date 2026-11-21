import { Link } from 'react-router-dom'
export default function Crumbs({ trail = [] }) {
  return (
    <nav className="crumbs" aria-label="Breadcrumb">
      <Link to="/">Home</Link>
      {trail.map(([label, to]) => (
        <span key={label}>
          {' '}
          &rsaquo; {to ? <Link to={to}>{label}</Link> : <span aria-current="page">{label}</span>}
        </span>
      ))}
    </nav>
  )
}
