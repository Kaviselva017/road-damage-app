import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { auth } from '../lib/firebase';
import { signInWithEmailAndPassword } from 'firebase/auth';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      await signInWithEmailAndPassword(auth, email, password);
      navigate('/');
    } catch (err) {
      setError('Invalid officer credentials or access denied.');
      console.error(err);
    }
    setLoading(false);
  };

  return (
    <div style={{ minHeight: '100vh', background: '#0d0f14', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ background: '#161a23', borderRadius: 16, padding: 40, width: 400, border: '1px solid #252b38', boxShadow: '0 20px 40px rgba(0,0,0,0.4)' }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ fontSize: 48, marginBottom: 8 }}>🛡️</div>
          <h1 style={{ color: '#f5a623', fontSize: 26, fontWeight: 800, margin: 0, letterSpacing: '-0.5px' }}>Officer Login</h1>
          <p style={{ color: '#7a8299', fontSize: 14, marginTop: 8 }}>Secure Access for Field Officers & Admins</p>
        </div>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ color: '#a0a7b8', fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6, textTransform: 'uppercase' }}>Work Email</label>
            <input
              type="email" value={email} onChange={e => setEmail(e.target.value)}
              placeholder="officer@roadwatch.gov" required
              style={{ width: '100%', background: '#0d0f14', color: '#e8eaf0', border: '1px solid #252b38', borderRadius: 8, padding: '12px 14px', fontSize: 15, boxSizing: 'border-box', outline: 'none' }}
            />
          </div>
          <div style={{ marginBottom: 24 }}>
            <label style={{ color: '#a0a7b8', fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6, textTransform: 'uppercase' }}>Security Password</label>
            <input
              type="password" value={password} onChange={e => setPassword(e.target.value)}
              placeholder="••••••••" required
              style={{ width: '100%', background: '#0d0f14', color: '#e8eaf0', border: '1px solid #252b38', borderRadius: 8, padding: '12px 14px', fontSize: 15, boxSizing: 'border-box', outline: 'none' }}
            />
          </div>
          {error && (
            <div style={{ background: 'rgba(224, 92, 92, 0.1)', border: '1px solid #e05c5c', borderRadius: 6, padding: '10px 12px', marginBottom: 20 }}>
              <p style={{ color: '#e05c5c', fontSize: 13, margin: 0, textAlign: 'center' }}>{error}</p>
            </div>
          )}
          <button type="submit" disabled={loading}
            style={{ width: '100%', background: '#f5a623', color: '#000', border: 'none', borderRadius: 8, padding: '14px', fontWeight: 700, cursor: 'pointer', fontSize: 16, transition: 'all 0.2s' }}>
            {loading ? 'Authenticating...' : 'Sign In Protected'}
          </button>
        </form>
        <div style={{ marginTop: 24, textAlign: 'center' }}>
          <p style={{ color: '#535b70', fontSize: 12 }}>
            Forgot password? Contact your administrator for a reset link.
          </p>
        </div>
      </div>
    </div>
  );
}
