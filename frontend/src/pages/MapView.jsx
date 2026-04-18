/**
 * MapView.jsx — Full-page interactive OpenStreetMap view for RoadWatch officer dashboard.
 *
 * Features:
 *  • Fetches ALL complaints on mount using the existing api.js service
 *  • Custom Leaflet markers (SVG circles) colour-coded by severity / completion status
 *  • Popup on marker click (full complaint summary + View Details)
 *  • Filter pill bar: All | High | Medium | Low | Completed
 *  • Floating legend (white card, bottom-left)
 *  • Loading spinner while data fetches
 *  • Back-to-dashboard nav button
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, Popup, CircleMarker, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useAuth } from '../services/AuthContext';
import { api } from '../services/api';
import {
  MARKER_COLORS,
  DEFAULT_CENTER,
  DEFAULT_ZOOM,
  DETAIL_ZOOM,
  TILE_URL,
  TILE_ATTRIBUTION
} from '../config/mapsConfig';
import { useAdminFeed } from '../hooks/useAdminFeed';

// ── Severity → colour mapping (exact spec values) ─────────────────────────────
function markerColor(complaint) {
  if (complaint.status === 'completed') return MARKER_COLORS.completed;
  if (complaint.severity === 'high')   return MARKER_COLORS.high;
  if (complaint.severity === 'medium') return MARKER_COLORS.medium;
  return MARKER_COLORS.low;
}

/**
 * Returns an L.divIcon containing an SVG circle for the given complaint.
 */
function svgMarker(color) {
  const svgString = `<svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <circle cx="12" cy="12" r="10" fill="${color}" fill-opacity="0.9" stroke="#ffffff" stroke-width="2"/>
  </svg>`;
  
  return L.divIcon({
    className: 'custom-svg-marker',
    html: svgString,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -14],
  });
}

// ── Filter definitions ────────────────────────────────────────────────────────
const FILTERS = ['All', 'High', 'Medium', 'Low', 'Completed'];

function applyFilter(complaints, filter) {
  switch (filter) {
    case 'High':      return complaints.filter(c => c.severity === 'high'   && c.status !== 'completed');
    case 'Medium':    return complaints.filter(c => c.severity === 'medium' && c.status !== 'completed');
    case 'Low':       return complaints.filter(c => c.severity === 'low'    && c.status !== 'completed');
    case 'Completed': return complaints.filter(c => c.status === 'completed');
    default:          return complaints;
  }
}

// ── Legend entries ────────────────────────────────────────────────────────────
const LEGEND = [
  { label: 'High severity',   color: MARKER_COLORS.high },
  { label: 'Medium severity', color: MARKER_COLORS.medium },
  { label: 'Low severity',    color: MARKER_COLORS.low },
  { label: 'Completed',       color: MARKER_COLORS.completed },
];

/**
 * Helper component to automatically re-center the map when the center prop changes.
 */
function MapUpdater({ center, zoom }) {
  const map = useMap();
  useEffect(() => {
    if (center && zoom) {
      map.setView(center, zoom, { animate: true });
    }
  }, [center, zoom, map]);
  return null;
}

MapUpdater.propTypes = {
  center: PropTypes.arrayOf(PropTypes.number),
  zoom: PropTypes.number,
};

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────
export default function MapView() {
  const navigate = useNavigate();
  const { token } = useAuth();

  const [complaints,    setComplaints]    = useState([]);
  const [activeFilter,  setActiveFilter]  = useState('All');
  const [loading,       setLoading]       = useState(true);
  const [error,         setError]         = useState('');
  
  const { events } = useAdminFeed();

  // Seed officer locations from REST endpoint on mount
  const [officerLocations, setOfficerLocations] = useState({});
  useEffect(() => {
    const base = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
    fetch(`${base}/admin/officers/locations`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) {
          const seed = {};
          data.forEach((d) => { seed[d.officer_id] = d; });
          setOfficerLocations(seed);
        }
      })
      .catch(console.error);
  }, [token]);

  // Merge live WS officer_location events on top of the REST seed
  const officerMarkers = useMemo(() => {
    const merged = { ...officerLocations };
    events.forEach((e) => {
      if (e.event === 'officer_location') {
        merged[e.data.officer_id] = e.data;
      }
    });
    return merged;
  }, [events, officerLocations]);

  // ── Fetch complaints on mount ─────────────────────────────────────────────
  const fetchComplaints = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.getComplaints(token);
      // Keep only complaints with valid coordinates
      setComplaints(data.filter(c => c.latitude != null && c.longitude != null));
    } catch (err) {
      console.error('MapView: failed to fetch complaints', err);
      setError('Failed to load complaints. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchComplaints();
  }, [fetchComplaints]);

  // ── Filter complaints client-side (no re-fetch) ────────────────────────────
  const visible = useMemo(
    () => applyFilter(complaints, activeFilter),
    [complaints, activeFilter],
  );

  // ── Map centre: first complaint coord → fallback India centre ─────────────
  const center = useMemo(() => {
    if (visible.length > 0) {
      return [visible[0].latitude, visible[0].longitude];
    } else if (complaints.length > 0) {
      return [complaints[0].latitude, complaints[0].longitude];
    }
    return DEFAULT_CENTER;
  }, [visible, complaints]);

  const zoom = complaints.length > 0 ? DETAIL_ZOOM : DEFAULT_ZOOM;

  // ── Early returns ─────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={S.fullPage}>
        <div style={S.spinnerWrap}>
          <div style={S.spinner} />
          <p style={{ color: '#7a8299', marginTop: 16 }}>
            Fetching complaint data…
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={S.page}>
      {/* ── Top toolbar ──────────────────────────────────────────────────── */}
      <div style={S.toolbar}>
        {/* Left: back + title */}
        <div style={S.toolbarLeft}>
          <button
            id="map-back-btn"
            onClick={() => navigate('/')}
            style={S.backBtn}
            aria-label="Back to dashboard"
          >
            ←
          </button>
          <div>
            <h1 style={S.title}>🗺️ Complaints Map (OSM)</h1>
            <p style={S.subtitle}>
              {visible.length} of {complaints.length} complaint
              {complaints.length !== 1 ? 's' : ''} shown
            </p>
          </div>
        </div>

        {/* Right: filter pills */}
        <div style={S.pillRow} role="group" aria-label="Severity filter">
          {FILTERS.map(f => (
            <button
              key={f}
              id={`map-filter-${f.toLowerCase()}`}
              onClick={() => { setActiveFilter(f); }}
              style={activeFilter === f ? S.pillActive : S.pill}
              aria-pressed={activeFilter === f}
            >
              {f}
            </button>
          ))}
          <button
            id="map-refresh-btn"
            onClick={fetchComplaints}
            style={S.refreshBtn}
            title="Refresh data"
          >
            ↻
          </button>
        </div>
      </div>

      {/* ── Error banner (non-fatal) ──────────────────────────────────────── */}
      {error && (
        <div style={S.errorBanner}>
          ⚠️ {error}
          <button onClick={fetchComplaints} style={S.retryBtn}>Retry</button>
        </div>
      )}

      {/* ── Map area ─────────────────────────────────────────────────────── */}
      <div style={S.mapOuter}>
        <MapContainer 
          center={center} 
          zoom={zoom} 
          style={S.mapContainerStyle}
          zoomControl={true}
        >
          <TileLayer
            url={TILE_URL}
            attribution={TILE_ATTRIBUTION}
          />
          <MapUpdater center={center} zoom={zoom} />
          
          {/* Markers */}
          {visible.map(c => (
            <Marker
              key={c.id ?? c.complaint_id}
              position={[c.latitude, c.longitude]}
              icon={svgMarker(markerColor(c))}
            >
              {/* InfoWindow (Popup in Leaflet) */}
              <Popup offset={[0, -10]}>
                <div style={S.iw}>
                  {/* Header bar coloured by severity */}
                  <div style={{
                    ...S.iwHeader,
                    borderLeft: `4px solid ${markerColor(c)}`,
                  }}>
                    <span style={S.iwId}>Complaint ID: {c.complaint_id}</span>
                  </div>

                  <div style={S.iwRow}>
                    <span style={S.iwLabel}>Type</span>
                    <span style={S.iwVal}>
                      {(c.damage_type || '—').replace(/_/g, ' ')}
                    </span>
                    <span style={{ ...S.iwLabel, marginLeft: 12 }}>Severity</span>
                    <span style={{
                      ...S.iwVal,
                      color: markerColor(c),
                      fontWeight: 700,
                    }}>
                      {c.severity?.toUpperCase() || '—'}
                    </span>
                  </div>

                  <div style={S.iwRow}>
                    <span style={S.iwLabel}>Status</span>
                    <span style={S.iwVal}>
                      {(c.status || '—').replace(/_/g, ' ').toUpperCase()}
                    </span>
                  </div>

                  <div style={S.iwRow}>
                    <span style={S.iwLabel}>Priority</span>
                    <span style={S.iwVal}>
                      {c.priority_score != null
                        ? `${Number(c.priority_score).toFixed(1)}/100`
                        : '—'}
                    </span>
                  </div>

                  <div style={{ ...S.iwRow, flexWrap: 'wrap', alignItems: 'flex-start' }}>
                    <span style={S.iwLabel}>Address</span>
                    <span style={{ ...S.iwVal, flex: 1 }}>
                      {c.address ||
                        `GPS: ${c.latitude.toFixed(5)}, ${c.longitude.toFixed(5)}`}
                    </span>
                  </div>

                  <button
                    id={`map-view-details-${c.complaint_id}`}
                    style={S.iwBtn}
                    onClick={() => navigate(`/complaint/${c.complaint_id}`)}
                  >
                    View Details →
                  </button>
                </div>
              </Popup>
            </Marker>
          ))}
          
          {/* Active Officers — CircleMarker + Tooltip (spec) */}
          {Object.values(officerMarkers).map((o) => (
            <CircleMarker
              key={`officer-${o.officer_id}`}
              center={[o.lat, o.lng]}
              radius={10}
              pathOptions={{ color: '#3B82F6', fillColor: '#3B82F6', fillOpacity: 0.85 }}
            >
              <Tooltip direction="top" offset={[0, -12]} opacity={1} permanent={false}>
                <div style={{ fontFamily: 'system-ui', fontSize: 12, lineHeight: '1.4' }}>
                  <strong>{o.name}</strong><br />
                  Zone: {o.zone}
                </div>
              </Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>

        {/* ── Legend ─────────────────────────────────────────────────────── */}
        <div style={S.legend}>
          {LEGEND.map(({ label, color }) => (
            <div key={label} style={S.legendRow}>
              <span style={{ ...S.dot, background: color }} />
              <span style={S.legendLabel}>{label}</span>
            </div>
          ))}
        </div>

        {/* ── No data overlay ────────────────────────────────────────────── */}
        {visible.length === 0 && (
          <div style={S.noData}>
            No {activeFilter !== 'All' ? activeFilter.toLowerCase() : ''} complaints to display
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Styles
// ─────────────────────────────────────────────────────────────────────────────
const S = {
  /* ── page shell ── */
  page: {
    minHeight: '100vh',
    background: '#0d0f14',
    color: '#e8eaf0',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    display: 'flex',
    flexDirection: 'column',
  },

  /* ── full-page centred states ── */
  fullPage: {
    minHeight: '100vh',
    background: '#0d0f14',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  spinnerWrap: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
  },
  spinner: {
    width: 48,
    height: 48,
    border: '4px solid #252b38',
    borderTop: '4px solid #f5a623',
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite',
  },

  /* ── toolbar ── */
  toolbar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 24px',
    background: '#161a23',
    borderBottom: '1px solid #252b38',
    flexWrap: 'wrap',
    gap: 12,
    flexShrink: 0,
  },
  toolbarLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 14,
  },
  backBtn: {
    background: '#252b38',
    color: '#e8eaf0',
    border: 'none',
    borderRadius: '50%',
    width: 34,
    height: 34,
    fontSize: 18,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    zIndex: 10,
  },
  title: {
    fontSize: 19,
    fontWeight: 800,
    margin: 0,
    lineHeight: 1.2,
  },
  subtitle: {
    fontSize: 12,
    color: '#7a8299',
    margin: '2px 0 0',
  },

  /* ── filter pills ── */
  pillRow: {
    display: 'flex',
    gap: 8,
    flexWrap: 'wrap',
    alignItems: 'center',
  },
  pill: {
    padding: '6px 16px',
    borderRadius: 20,
    border: '1px solid #252b38',
    background: 'transparent',
    color: '#7a8299',
    fontSize: 13,
    cursor: 'pointer',
    transition: 'all 0.15s',
    fontWeight: 500,
  },
  pillActive: {
    padding: '6px 16px',
    borderRadius: 20,
    border: '1px solid #f5a623',
    background: '#f5a623',
    color: '#000',
    fontSize: 13,
    cursor: 'pointer',
    fontWeight: 700,
  },
  refreshBtn: {
    padding: '6px 12px',
    borderRadius: 20,
    border: '1px solid #252b38',
    background: 'transparent',
    color: '#7a8299',
    fontSize: 16,
    cursor: 'pointer',
    lineHeight: 1,
  },

  /* ── error banner ── */
  errorBanner: {
    background: '#3b1010',
    color: '#fca5a5',
    padding: '8px 24px',
    fontSize: 13,
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    flexShrink: 0,
  },
  retryBtn: {
    background: '#ef4444',
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    padding: '4px 12px',
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 700,
  },

  /* ── map wrapper ── */
  mapOuter: {
    position: 'relative',
    flex: 1,
    display: 'flex',
  },
  mapContainerStyle: {
    width:  '100%',
    height: '100%',
    flex: 1,
  },

  /* ── legend (white card, spec-exact positioning) ── */
  legend: {
    position: 'absolute',
    bottom: 32,
    left: 16,
    background: '#ffffff',
    borderRadius: 8,
    padding: 12,
    boxShadow: '0 2px 12px rgba(0,0,0,0.35)',
    zIndex: 1000, /* leaflet tile layer gets high z index, so legend needs more */
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    minWidth: 160,
  },
  legendRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  dot: {
    display: 'inline-block',
    width: 12,
    height: 12,
    borderRadius: '50%',
    flexShrink: 0,
    border: '1px solid rgba(0,0,0,0.15)',
  },
  legendLabel: {
    fontSize: 12,
    color: '#1e2434',
    fontWeight: 500,
    margin: 0,
  },

  /* ── no-data overlay ── */
  noData: {
    position: 'absolute',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    background: 'rgba(22, 26, 35, 0.92)',
    color: '#7a8299',
    padding: '14px 28px',
    borderRadius: 10,
    fontSize: 14,
    border: '1px solid #252b38',
    pointerEvents: 'none',
    zIndex: 1000,
  },

  /* ── InfoWindow (Popup) ── */
  iw: {
    minWidth: 230,
    maxWidth: 290,
    fontFamily: 'system-ui, -apple-system, sans-serif',
    fontSize: 13,
    color: '#1e2434',
    padding: '2px 0',
  },
  iwHeader: {
    paddingLeft: 8,
    marginBottom: 10,
    paddingBottom: 8,
    borderBottom: '1px solid #e5e7eb',
  },
  iwId: {
    fontWeight: 700,
    fontSize: 14,
    color: '#1e2434',
  },
  iwRow: {
    display: 'flex',
    alignItems: 'baseline',
    gap: 4,
    marginBottom: 5,
    flexWrap: 'wrap',
  },
  iwLabel: {
    fontSize: 11,
    color: '#6b7280',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    flexShrink: 0,
  },
  iwVal: {
    fontSize: 13,
    color: '#1e2434',
    fontWeight: 500,
  },
  iwBtn: {
    marginTop: 10,
    width: '100%',
    padding: '8px 0',
    background: '#1d4ed8',
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    cursor: 'pointer',
    fontWeight: 700,
    fontSize: 13,
    letterSpacing: '0.03em',
  },
};

// Inject keyframe CSS for spinner (once)
if (typeof document !== 'undefined' && !document.getElementById('rw-spin-style')) {
  const st = document.createElement('style');
  st.id = 'rw-spin-style';
  st.textContent = '@keyframes spin { to { transform: rotate(360deg); } }';
  document.head.appendChild(st);
}
// Fix popup padding styles from leaflet mapping
if (typeof document !== 'undefined' && !document.getElementById('rw-leaflet-style')) {
  const st = document.createElement('style');
  st.id = 'rw-leaflet-style';
  st.textContent = '.leaflet-popup-content { margin: 12px 14px; line-height: 1.4; } .custom-svg-marker { background: transparent; border: none; }';
  document.head.appendChild(st);
}
