import { useState, useEffect, useRef, useCallback } from 'react';

export function useAdminFeed() {
  const [events, setEvents] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [unseenCount, setUnseenCount] = useState(0);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const attemptRef = useRef(0);
  // Store connect in a ref so onclose can reference the latest version
  // without triggering the "accessed before declared" lint rule.
  const connectRef = useRef(null);

  const connect = useCallback(() => {
    const token = localStorage.getItem('officer_token');
    if (!token) return;

    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
    const derived = apiUrl
      .replace('https://', 'wss://')
      .replace('http://', 'ws://')
      .replace('/api', '');

    // Prefer an explicit WS URL env var; fall back to derived value.
    const wsBase = import.meta.env.VITE_WS_URL || derived;

    const ws = new WebSocket(`${wsBase}/ws/admin/feed?token=${token}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      attemptRef.current = 0;
    };

    ws.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        if (parsed.event === 'pong' || parsed.type === 'ping') return;
        setEvents((prev) => [parsed, ...prev].slice(0, 50));
        setUnseenCount((prev) => prev + 1);
      } catch {
        /* ignore malformed */
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      // Exponential backoff: 2s, 4s, 8s, 16s, capped at 30s
      const delay = Math.min(2 ** attemptRef.current * 1000, 30000);
      attemptRef.current += 1;
      // Use the ref to avoid the "accessed before declared" issue
      reconnectRef.current = setTimeout(() => connectRef.current?.(), delay);
    };

    ws.onerror = () => ws.close();
  }, []);

  // Keep the ref in sync with the latest connect callback
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const markAsSeen = useCallback(() => setUnseenCount(0), []);
  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, isConnected, unseenCount, markAsSeen, clearEvents };
}
