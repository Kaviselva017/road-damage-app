import { createContext, useContext, useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { auth } from '../lib/firebase';
import { onAuthStateChanged, signOut } from 'firebase/auth';

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (fbUser) => {
      if (fbUser) {
        const idToken = await fbUser.getIdToken();
        setToken(idToken);
        
        // Sync with backend to get details and verify admin status
        try {
          const res = await fetch(`${import.meta.env.VITE_API_URL}/auth/sync-officer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id_token: idToken }),
          });
          const profile = await res.json();
          if (res.ok) {
            setUser(profile);
            setIsAdmin(profile.is_admin || false);
          } else {
            console.error('Officer sync failed', profile);
            setUser(null);
            setIsAdmin(false);
            // If they are logged into Firebase but not authorized in our backend, they might be a citizen
            // but the dashboard is for officers/admin.
          }
        } catch (error) {
          console.error('Auth sync error', error);
        }
      } else {
        setUser(null);
        setToken(null);
        setIsAdmin(false);
      }
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  const logout = () => signOut(auth);

  const value = {
    user,
    token,
    isAdmin,
    logout,
    loading
  };

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

AuthProvider.propTypes = {
  children: PropTypes.node.isRequired,
};
