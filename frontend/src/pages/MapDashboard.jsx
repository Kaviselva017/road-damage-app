import { useState } from 'react'
import { MapContainer, TileLayer, ZoomControl } from 'react-leaflet'
import HeatmapView from '../components/HeatmapView'
import HotspotPanel from '../components/HotspotPanel'
import TimelineChart from '../components/TimelineChart'

const MapDashboard = () => {
  const [gridSize, setGridSize] = useState(500)
  const token = localStorage.getItem('token') // Simplistic auth retrieval

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#f8fafc', overflow: 'hidden', fontFamily: 'system-ui, sans-serif' }}>
      {/* Header */}
      <header style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 32px', background: '#fff', borderBottom: '1px solid #e5e7eb', flexShrink: 0, zIndex: 50 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ background: 'rgba(59,130,246,0.1)', padding: 8, borderRadius: 8 }}>
            🗺️
          </div>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: '#0f172a', letterSpacing: '-0.025em', margin: 0 }}>Road Damage Intelligence Map</h1>
            <p style={{ fontSize: 10, color: '#6b7280', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.1em', margin: 0 }}>PostGIS Heatmap &amp; Predictive Triage</p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, background: '#f9fafb', padding: '8px 16px', borderRadius: 12, border: '1px solid #f3f4f6' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#6b7280' }}>
              ⚙️
              <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase' }}>Grid Analysis:</span>
            </div>
            <input
              type="range"
              min="100" max="2000" step="100"
              value={gridSize}
              onChange={(e) => setGridSize(parseInt(e.target.value))}
              style={{ width: 128, cursor: 'pointer', accentColor: '#3b82f6' }}
            />
            <span style={{ fontSize: 12, fontWeight: 900, color: '#334155', width: 48 }}>{gridSize}m</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative', overflow: 'hidden' }}>
        {/* Map Area */}
        <div style={{ flex: 1, position: 'relative' }}>
          <MapContainer
            center={[12.9716, 77.5946]}
            zoom={13}
            zoomControl={false}
            style={{ height: '100%', width: '100%' }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
            />
            <ZoomControl position="bottomleft" />

            <HeatmapView gridSize={gridSize} />
            <HotspotPanel token={token} />
          </MapContainer>
        </div>

        {/* Bottom Panel */}
        <div style={{ background: '#f8fafc', padding: 24, flexShrink: 0, position: 'relative', zIndex: 40, borderTop: '1px solid #e5e7eb' }}>
          <div style={{ maxWidth: 1152, margin: '0 auto' }}>
            <TimelineChart />
          </div>
        </div>
      </main>
    </div>
  )
}

export default MapDashboard
