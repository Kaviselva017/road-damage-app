import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../services/AuthContext';
import { api } from '../services/api';
import { formatDateTime } from '../utils/dateTime';

const SEVERITY_COLORS = { high: '#e05c5c', medium: '#f5a623', low: '#3ecfb2' };
const STATUS_COLORS = {
  pending: '#7a8299', assigned: '#f5a623',
  in_progress: '#3b82f6', completed: '#22c55e', rejected: '#e05c5c'
};

export default function Dashboard() {
  const { token, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [complaints, setComplaints] = useState([]);
  const [filter, setFilter] = useState({ status: '', severity: '' });
  const [loading, setLoading] = useState(true);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filter.status) params.status = filter.status;
      if (filter.severity) params.severity = filter.severity;
      const data = await api.getComplaints(token, params);
      setComplaints(data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  }, [token, filter.status, filter.severity]);

  const downloadPDF = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${api.baseUrl}/complaints/report/download`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) throw new Error('PDF download failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `RoadWatch_Report_${new Date().toISOString().slice(0,10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
      alert('Failed to download PDF');
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, [load]);

  const stats = {
    total: complaints.length,
    pending: complaints.filter(c => c.status === 'pending' || c.status === 'assigned').length,
    inProgress: complaints.filter(c => c.status === 'in_progress').length,
    completed: complaints.filter(c => c.status === 'completed').length,
    high: complaints.filter(c => c.severity === 'high').length,
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Officer Dashboard</h1>
          <p style={styles.subtitle}>Road Damage Complaint Management</p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          {isAdmin && (
            <button onClick={() => navigate('/admin')} style={{...styles.btnOutline, borderColor: '#f5a623', color: '#f5a623'}}>
              ⚙️ Admin Panel
            </button>
          )}
          <button onClick={downloadPDF} style={styles.btnPdf} disabled={loading}>
            {loading ? 'Processing...' : '📄 PDF Report'}
          </button>
          <button onClick={() => navigate('/map')} style={styles.btnOutline}>🗺 Map View</button>
          <button onClick={logout} style={styles.btnOutline}>Sign Out</button>
        </div>
      </div>

      {/* Stats */}
      <div style={styles.statsGrid}>
        {[
          { label: 'Total', value: stats.total, color: '#7a8299' },
          { label: 'Pending / Assigned', value: stats.pending, color: '#f5a623' },
          { label: 'In Progress', value: stats.inProgress, color: '#3b82f6' },
          { label: 'Completed', value: stats.completed, color: '#22c55e' },
          { label: '🔴 High Severity', value: stats.high, color: '#e05c5c' },
        ].map(s => (
          <div key={s.label} style={{ ...styles.statCard, borderTop: `3px solid ${s.color}` }}>
            <div style={{ fontSize: 28, fontWeight: 800, color: s.color }}>{s.value}</div>
            <div style={{ fontSize: 12, color: '#7a8299', marginTop: 4 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div style={styles.filterRow}>
        <select value={filter.status} onChange={e => setFilter(f => ({ ...f, status: e.target.value }))} style={styles.select}>
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="assigned">Assigned</option>
          <option value="in_progress">In Progress</option>
          <option value="completed">Completed</option>
        </select>
        <select value={filter.severity} onChange={e => setFilter(f => ({ ...f, severity: e.target.value }))} style={styles.select}>
          <option value="">All Severities</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <button onClick={load} style={styles.btnPrimary}>Refresh</button>
      </div>

      {/* Table */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40, color: '#7a8299' }}>Loading complaints...</div>
      ) : (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr style={{ background: '#161a23' }}>
                {['Complaint ID', 'Type', 'Severity', 'Location', 'Status', 'Date', 'Action'].map(h => (
                  <th key={h} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {complaints.length === 0 ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: 32, color: '#7a8299' }}>No complaints found</td></tr>
              ) : complaints.map(c => (
                <tr key={c.id} style={styles.tr}>
                  <td style={{ ...styles.td, color: '#f5a623', fontWeight: 700 }}>{c.complaint_id}</td>
                  <td style={styles.td}>{c.damage_type.replace('_', ' ')}</td>
                  <td style={styles.td}>
                    <span style={{ ...styles.badge, background: SEVERITY_COLORS[c.severity] + '22', color: SEVERITY_COLORS[c.severity] }}>
                      {c.severity.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ ...styles.td, fontSize: 12, color: '#7a8299' }}>
                    {c.address || `${c.latitude.toFixed(4)}, ${c.longitude.toFixed(4)}`}
                  </td>
                  <td style={styles.td}>
                    <span style={{ ...styles.badge, background: STATUS_COLORS[c.status] + '22', color: STATUS_COLORS[c.status] }}>
                      {c.status.replace('_', ' ').toUpperCase()}
                    </span>
                  </td>
                  <td style={{ ...styles.td, fontSize: 12, color: '#7a8299' }}>
                    {formatDateTime(c.created_at)}
                  </td>
                  <td style={styles.td}>
                    <button onClick={() => navigate(`/complaint/${c.complaint_id}`)} style={styles.btnSmall}>
                      View →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const styles = {
  container: { minHeight: '100vh', background: '#0d0f14', color: '#e8eaf0', padding: '24px 32px', fontFamily: 'system-ui, sans-serif' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 },
  title: { fontSize: 24, fontWeight: 800, margin: 0 },
  subtitle: { color: '#7a8299', margin: '4px 0 0', fontSize: 14 },
  statsGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 16, marginBottom: 24 },
  statCard: { background: '#161a23', borderRadius: 10, padding: '16px 20px', border: '1px solid #252b38' },
  filterRow: { display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' },
  select: { background: '#161a23', color: '#e8eaf0', border: '1px solid #252b38', borderRadius: 8, padding: '8px 14px', fontSize: 14 },
  tableWrap: { overflowX: 'auto', borderRadius: 12, border: '1px solid #252b38' },
  table: { width: '100%', borderCollapse: 'collapse', background: '#161a23' },
  th: { padding: '12px 16px', textAlign: 'left', fontSize: 12, fontWeight: 700, color: '#7a8299', letterSpacing: '0.06em', textTransform: 'uppercase', borderBottom: '1px solid #252b38' },
  td: { padding: '14px 16px', fontSize: 14, borderBottom: '1px solid #1c2130' },
  tr: { cursor: 'pointer', transition: 'background 0.15s' },
  badge: { padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 700 },
  btnPrimary: { background: '#f5a623', color: '#000', border: 'none', borderRadius: 8, padding: '8px 18px', fontWeight: 700, cursor: 'pointer' },
  btnOutline: { background: 'transparent', color: '#e8eaf0', border: '1px solid #252b38', borderRadius: 8, padding: '8px 16px', cursor: 'pointer', fontSize: 14 },
  btnSmall: { background: '#252b38', color: '#e8eaf0', border: 'none', borderRadius: 6, padding: '6px 14px', cursor: 'pointer', fontSize: 13 },
  btnPdf: { background: 'linear-gradient(135deg, #10b981, #059669)', color: '#fff', border: 'none', borderRadius: 8, padding: '8px 16px', cursor: 'pointer', fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' },
};
