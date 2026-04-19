// dashboard/src/components/LoginPage.tsx
import { GoogleLogin, GoogleOAuthProvider } from '@react-oauth/google'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string

function LoginForm() {
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSuccess = async (credentialResponse: { credential?: string }) => {
    if (!credentialResponse.credential) return
    const res = await fetch('/auth/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id_token: credentialResponse.credential }),
    })
    if (!res.ok) { alert('Login failed'); return }
    const data = await res.json()
    login(data.access_token, data.refresh_token, data.user)
    navigate('/dashboard')
  }

  return (
    <div style={{ display:'flex', flexDirection:'column', alignItems:'center',
                  justifyContent:'center', minHeight:'100vh', gap:24 }}>
      <h1 style={{ fontSize:22, fontWeight:500 }}>Road Damage Reporter</h1>
      <p style={{ color:'#666', fontSize:14 }}>Officer dashboard — sign in to continue</p>
      <GoogleLogin onSuccess={handleSuccess} onError={() => alert('Login failed')}
        useOneTap shape="rectangular" theme="outline" size="large"
        text="continue_with" locale="en" />
    </div>
  )
}

export default function LoginPage() {
  return (
    <GoogleOAuthProvider clientId={CLIENT_ID}>
      <LoginForm />
    </GoogleOAuthProvider>
  )
}
