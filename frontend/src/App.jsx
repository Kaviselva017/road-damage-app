import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import ComplaintDetail from './pages/ComplaintDetail';
import MapView from './pages/MapView';
import AdminPanel from './pages/AdminPanel';
import { AuthProvider, useAuth } from './services/AuthContext';

import * as Sentry from "@sentry/react";

const SentryRoutes = Sentry.withSentryReactRouterV6Routing(Routes);

function ProtectedRoute({ children }) {
  const { token } = useAuth();
  return token ? children : <Navigate to="/login" />;
}

function AdminRoute({ children }) {
  const { token, isAdmin } = useAuth();
  if (!token) return <Navigate to="/login" />;
  return isAdmin ? children : <Navigate to="/" />;
}

export default function App() {
  return (
    <Sentry.ErrorBoundary
      fallback={
        <div style={{padding:'2rem',textAlign:'center'}}>
          <h2>Something went wrong</h2>
          <p>Our team has been notified automatically.</p>
          <button onClick={() => window.location.reload()}>Reload</button>
        </div>
      }
      showDialog={false}
    >
      <AuthProvider>
        <BrowserRouter>
          <SentryRoutes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/complaint/:id" element={<ProtectedRoute><ComplaintDetail /></ProtectedRoute>} />
            <Route path="/map" element={<ProtectedRoute><MapView /></ProtectedRoute>} />
            <Route path="/admin" element={<AdminRoute><AdminPanel /></AdminRoute>} />
          </SentryRoutes>
        </BrowserRouter>
      </AuthProvider>
    </Sentry.ErrorBoundary>
  );
}
