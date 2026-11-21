import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { prioColor } from '../lib'

export const ROUTE_COLORS = ['#1b5fbf', '#7b3fb0', '#0e8a7d', '#c2410c', '#8a6d00']
const SPEED = 40 // simulation speed-up for vehicle movement

function interp(route, t) {
  const { points: p, times: ts } = route
  if (t <= ts[0]) return p[0]
  for (let i = 0; i < ts.length - 1; i++) {
    if (t < ts[i + 1]) {
      const k = (t - ts[i]) / Math.max(0.001, ts[i + 1] - ts[i])
      return [p[i][0] + (p[i + 1][0] - p[i][0]) * k, p[i][1] + (p[i + 1][1] - p[i][1]) * k]
    }
  }
  return p[p.length - 1]
}

export default function MapView({ geo, st, showBase, placing, onPlace, fetchedAt, focus }) {
  const el = useRef(),
    map = useRef(),
    base = useRef(),
    dyn = useRef(),
    veh = useRef({})
  const stRef = useRef(st),
    placingRef = useRef(placing),
    placeRef = useRef(onPlace)
  stRef.current = st
  placingRef.current = placing
  placeRef.current = onPlace

  useEffect(() => {
    if (!geo || map.current) return
    const m = L.map(el.current, { attributionControl: !!geo.tiles, zoomSnap: 0.25, maxZoom: 19 })
    if (geo.tiles)
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors',
      }).addTo(m)
    map.current = m
    m.fitBounds(L.latLngBounds(geo.bounds), { padding: [16, 16] })
    base.current = L.layerGroup().addTo(m)
    dyn.current = L.layerGroup().addTo(m)
    if (geo.river.length)
      L.polyline(geo.river, { color: '#8dbbe0', weight: 26, opacity: 0.55, lineCap: 'round' }).addTo(
        base.current,
      )
    geo.roads.forEach(([a, b, br]) =>
      L.polyline([a, b], {
        color: br ? '#2f4b6e' : '#aab5c2',
        weight: br ? 6 : 2.5,
        opacity: br ? 0.9 : 0.8,
      }).addTo(base.current),
    )
    geo.bridges.forEach((b) =>
      L.marker([b.lat, b.lng], {
        icon: L.divIcon({
          className: 'map-tag bridge',
          html: b.label,
          iconSize: [60, 16],
          iconAnchor: [30, -4],
        }),
        interactive: false,
      }).addTo(base.current),
    )
    geo.places.forEach((p) =>
      L.marker([p.lat, p.lng], {
        icon: L.divIcon({ className: 'map-tag', html: p.name, iconSize: [150, 14], iconAnchor: [75, -9] }),
        interactive: false,
      }).addTo(base.current),
    )
    geo.depots.forEach((d) =>
      L.marker([d.lat, d.lng], {
        icon: L.divIcon({ className: 'depot-ic', html: 'D', iconSize: [24, 24], iconAnchor: [12, 12] }),
      })
        .bindTooltip(d.name)
        .addTo(base.current),
    )
    m.on('click', (e) => {
      if (placingRef.current) placeRef.current(e.latlng)
    })
  }, [geo])

  useEffect(() => {
    if (el.current) el.current.classList.toggle('placing', !!placing)
  }, [placing])
  useEffect(() => {
    if (focus && map.current)
      map.current.flyTo([focus.lat, focus.lng], Math.max(map.current.getZoom(), 15), { duration: 0.8 })
  }, [focus])

  useEffect(() => {
    if (!map.current || !st) return
    const g0 = dyn.current
    g0.clearLayers()
    veh.current = {}
    const g = g0
    const plan = st.plan,
      uns = new Set(plan?.optimized.metrics.unserved_ids || [])
    st.hazards.forEach((h) => {
      const c = h.kind === 'blocked' ? '#b3261e' : '#d9730d'
      L.circle([h.lat, h.lng], {
        radius: h.radius,
        color: c,
        weight: 2,
        dashArray: '6 4',
        fillColor: c,
        fillOpacity: 0.16,
      })
        .bindTooltip(`${h.label} (${h.kind === 'blocked' ? 'closed' : 'slow'})`)
        .addTo(g)
    })
    if (plan && showBase)
      plan.baseline.routes.forEach((r) =>
        L.polyline(r.points, { color: '#555', weight: 3, dashArray: '2 7', opacity: 0.9 }).addTo(g),
      )
    plan?.optimized.routes.forEach((r, i) =>
      L.polyline(r.points, { color: ROUTE_COLORS[i % 5], weight: 4, opacity: 0.88 }).addTo(g),
    )
    st.needs
      .filter((n) => n.lat && n.status !== 'rejected')
      .forEach((n) => {
        const review = n.status === 'review'
        L.circleMarker([n.lat, n.lng], {
          radius: 7 + Math.min(n.people, 120) / 12,
          fillColor: prioColor(n.priority),
          fillOpacity: review ? 0.45 : 0.92,
          color: uns.has(n.id) ? '#b3261e' : review ? '#333' : '#fff',
          weight: uns.has(n.id) ? 3 : 2,
          dashArray: review ? '3 3' : null,
        })
          .bindTooltip(
            `${n.label}: ${n.people} people, priority ${n.priority}${review ? ' (under review)' : ''}${uns.has(n.id) ? ' (not reachable)' : ''}`,
          )
          .addTo(g)
      })
    const live = st.live || {}
    st.needs
      .filter((n) => n.gps_at && n.status !== 'rejected')
      .forEach((n) => {
        const g = n.gps_at
        if (g.acc && g.acc <= 800)
          L.circle([g.lat, g.lng], {
            radius: g.acc,
            color: '#1b5fbf',
            weight: 1,
            fillColor: '#1b5fbf',
            fillOpacity: 0.12,
            interactive: false,
          }).addTo(g0)
        if (n.lat && Math.abs(n.lat - g.lat) + Math.abs(n.lng - g.lng) > 0.0002)
          L.polyline(
            [
              [g.lat, g.lng],
              [n.lat, n.lng],
            ],
            { color: '#1b5fbf', weight: 1.5, dashArray: '3 4', interactive: false },
          ).addTo(g0)
        L.circleMarker([g.lat, g.lng], {
          radius: 5,
          color: '#fff',
          weight: 2,
          fillColor: '#1b5fbf',
          fillOpacity: 1,
        })
          .bindTooltip(
            `Reporter's phone location${g.acc != null ? ` (about ${Math.round(g.acc)} m)` : ''}: ${n.label}`,
          )
          .addTo(g0)
      })
    plan?.optimized.routes.forEach((r, i) => {
      const lv = live[r.vehicle_id]
      veh.current[r.vehicle_id] = {
        live: !!lv,
        route: r,
        marker: L.marker(lv ? [lv.lat, lv.lng] : r.points[0], {
          zIndexOffset: 1000,
          icon: L.divIcon({
            className: 'veh-ic' + (lv ? ' live' : ''),
            html: `<span style="background:${ROUTE_COLORS[i % 5]}">${r.vehicle_id}${lv ? ' LIVE' : ''}</span>`,
            iconSize: [lv ? 70 : 44, 20],
            iconAnchor: [lv ? 35 : 22, 10],
          }),
        }).addTo(g),
      }
    })
    Object.entries(live)
      .filter(([id]) => !veh.current[id])
      .forEach(([id, lv]) =>
        L.marker([lv.lat, lv.lng], {
          zIndexOffset: 1000,
          icon: L.divIcon({
            className: 'veh-ic live',
            html: `<span style="background:#555">${id} LIVE</span>`,
            iconSize: [70, 20],
            iconAnchor: [35, 10],
          }),
        }).addTo(g),
      )
  }, [st, showBase, geo])

  useEffect(() => {
    let raf
    const tick = () => {
      const s = stRef.current
      if (s?.plan?.approved && s.approval_elapsed_s != null) {
        const t = (s.approval_elapsed_s + (performance.now() - fetchedAt.current) / 1000) * SPEED
        Object.values(veh.current).forEach((v) => {
          if (!v.live) v.marker.setLatLng(interp(v.route, t))
        })
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [])

  useEffect(
    () => () => {
      map.current?.remove()
      map.current = null
    },
    [],
  )
  return <div ref={el} className="map" />
}
