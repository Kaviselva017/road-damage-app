import { useNavigate } from 'react-router-dom';

export default function MapView() {
  const navigate = useNavigate();
  return (
    <div style={{ minHeight: '100vh', background: '#0d0f14', color: '#e8eaf0', padding: '24px 32px', fontFamily: 'system-ui, sans-serif' }}>
      <button onClick={() => navigate('/')} style={{ background: 'none', border: 'none', color: '#7a8299', cursor: 'pointer', marginBottom: 20, fontSize: 14 }}>
        ← Back to Dashboard
      </button>
      <h2 style={{ color: '#f5a623' }}>🗺 Live Map View</h2>
      <p style={{ color: '#7a8299', marginBottom: 20 }}>
        Integrate Google Maps API key in <code>VITE_GOOGLE_MAPS_KEY</code> and use the
        <code>@react-google-maps/api</code> package to render complaint markers by severity.
      </p>
      <div style={{ background: '#161a23', borderRadius: 12, padding: 40, border: '1px dashed #252b38', textAlign: 'center', color: '#7a8299' }}>
        Map renders here — add Google Maps API key to enable
      </div>
    </div>
  );
}
