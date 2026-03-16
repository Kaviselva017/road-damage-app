import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../services/AuthContext';
import { api } from '../services/api';

const SEVERITY_COLORS = { high: '#e05c5c', medium: '#f5a623', low: '#3ecfb2' };

export default function ComplaintDetail() {
  const { id } = useParams();
  const { token } = useAuth();
  const navigate = useNavigate();
  const [complaint, setComplaint] = useState(null);
  const [status, setStatus] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getComplaint(token, id).then(c => {
      setComplaint(c);
      setStatus(c.status);
      setNotes(c.officer_notes || '');
    });
  }, [id]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.updateStatus(token, id, status, notes);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) { alert(e.message); }
    setSaving(false);
  };

  if (!complaint) return <div style={{ color: '#fff', padding: 40, background: '#0d0f14', minHeight: '100vh' }}>Loading...</div>;

  const BASE = import.meta.env.VITE_API_URL?.replace('/api', '') || 'http://localhost:8000';

  return (
    <div style={{ minHeight: '100vh', background: '#0d0f14', color: '#e8eaf0', padding: '24px 32px', fontFamily: 'system-ui, sans-serif' }}>
      <button onClick={() => navigate('/')} style={{ background: 'none', border: 'none', color: '#7a8299', cursor: 'pointer', marginBottom: 20, fontSize: 14 }}>
        ← Back to Dashboard
      </button>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, maxWidth: 1000 }}>
        {/* Left: Image + AI results */}
        <div>
          <img
            src={`${BASE}${complaint.image_url}`}
            alt="Road damage"
            style={{ width: '100%', borderRadius: 12, border: '2px solid #252b38' }}
          />
          <div style={{ background: '#161a23', borderRadius: 12, padding: 20, marginTop: 16, border: '1px solid #252b38' }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 14, color: '#7a8299', textTransform: 'uppercase', letterSpacing: '0.08em' }}>AI Detection Results</h3>
            <Row label="Damage Type" value={complaint.damage_type.replace('_', ' ')} />
            <Row label="Severity" value={complaint.severity.toUpperCase()} color={SEVERITY_COLORS[complaint.severity]} />
            <Row label="AI Confidence" value={`${(complaint.ai_confidence * 100).toFixed(1)}%`} />
            <Row label="Description" value={complaint.description} />
          </div>
        </div>

        {/* Right: Details + Update */}
        <div>
          <div style={{ background: '#161a23', borderRadius: 12, padding: 20, border: '1px solid #252b38', marginBottom: 16 }}>
            <h2 style={{ margin: '0 0 4px', color: '#f5a623' }}>{complaint.complaint_id}</h2>
            <p style={{ color: '#7a8299', margin: '0 0 16px', fontSize: 13 }}>
              Reported {new Date(complaint.created_at).toLocaleString()}
            </p>
            <Row label="Latitude" value={complaint.latitude} />
            <Row label="Longitude" value={complaint.longitude} />
            {complaint.address && <Row label="Address" value={complaint.address} />}
            <div style={{ marginTop: 12 }}>
              <a
                href={`https://maps.google.com/?q=${complaint.latitude},${complaint.longitude}`}
                target="_blank" rel="noreferrer"
                style={{ color: '#3ecfb2', fontSize: 13 }}>
                📍 View on Google Maps →
              </a>
            </div>
          </div>

          <div style={{ background: '#161a23', borderRadius: 12, padding: 20, border: '1px solid #252b38' }}>
            <h3 style={{ margin: '0 0 16px', fontSize: 14, color: '#7a8299', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Update Status</h3>
            <select
              value={status}
              onChange={e => setStatus(e.target.value)}
              style={{ width: '100%', background: '#0d0f14', color: '#e8eaf0', border: '1px solid #252b38', borderRadius: 8, padding: '10px 14px', fontSize: 14, marginBottom: 12 }}>
              <option value="pending">Pending</option>
              <option value="assigned">Assigned</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
              <option value="rejected">Rejected</option>
            </select>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Add inspection notes..."
              rows={4}
              style={{ width: '100%', background: '#0d0f14', color: '#e8eaf0', border: '1px solid #252b38', borderRadius: 8, padding: 12, fontSize: 14, resize: 'vertical', boxSizing: 'border-box' }}
            />
            <button
              onClick={handleSave}
              disabled={saving}
              style={{ marginTop: 12, width: '100%', background: saved ? '#22c55e' : '#f5a623', color: '#000', border: 'none', borderRadius: 8, padding: '12px', fontWeight: 700, cursor: 'pointer', fontSize: 15 }}>
              {saving ? 'Saving...' : saved ? '✓ Saved!' : 'Update Status'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, color }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
      <span style={{ color: '#7a8299', fontSize: 13 }}>{label}</span>
      <span style={{ color: color || '#e8eaf0', fontSize: 13, fontWeight: 500, maxWidth: '60%', textAlign: 'right' }}>{value}</span>
    </div>
  );
}
