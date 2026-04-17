import { createContext, useContext, useState, useEffect } from 'react';
import { jwtDecode } from 'jwt-decode';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem('officer_token'));
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    if (token) {
      try {
        const decoded = jwtDecode(token);
        setIsAdmin(decoded.role === 'admin' || decoded.is_admin === true);
        
        // --- Sentry User Identification ---
        import('@sentry/react').then(Sentry => {
          Sentry.setUser({ 
            id: decoded.sub, 
            role: decoded.role,
            is_admin: decoded.role === 'admin' 
          });
        });
      } catch (e) {
        setIsAdmin(false);
      }
    } else {
      setIsAdmin(false);
      import('@sentry/react').then(Sentry => Sentry.setUser(null));
    }
  }, [token]);

  const login = (newToken) => {
    localStorage.setItem('officer_token', newToken);
    setToken(newToken);
  };
  const logout = () => {
    localStorage.removeItem('officer_token');
    setToken(null);
  };

  return (
    <AuthContext.Provider value={{ token, login, logout, isAdmin }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
