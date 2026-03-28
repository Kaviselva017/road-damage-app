import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../services/AuthContext';
import { api, getOfficerSocketUrl } from '../services/api';
import { formatDateTime } from '../utils/dateTime';

const SEVERITY_COLORS = { high: '#e05c5c', medium: '#f5a623', low: '#3ecfb2' };
const STATUS_COLORS = {
  pending: '#7a8299',
  assigned: '#f5a623',
  in_progress: '#3b82f6',
  completed: '#22c55e',
  rejected: '#e05c5c',
};

function formatLabel(value) {
  return String(value || 'unknown').replace(/_/g, ' ');
}

function buildPoints(complaints) {
  const plotted = complaints.filter(
    (complaint) =>
      Number.isFinite(complaint.latitude) &&
      Number.isFinite(complaint.longitude),
  );

  if (!plotted.length) {
    return [];
  }

  const latitudes = plotted.map((complaint) => complaint.latitude);
  const longitudes = plotted.map((complaint) => complaint.longitude);
  const minLat = Math.min(...latitudes);
  const maxLat = Math.max(...latitudes);
  const minLng = Math.min(...longitudes);
  const maxLng = Math.max(...longitudes);
  const latRange = Math.max(maxLat - minLat, 0.01);
  const lngRange = Math.max(maxLng - minLng, 0.01);
  const paddedMinLat = minLat - (latRange * 0.08);
  const paddedMaxLat = maxLat + (latRange * 0.08);
  const paddedMinLng = minLng - (lngRange * 0.08);
  const paddedMaxLng = maxLng + (lngRange * 0.08);
  const paddedLatRange = paddedMaxLat - paddedMinLat || 0.01;
  const paddedLngRange = paddedMaxLng - paddedMinLng || 0.01;

  return plotted.map((complaint) => ({
    ...complaint,
    x: ((complaint.longitude - paddedMinLng) / paddedLngRange) * 100,
    y: 100 - (((complaint.latitude - paddedMinLat) / paddedLatRange) * 100),
  }));
}

function markerSize(complaint, active) {
  const base = complaint.severity === 'high' ? 18 : complaint.severity === 'medium' ? 14 : 12;
  const priorityBonus = Math.min((complaint.priority_score || 0) / 20, 6);
  return `${base + priorityBonus + (active ? 4 : 0)}px`;
}

export default function MapView() {
  const navigate = useNavigate();
  const { token } = useAuth();

  const [complaints, setComplaints] = useState([]);
  const [selectedComplaintId, setSelectedComplaintId] = useState(null);
  const [filter, setFilter] = useState({ status: '', severity: '', search: '' });
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  const [syncState, setSyncState] = useState('offline');
  const [lastEvent, setLastEvent] = useState('');

  async function loadComplaints(silent = false) {
    if (!silent) {
      setLoading(true);
    }
    try {
      const data = await api.getComplaints(token);
      const next = Array.isArray(data) ? data : [];
      setComplaints(next);
      if (!selectedComplaintId && next.length) {
        setSelectedComplaintId(next[0].complaint_id);
      }
    } catch (error) {
      console.error(error);
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    loadComplaints(refreshKey > 0);
  }, [token, refreshKey]);

  useEffect(() => {
    if (!token) {
      return undefined;
    }

    let socket;
    let heartbeat;

    try {
      socket = new WebSocket(getOfficerSocketUrl());
      setSyncState('connecting');

      socket.onopen = () => {
        setSyncState('live');
        heartbeat = window.setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send('ping');
          }
        }, 15000);
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const summary = payload.complaint_id
            ? `${formatLabel(payload.type)}: ${payload.complaint_id}`
            : formatLabel(payload.type);
          setLastEvent(summary);
          setRefreshKey((current) => current + 1);
        } catch (error) {
          console.error(error);
        }
      };

      socket.onerror = () => {
        setSyncState('degraded');
      };

      socket.onclose = () => {
        setSyncState('offline');
        if (heartbeat) {
          window.clearInterval(heartbeat);
        }
      };
    } catch (error) {
      console.error(error);
      setSyncState('offline');
    }

    return () => {
      if (heartbeat) {
        window.clearInterval(heartbeat);
      }
      if (socket && socket.readyState < 2) {
        socket.close();
      }
    };
  }, [token]);

  const visibleComplaints = complaints.filter((complaint) => {
    if (filter.status && complaint.status !== filter.status) {
      return false;
    }
    if (filter.severity && complaint.severity !== filter.severity) {
      return false;
    }
    if (filter.search) {
      const haystack = [
        complaint.complaint_id,
        complaint.address,
        complaint.damage_type,
        complaint.status,
        complaint.area_type,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      if (!haystack.includes(filter.search.toLowerCase())) {
        return false;
      }
    }
    return true;
  });

  useEffect(() => {
    if (!visibleComplaints.length) {
      setSelectedComplaintId(null);
      return;
    }
    if (!visibleComplaints.some((complaint) => complaint.complaint_id === selectedComplaintId)) {
      setSelectedComplaintId(visibleComplaints[0].complaint_id);
    }
  }, [visibleComplaints, selectedComplaintId]);

  const points = buildPoints(visibleComplaints);
  const selectedComplaint = visibleComplaints.find(
    (complaint) => complaint.complaint_id === selectedComplaintId,
  );

  const mapStats = {
    total: visibleComplaints.length,
    high: visibleComplaints.filter((complaint) => complaint.severity === 'high').length,
    inProgress: visibleComplaints.filter((complaint) => complaint.status === 'in_progress').length,
    averagePriority: visibleComplaints.length
      ? Math.round(
          visibleComplaints.reduce(
            (sum, complaint) => sum + (complaint.priority_score || 0),
            0,
          ) / visibleComplaints.length,
        )
      : 0,
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div>
          <button onClick={() => navigate('/')} style={styles.backButton}>
            Back to Dashboard
          </button>
          <h1 style={styles.title}>Operations Map</h1>
          <p style={styles.subtitle}>
            Live spatial view of officer complaints using reported GPS coordinates.
          </p>
        </div>
        <div style={styles.headerActions}>
          <div
            style={{
              ...styles.syncBadge,
              borderColor: syncState === 'live' ? '#1f6f54' : '#3b4253',
              color: syncState === 'live' ? '#74d9b6' : '#98a2b3',
            }}
          >
            {syncState === 'live' ? 'Live updates on' : syncState === 'connecting' ? 'Connecting' : syncState === 'degraded' ? 'Live sync degraded' : 'Live sync offline'}
          </div>
          <button onClick={() => setRefreshKey((current) => current + 1)} style={styles.refreshButton}>
            Refresh
          </button>
        </div>
      </div>

      <div style={styles.statsGrid}>
        <StatCard label="Visible complaints" value={mapStats.total} color="#e8eaf0" />
        <StatCard label="High severity" value={mapStats.high} color="#e05c5c" />
        <StatCard label="In progress" value={mapStats.inProgress} color="#3b82f6" />
        <StatCard label="Avg priority" value={mapStats.averagePriority} color="#f5a623" />
      </div>

      <div style={styles.filterRow}>
        <input
          value={filter.search}
          onChange={(event) => setFilter((current) => ({ ...current, search: event.target.value }))}
          placeholder="Search complaint id, area, address"
          style={styles.searchInput}
        />
        <select
          value={filter.status}
          onChange={(event) => setFilter((current) => ({ ...current, status: event.target.value }))}
          style={styles.select}
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="assigned">Assigned</option>
          <option value="in_progress">In progress</option>
          <option value="completed">Completed</option>
          <option value="rejected">Rejected</option>
        </select>
        <select
          value={filter.severity}
          onChange={(event) => setFilter((current) => ({ ...current, severity: event.target.value }))}
          style={styles.select}
        >
          <option value="">All severities</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {lastEvent ? <div style={styles.eventBanner}>Last update: {lastEvent}</div> : null}

      {loading ? (
        <div style={styles.loadingState}>Loading mapped complaints...</div>
      ) : (
        <div style={styles.layout}>
          <div style={styles.mapPanel}>
            <div style={styles.mapHeader}>
              <div>
                <h2 style={styles.sectionTitle}>Coordinate map</h2>
                <p style={styles.sectionCopy}>
                  Marker positions are normalized from complaint latitude and longitude.
                </p>
              </div>
              <div style={styles.legend}>
                {Object.entries(SEVERITY_COLORS).map(([severity, color]) => (
                  <span key={severity} style={styles.legendItem}>
                    <span style={{ ...styles.legendDot, background: color }} />
                    {formatLabel(severity)}
                  </span>
                ))}
              </div>
            </div>

            <div style={styles.mapCanvas}>
              <div style={styles.mapGrid} />
              {!points.length ? (
                <div style={styles.emptyState}>
                  <h3 style={{ margin: 0, fontSize: 18 }}>No complaints match these filters</h3>
                  <p style={{ margin: '8px 0 0', color: '#98a2b3' }}>
                    Clear a filter or refresh to repopulate the map.
                  </p>
                </div>
              ) : (
                points.map((complaint) => {
                  const active = complaint.complaint_id === selectedComplaintId;
                  return (
                    <button
                      key={complaint.complaint_id}
                      onClick={() => setSelectedComplaintId(complaint.complaint_id)}
                      title={`${complaint.complaint_id} - ${formatLabel(complaint.severity)}`}
                      style={{
                        ...styles.marker,
                        left: `${complaint.x}%`,
                        top: `${complaint.y}%`,
                        background: SEVERITY_COLORS[complaint.severity] || '#7a8299',
                        borderColor: active ? '#f8fafc' : STATUS_COLORS[complaint.status] || '#1f2937',
                        boxShadow: active
                          ? `0 0 0 6px ${(SEVERITY_COLORS[complaint.severity] || '#7a8299')}22`
                          : '0 10px 30px rgba(0, 0, 0, 0.22)',
                        width: markerSize(complaint, active),
                        height: markerSize(complaint, active),
                      }}
                    />
                  );
                })
              )}
            </div>
          </div>

          <div style={styles.sidebar}>
            <div style={styles.sidebarCard}>
              <h2 style={styles.sectionTitle}>Selected complaint</h2>
              {selectedComplaint ? (
                <>
                  <div style={styles.selectedHeader}>
                    <div>
                      <div style={styles.selectedId}>{selectedComplaint.complaint_id}</div>
                      <div style={styles.selectedAddress}>
                        {selectedComplaint.address || `${selectedComplaint.latitude.toFixed(4)}, ${selectedComplaint.longitude.toFixed(4)}`}
                      </div>
                    </div>
                    <span
                      style={{
                        ...styles.badge,
                        background: `${SEVERITY_COLORS[selectedComplaint.severity] || '#7a8299'}22`,
                        color: SEVERITY_COLORS[selectedComplaint.severity] || '#7a8299',
                      }}
                    >
                      {formatLabel(selectedComplaint.severity)}
                    </span>
                  </div>
                  <DetailRow label="Status" value={formatLabel(selectedComplaint.status)} />
                  <DetailRow label="Damage type" value={formatLabel(selectedComplaint.damage_type)} />
                  <DetailRow label="Area type" value={formatLabel(selectedComplaint.area_type || 'residential')} />
                  <DetailRow label="Priority score" value={selectedComplaint.priority_score || 0} />
                  <DetailRow label="Reported" value={formatDateTime(selectedComplaint.created_at)} />
                  <DetailRow
                    label="Coordinates"
                    value={`${selectedComplaint.latitude.toFixed(5)}, ${selectedComplaint.longitude.toFixed(5)}`}
                  />
                  <div style={styles.sidebarActions}>
                    <button
                      onClick={() => navigate(`/complaint/${selectedComplaint.complaint_id}`)}
                      style={styles.primaryButton}
                    >
                      Open complaint
                    </button>
                    <a
                      href={`https://maps.google.com/?q=${selectedComplaint.latitude},${selectedComplaint.longitude}`}
                      target="_blank"
                      rel="noreferrer"
                      style={styles.linkButton}
                    >
                      Open in Google Maps
                    </a>
                  </div>
                </>
              ) : (
                <p style={styles.emptySidebarCopy}>Select a marker to inspect a complaint.</p>
              )}
            </div>

            <div style={styles.sidebarCard}>
              <h2 style={styles.sectionTitle}>Visible queue</h2>
              <div style={styles.complaintList}>
                {visibleComplaints.length ? (
                  visibleComplaints
                    .sort((left, right) => (right.priority_score || 0) - (left.priority_score || 0))
                    .map((complaint) => (
                      <button
                        key={complaint.complaint_id}
                        onClick={() => setSelectedComplaintId(complaint.complaint_id)}
                        style={{
                          ...styles.listItem,
                          borderColor:
                            complaint.complaint_id === selectedComplaintId
                              ? '#f5a623'
                              : '#252b38',
                        }}
                      >
                        <div style={styles.listTopRow}>
                          <span style={styles.listId}>{complaint.complaint_id}</span>
                          <span
                            style={{
                              ...styles.badge,
                              background: `${STATUS_COLORS[complaint.status] || '#7a8299'}22`,
                              color: STATUS_COLORS[complaint.status] || '#7a8299',
                            }}
                          >
                            {formatLabel(complaint.status)}
                          </span>
                        </div>
                        <div style={styles.listAddress}>
                          {complaint.address || `${complaint.latitude.toFixed(4)}, ${complaint.longitude.toFixed(4)}`}
                        </div>
                        <div style={styles.listMeta}>
                          <span style={{ color: SEVERITY_COLORS[complaint.severity] || '#7a8299' }}>
                            {formatLabel(complaint.severity)}
                          </span>
                          <span>Priority {complaint.priority_score || 0}</span>
                        </div>
                      </button>
                    ))
                ) : (
                  <p style={styles.emptySidebarCopy}>No visible complaints in this view.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DetailRow({ label, value }) {
  return (
    <div style={styles.detailRow}>
      <span style={styles.detailLabel}>{label}</span>
      <span style={styles.detailValue}>{value}</span>
    </div>
  );
}

function StatCard({ label, value, color }) {
  return (
    <div style={styles.statCard}>
      <div style={{ fontSize: 28, fontWeight: 800, color }}>{value}</div>
      <div style={styles.statLabel}>{label}</div>
    </div>
  );
}

const styles = {
  container: {
    minHeight: '100vh',
    background:
      'radial-gradient(circle at top left, rgba(245, 166, 35, 0.12), transparent 28%), linear-gradient(180deg, #0d0f14 0%, #121620 100%)',
    color: '#e8eaf0',
    padding: '24px 32px 36px',
    fontFamily: 'system-ui, sans-serif',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 16,
    marginBottom: 24,
    flexWrap: 'wrap',
  },
  headerActions: { display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' },
  backButton: {
    background: 'transparent',
    border: 'none',
    color: '#98a2b3',
    cursor: 'pointer',
    padding: 0,
    marginBottom: 10,
    fontSize: 14,
  },
  title: { fontSize: 30, fontWeight: 800, margin: 0 },
  subtitle: { color: '#98a2b3', margin: '6px 0 0', fontSize: 14, maxWidth: 620 },
  syncBadge: {
    border: '1px solid #3b4253',
    borderRadius: 999,
    padding: '8px 14px',
    fontSize: 13,
    background: '#131923',
  },
  refreshButton: {
    background: '#f5a623',
    color: '#0d0f14',
    border: 'none',
    borderRadius: 8,
    padding: '10px 16px',
    fontWeight: 700,
    cursor: 'pointer',
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
    gap: 14,
    marginBottom: 18,
  },
  statCard: {
    background: 'rgba(22, 26, 35, 0.95)',
    borderRadius: 14,
    border: '1px solid #252b38',
    padding: '16px 18px',
  },
  statLabel: { color: '#7a8299', fontSize: 12, marginTop: 5 },
  filterRow: { display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' },
  searchInput: {
    flex: '1 1 260px',
    background: '#161a23',
    color: '#e8eaf0',
    border: '1px solid #252b38',
    borderRadius: 10,
    padding: '10px 14px',
    fontSize: 14,
  },
  select: {
    background: '#161a23',
    color: '#e8eaf0',
    border: '1px solid #252b38',
    borderRadius: 10,
    padding: '10px 14px',
    fontSize: 14,
  },
  eventBanner: {
    background: 'rgba(59, 130, 246, 0.12)',
    border: '1px solid rgba(59, 130, 246, 0.25)',
    color: '#93c5fd',
    borderRadius: 12,
    padding: '10px 14px',
    fontSize: 13,
    marginBottom: 16,
  },
  loadingState: {
    padding: 48,
    textAlign: 'center',
    color: '#98a2b3',
    background: 'rgba(22, 26, 35, 0.85)',
    border: '1px solid #252b38',
    borderRadius: 14,
  },
  layout: {
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 2fr) minmax(320px, 1fr)',
    gap: 18,
    alignItems: 'start',
  },
  mapPanel: {
    background: 'rgba(22, 26, 35, 0.95)',
    borderRadius: 18,
    border: '1px solid #252b38',
    padding: 18,
  },
  mapHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: 12,
    alignItems: 'flex-start',
    flexWrap: 'wrap',
    marginBottom: 16,
  },
  sectionTitle: { margin: 0, fontSize: 17, fontWeight: 700 },
  sectionCopy: { margin: '6px 0 0', color: '#98a2b3', fontSize: 13 },
  legend: { display: 'flex', gap: 12, flexWrap: 'wrap' },
  legendItem: { display: 'flex', alignItems: 'center', gap: 6, color: '#98a2b3', fontSize: 12 },
  legendDot: { width: 10, height: 10, borderRadius: 999 },
  mapCanvas: {
    position: 'relative',
    minHeight: 520,
    borderRadius: 16,
    overflow: 'hidden',
    background:
      'linear-gradient(180deg, rgba(17, 24, 39, 0.96) 0%, rgba(10, 16, 27, 0.98) 100%)',
    border: '1px solid #1f2430',
  },
  mapGrid: {
    position: 'absolute',
    inset: 0,
    backgroundImage:
      'linear-gradient(rgba(148, 163, 184, 0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(148, 163, 184, 0.08) 1px, transparent 1px)',
    backgroundSize: '56px 56px',
    maskImage: 'linear-gradient(180deg, rgba(0,0,0,0.88), rgba(0,0,0,0.45))',
  },
  marker: {
    position: 'absolute',
    transform: 'translate(-50%, -50%)',
    borderRadius: 999,
    border: '3px solid #f8fafc',
    cursor: 'pointer',
    transition: 'transform 0.15s ease, box-shadow 0.15s ease',
  },
  emptyState: {
    position: 'absolute',
    inset: 0,
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    textAlign: 'center',
    padding: 24,
  },
  sidebar: { display: 'grid', gap: 18 },
  sidebarCard: {
    background: 'rgba(22, 26, 35, 0.95)',
    borderRadius: 18,
    border: '1px solid #252b38',
    padding: 18,
  },
  selectedHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: 12,
    marginBottom: 12,
    alignItems: 'flex-start',
  },
  selectedId: { color: '#f5a623', fontSize: 20, fontWeight: 800 },
  selectedAddress: { color: '#98a2b3', fontSize: 13, marginTop: 4 },
  badge: {
    padding: '4px 10px',
    borderRadius: 999,
    fontSize: 11,
    fontWeight: 700,
    textTransform: 'uppercase',
  },
  detailRow: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: 12,
    padding: '10px 0',
    borderBottom: '1px solid #1f2430',
  },
  detailLabel: { color: '#7a8299', fontSize: 13 },
  detailValue: { color: '#e8eaf0', fontSize: 13, textAlign: 'right', maxWidth: '60%' },
  sidebarActions: { display: 'grid', gap: 10, marginTop: 16 },
  primaryButton: {
    background: '#f5a623',
    color: '#0d0f14',
    border: 'none',
    borderRadius: 10,
    padding: '11px 14px',
    fontWeight: 700,
    cursor: 'pointer',
  },
  linkButton: {
    display: 'inline-flex',
    justifyContent: 'center',
    alignItems: 'center',
    textDecoration: 'none',
    background: '#18202d',
    color: '#8ec5ff',
    border: '1px solid #273247',
    borderRadius: 10,
    padding: '11px 14px',
    fontWeight: 600,
  },
  complaintList: { display: 'grid', gap: 10, maxHeight: 440, overflowY: 'auto', marginTop: 14 },
  listItem: {
    background: '#121824',
    border: '1px solid #252b38',
    borderRadius: 14,
    padding: 12,
    cursor: 'pointer',
    textAlign: 'left',
  },
  listTopRow: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: 8,
    alignItems: 'center',
    marginBottom: 8,
  },
  listId: { color: '#f5a623', fontWeight: 700, fontSize: 13 },
  listAddress: { color: '#d8dee9', fontSize: 13, lineHeight: 1.4, marginBottom: 8 },
  listMeta: { display: 'flex', justifyContent: 'space-between', color: '#7a8299', fontSize: 12 },
  emptySidebarCopy: { color: '#98a2b3', fontSize: 13, margin: '14px 0 0' },
};
