import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../services/AuthContext';
import { api } from '../services/api';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const data = await api.officerLogin(email, password);
      login(data.access_token);
      navigate('/');
    } catch (err) {
      setError('Invalid credentials. Please try again.');
    }
    setLoading(false);
  };

  return (
    <div style={{ minHeight: '100vh', background: '#0d0f14', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ background: '#161a23', borderRadius: 16, padding: 40, width: 380, border: '1px solid #252b38' }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>🛣️</div>
          <h1 style={{ color: '#f5a623', fontSize: 22, fontWeight: 800, margin: 0 }}>Officer Portal</h1>
          <p style={{ color: '#7a8299', fontSize: 14, marginTop: 4 }}>Road Damage Management System</p>
        </div>
        <form onSubmit={handleSubmit}>
          <input
            type="email" value={email} onChange={e => setEmail(e.target.value)}
            placeholder="Officer Email" required
            style={{ width: '100%', background: '#0d0f14', color: '#e8eaf0', border: '1px solid #252b38', borderRadius: 8, padding: '12px 14px', fontSize: 14, marginBottom: 12, boxSizing: 'border-box' }}
          />
          <input
            type="password" value={password} onChange={e => setPassword(e.target.value)}
            placeholder="Password" required
            style={{ width: '100%', background: '#0d0f14', color: '#e8eaf0', border: '1px solid #252b38', borderRadius: 8, padding: '12px 14px', fontSize: 14, marginBottom: 16, boxSizing: 'border-box' }}
          />
          {error && <p style={{ color: '#e05c5c', fontSize: 13, marginBottom: 12 }}>{error}</p>}
          <button type="submit" disabled={loading}
            style={{ width: '100%', background: '#f5a623', color: '#000', border: 'none', borderRadius: 8, padding: '13px', fontWeight: 700, cursor: 'pointer', fontSize: 15 }}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}
