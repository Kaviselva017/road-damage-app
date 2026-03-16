import { createContext, useContext, useState } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem('officer_token'));

  const login = (newToken) => {
    localStorage.setItem('officer_token', newToken);
    setToken(newToken);
  };
  const logout = () => {
    localStorage.removeItem('officer_token');
    setToken(null);
  };

  return (
    <AuthContext.Provider value={{ token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
