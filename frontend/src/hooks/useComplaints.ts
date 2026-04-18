/**
 * frontend/src/hooks/useComplaints.ts
 * =====================================
 * React hook that maintains a user-keyed WebSocket connection to the
 * RoadWatch backend (/ws/user/{userId}).
 *
 * Features:
 *  - Native WebSocket (no third-party lib)
 *  - Exponential back-off reconnect: 1s → 2s → 4s … capped at 30s
 *  - Tracks isConnected + lastEvent
 *  - Appends incoming events to a useState array
 *  - Responds to server "ping" with "pong" automatically
 */

import { useCallback, useEffect, useRef, useState } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface WsEvent {
  event: string;
  complaint_id?: string | number;
  status?: string;
  severity?: string;
  damage_type?: string;
  confidence?: number;
  timestamp?: string;
  [key: string]: unknown;
}

export interface UseWebSocketResult {
  complaints: WsEvent[];
  isConnected: boolean;
  lastEvent: WsEvent | null;
  clearEvents: () => void;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const BASE_URL =
  (import.meta as any).env?.VITE_WS_URL ||
  (window.location.protocol === "https:" ? "wss" : "ws") +
    "://" +
    window.location.host;

const MAX_BACKOFF_MS = 30_000;
const INITIAL_BACKOFF_MS = 1_000;

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useWebSocket(
  token: string,
  userId: string | number,
  enabled: boolean = true
): UseWebSocketResult {
  const [complaints, setComplaints] = useState<WsEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WsEvent | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef<number>(INITIAL_BACKOFF_MS);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);

  const clearEvents = useCallback(() => setComplaints([]), []);

  const connect = useCallback(() => {
    if (!enabled || !token || !userId) return;
    if (unmountedRef.current) return;

    const url = `${BASE_URL}/ws/user/${userId}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (unmountedRef.current) { ws.close(); return; }
      setIsConnected(true);
      backoffRef.current = INITIAL_BACKOFF_MS; // reset on successful connect
    };

    ws.onmessage = (ev: MessageEvent) => {
      if (unmountedRef.current) return;
      try {
        const data: WsEvent = JSON.parse(ev.data as string);

        // Respond to heartbeat ping immediately
        if (data.event === "ping") {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ event: "pong" }));
          }
          return;
        }

        setLastEvent(data);
        setComplaints((prev) => [data, ...prev].slice(0, 200)); // keep last 200
      } catch {
        // non-JSON message — ignore
      }
    };

    ws.onclose = () => {
      if (unmountedRef.current) return;
      setIsConnected(false);
      wsRef.current = null;
      scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose will fire right after — reconnect handled there
      ws.close();
    };
  }, [token, userId, enabled]); // eslint-disable-line react-hooks/exhaustive-deps

  const scheduleReconnect = useCallback(() => {
    if (unmountedRef.current) return;
    const delay = Math.min(backoffRef.current, MAX_BACKOFF_MS);
    backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
    retryTimerRef.current = setTimeout(() => {
      if (!unmountedRef.current) connect();
    }, delay);
  }, [connect]);

  useEffect(() => {
    unmountedRef.current = false;

    if (enabled && token && userId) {
      connect();
    }

    return () => {
      unmountedRef.current = true;
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on intentional close
        wsRef.current.close();
      }
    };
  }, [connect, enabled, token, userId]);

  return { complaints, isConnected, lastEvent, clearEvents };
}

// ── Re-export for convenience ─────────────────────────────────────────────────
export default useWebSocket;
