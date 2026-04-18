import { useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import { useMap } from 'react-leaflet'

const HotspotPanel = ({ token }) => {
  const map = useMap()
  const [hotspots, setHotspots] = useState([])
  const [collapsed, setCollapsed] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchHotspots = async () => {
      try {
        const response = await fetch('/api/map/hotspots?min_count=3', {
          headers: { 'Authorization': `Bearer ${token}` }
        })
        if (!response.ok) throw new Error('Auth required')
        const data = await response.json()
        setHotspots(data.slice(0, 10)) // Top 10
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    if (token) fetchHotspots()
  }, [token])

  const handleFlyTo = (lat, lng) => {
    map.flyTo([lat, lng], 15, { duration: 1 })
  }

  const getSeverityColor = (sev) => {
    switch (sev.toLowerCase()) {
      case 'critical': return { background: '#dc2626', color: '#fff' }
      case 'high':     return { background: '#f97316', color: '#fff' }
      case 'medium':   return { background: '#facc15', color: '#000' }
      default:         return { background: '#3b82f6', color: '#fff' }
    }
  }

  return (
    <div style={{
      position: 'fixed', right: 0, top: 0, height: '100vh',
      transition: 'width 0.3s', zIndex: 1001,
      background: '#fff', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
      display: 'flex', width: collapsed ? 0 : 320, overflow: 'hidden'
    }}>
      <button
        onClick={() => setCollapsed(!collapsed)}
        style={{
          position: 'absolute', left: -40, top: '50%', transform: 'translateY(-50%)',
          background: '#fff', border: '1px solid #e5e7eb', borderRight: 'none',
          borderRadius: '12px 0 0 12px', padding: '8px', cursor: 'pointer',
          boxShadow: '-2px 0 8px rgba(0,0,0,0.1)'
        }}
      >
        {collapsed ? '‹' : '›'}
      </button>

      {!collapsed && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '24px', borderBottom: '1px solid #e5e7eb', background: '#0f172a', color: '#fff' }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
              ⚠️ Damage Hotspots
            </h2>
            <p style={{ fontSize: 11, color: '#94a3b8', marginTop: 4, marginBottom: 0 }}>Highest priority resolution zones</p>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
            {loading ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 160, gap: 8, color: '#9ca3af' }}>
                <div style={{ width: 24, height: 24, border: '2px solid #e5e7eb', borderTop: '2px solid #3b82f6', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
                <span style={{ fontSize: 14 }}>Identifying hotspots...</span>
              </div>
            ) : hotspots.map((h, idx) => (
              <div
                key={idx}
                onClick={() => handleFlyTo(h.lat, h.lng)}
                style={{
                  padding: 16, borderRadius: 12, border: '1px solid #f3f4f6',
                  cursor: 'pointer', transition: 'all 0.15s',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.06)'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#9ca3af' }}>#{idx + 1}</span>
                  <span style={{
                    fontSize: 10, padding: '2px 8px', borderRadius: 999,
                    fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.05em',
                    ...getSeverityColor(h.max_severity)
                  }}>
                    {h.max_severity}
                  </span>
                </div>

                <h3 style={{ fontWeight: 700, color: '#1e293b', fontSize: 14, margin: '0 0 4px', textTransform: 'capitalize', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {h.dominant_damage_type} Cluster
                </h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#6b7280', marginBottom: 12 }}>
                  📍 {h.count} active reports nearby
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={{ fontSize: 10, color: '#9ca3af', textTransform: 'uppercase', fontWeight: 500 }}>Est. Repair Cost</span>
                    <span style={{ fontSize: 14, fontWeight: 700, color: '#0f172a' }}>
                      ₹{h.estimated_repair_cost.toLocaleString()}
                    </span>
                  </div>
                  <div style={{ width: 32, height: 32, background: '#f8fafc', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16 }}>
                    ›
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default HotspotPanel

HotspotPanel.propTypes = {
  token: PropTypes.string,
}
