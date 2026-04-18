import { useState, useEffect, useRef } from 'react';

export function useAdminFeed(token) {
  const [events, setEvents] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeout = useRef(null);
  const backoff = useRef(1000);

  useEffect(() => {
    if (!token) return;
    
    const connect = () => {
      let wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
      if (!wsUrl.startsWith('ws')) {
          wsUrl = wsUrl.replace(/^http/, 'ws');
      }
      wsRef.current = new WebSocket(`${wsUrl}/ws/admin/feed?token=${token}`);

      wsRef.current.onopen = () => {
        setIsConnected(true);
        backoff.current = 1000;
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastEvent(data);
          setEvents(prev => [...prev, data].slice(-100));
        } catch (e) {
          console.error("WS parse error", e);
        }
      };

      wsRef.current.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;
        reconnectTimeout.current = setTimeout(() => {
          backoff.current = Math.min(backoff.current * 1.5, 30000);
          connect();
        }, backoff.current);
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimeout.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, [token]);

  return { events, isConnected, lastEvent };
}
