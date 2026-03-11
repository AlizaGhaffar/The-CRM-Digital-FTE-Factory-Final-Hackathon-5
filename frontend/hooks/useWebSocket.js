/**
 * frontend/hooks/useWebSocket.js
 *
 * NimbusFlow — Real-time WebSocket hook
 *
 * Features:
 *   - Auto-connect on mount, auto-disconnect on unmount
 *   - Exponential back-off reconnect (up to MAX_DELAY_MS)
 *   - Heartbeat ping/pong to detect stale connections
 *   - Per-event-type subscriber registry (decoupled from React tree)
 *   - Auth token sent in initial handshake message
 *   - Message envelope: { type: string, payload: any, ts: ISO string }
 *
 * Usage:
 *   import { useWebSocket } from '@/hooks/useWebSocket';
 *
 *   function Dashboard() {
 *     const { status, on, send } = useWebSocket();
 *
 *     useEffect(() => {
 *       const off = on('ticket.new', (payload) => {
 *         setTickets(prev => [payload, ...prev]);
 *       });
 *       return off; // unsubscribe on unmount
 *     }, [on]);
 *   }
 *
 * Environment variable:
 *   NEXT_PUBLIC_WS_URL  or  VITE_WS_URL
 *   Defaults to ws://localhost:8000/ws
 */

import { useState, useEffect, useRef, useCallback } from 'react';

// ── Config ─────────────────────────────────────────────────────────────────

const WS_URL =
  (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_WS_URL) ||
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_WS_URL) ||
  'ws://localhost:8000/ws';

const INITIAL_DELAY_MS  = 1_000;   // first reconnect wait
const MAX_DELAY_MS      = 30_000;  // cap reconnect back-off
const HEARTBEAT_INTERVAL= 25_000;  // ping interval
const HEARTBEAT_TIMEOUT = 10_000;  // pong must arrive within this window
const MAX_RECONNECTS    = 10;      // give up after N consecutive failures

// ── Connection status enum ──────────────────────────────────────────────────

export const WS_STATUS = {
  CONNECTING:    'connecting',
  CONNECTED:     'connected',
  RECONNECTING:  'reconnecting',
  DISCONNECTED:  'disconnected',
  FAILED:        'failed',        // exceeded MAX_RECONNECTS
};

// ── Event types (reference) ─────────────────────────────────────────────────

export const WS_EVENTS = {
  // Inbound (server → client)
  TICKET_NEW:         'ticket.new',
  TICKET_UPDATED:     'ticket.updated',
  TICKET_RESOLVED:    'ticket.resolved',
  ESCALATION_NEW:     'escalation.new',
  ESCALATION_CLAIMED: 'escalation.claimed',
  MESSAGE_NEW:        'message.new',
  AGENT_TYPING:       'agent.typing',
  METRICS_UPDATE:     'metrics.update',
  ACTIVITY_EVENT:     'activity.event',
  SENTIMENT_ALERT:    'sentiment.alert',
  KB_UPDATED:         'kb.updated',
  SYSTEM_NOTICE:      'system.notice',
  PONG:               'pong',

  // Outbound (client → server)
  PING:               'ping',
  SUBSCRIBE:          'subscribe',
  UNSUBSCRIBE:        'unsubscribe',
  RESPOND:            'respond',
  CLAIM_ESCALATION:   'claim_escalation',
};

// ── Token helper (shared with api.js pattern) ───────────────────────────────

function getToken() {
  return typeof localStorage !== 'undefined' ? localStorage.getItem('nf_token') : null;
}

// ── useWebSocket hook ───────────────────────────────────────────────────────

/**
 * @param {object}  options
 * @param {string}  [options.url]            — WebSocket URL (overrides env default)
 * @param {boolean} [options.enabled=true]   — set false to keep disconnected
 * @param {string[]}[options.channels]       — channel names to subscribe to on connect
 * @param {(event: MessageEvent) => void} [options.onRawMessage] — bypass parsed routing
 */
export function useWebSocket({
  url      = WS_URL,
  enabled  = true,
  channels = [],
  onRawMessage,
} = {}) {
  const [status,        setStatus]        = useState(WS_STATUS.DISCONNECTED);
  const [lastEventTime, setLastEventTime] = useState(null);
  const [reconnectCount,setReconnectCount]= useState(0);

  const wsRef           = useRef(null);       // WebSocket instance
  const listenersRef    = useRef({});         // { eventType: Set<fn> }
  const reconnectTimer  = useRef(null);
  const heartbeatTimer  = useRef(null);
  const pongTimer       = useRef(null);
  const reconnectDelay  = useRef(INITIAL_DELAY_MS);
  const reconnectsLeft  = useRef(MAX_RECONNECTS);
  const mountedRef      = useRef(true);
  const channelsRef     = useRef(channels);
  channelsRef.current   = channels;

  // ── Emit to local subscribers ──────────────────────────────────────────

  const emit = useCallback((type, payload) => {
    setLastEventTime(new Date());
    const fns = listenersRef.current[type];
    if (fns) fns.forEach(fn => { try { fn(payload); } catch(e) { console.error('[ws] subscriber error', e); } });
    // Also fire wildcard '*' listeners
    const wildcards = listenersRef.current['*'];
    if (wildcards) wildcards.forEach(fn => { try { fn(type, payload); } catch(e) { /* ignore */ } });
  }, []);

  // ── Send a message ─────────────────────────────────────────────────────

  const send = useCallback((type, payload = {}) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn('[ws] send called while not connected, dropping:', type);
      return false;
    }
    ws.send(JSON.stringify({ type, payload, ts: new Date().toISOString() }));
    return true;
  }, []);

  // ── Heartbeat ──────────────────────────────────────────────────────────

  const startHeartbeat = useCallback(() => {
    clearInterval(heartbeatTimer.current);
    heartbeatTimer.current = setInterval(() => {
      if (wsRef.current?.readyState !== WebSocket.OPEN) return;
      send(WS_EVENTS.PING);
      // Expect pong within HEARTBEAT_TIMEOUT
      pongTimer.current = setTimeout(() => {
        console.warn('[ws] pong timeout — closing stale connection');
        wsRef.current?.close(4001, 'Heartbeat timeout');
      }, HEARTBEAT_TIMEOUT);
    }, HEARTBEAT_INTERVAL);
  }, [send]);

  const stopHeartbeat = useCallback(() => {
    clearInterval(heartbeatTimer.current);
    clearTimeout(pongTimer.current);
  }, []);

  // ── Connect ────────────────────────────────────────────────────────────

  const connect = useCallback(() => {
    if (!mountedRef.current || !enabled) return;
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) return;

    setStatus(reconnectsLeft.current < MAX_RECONNECTS ? WS_STATUS.RECONNECTING : WS_STATUS.CONNECTING);

    let ws;
    try {
      ws = new WebSocket(url);
    } catch (err) {
      console.error('[ws] failed to construct WebSocket:', err);
      scheduleReconnect();
      return;
    }

    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) { ws.close(); return; }
      setStatus(WS_STATUS.CONNECTED);
      setReconnectCount(0);
      reconnectDelay.current  = INITIAL_DELAY_MS;
      reconnectsLeft.current  = MAX_RECONNECTS;

      // Auth handshake
      const tok = getToken();
      if (tok) ws.send(JSON.stringify({ type: 'auth', payload: { token: tok }, ts: new Date().toISOString() }));

      // Subscribe to requested channels
      if (channelsRef.current.length > 0) {
        ws.send(JSON.stringify({ type: WS_EVENTS.SUBSCRIBE, payload: { channels: channelsRef.current }, ts: new Date().toISOString() }));
      }

      startHeartbeat();
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      onRawMessage?.(event);
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === WS_EVENTS.PONG) clearTimeout(pongTimer.current);
        emit(msg.type, msg.payload ?? msg);
      } catch {
        console.warn('[ws] received non-JSON message:', event.data);
      }
    };

    ws.onclose = (evt) => {
      stopHeartbeat();
      if (!mountedRef.current) return;
      // 1000 = normal close, 4000+ = app-controlled clean close
      if (evt.code === 1000 || evt.code === 4000) {
        setStatus(WS_STATUS.DISCONNECTED);
        return;
      }
      scheduleReconnect();
    };

    ws.onerror = (err) => {
      console.error('[ws] error:', err);
      // onclose will fire next and schedule reconnect
    };
  }, [url, enabled, emit, startHeartbeat, stopHeartbeat, onRawMessage]);

  // ── Reconnect with back-off ────────────────────────────────────────────

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return;
    reconnectsLeft.current -= 1;
    if (reconnectsLeft.current <= 0) {
      setStatus(WS_STATUS.FAILED);
      console.error('[ws] max reconnects reached — giving up');
      return;
    }
    setReconnectCount(c => c + 1);
    const delay = reconnectDelay.current;
    reconnectDelay.current = Math.min(delay * 2, MAX_DELAY_MS);
    console.info(`[ws] reconnecting in ${delay}ms (${reconnectsLeft.current} attempts left)`);
    reconnectTimer.current = setTimeout(connect, delay);
  }, [connect]);

  // ── Disconnect ─────────────────────────────────────────────────────────

  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimer.current);
    stopHeartbeat();
    wsRef.current?.close(4000, 'Client disconnect');
    wsRef.current = null;
    setStatus(WS_STATUS.DISCONNECTED);
  }, [stopHeartbeat]);

  // ── Reconnect manually ─────────────────────────────────────────────────

  const reconnect = useCallback(() => {
    reconnectsLeft.current = MAX_RECONNECTS;
    reconnectDelay.current = INITIAL_DELAY_MS;
    disconnect();
    setTimeout(connect, 100);
  }, [connect, disconnect]);

  // ── Subscribe to an event type ─────────────────────────────────────────
  // Returns an unsubscribe function

  const on = useCallback((eventType, handler) => {
    if (!listenersRef.current[eventType]) listenersRef.current[eventType] = new Set();
    listenersRef.current[eventType].add(handler);
    return () => {
      listenersRef.current[eventType]?.delete(handler);
    };
  }, []);

  // ── Subscribe to multiple event types at once ──────────────────────────

  const onAny = useCallback((eventMap) => {
    const offs = Object.entries(eventMap).map(([type, fn]) => on(type, fn));
    return () => offs.forEach(off => off());
  }, [on]);

  // ── Mount / unmount ────────────────────────────────────────────────────

  useEffect(() => {
    mountedRef.current = true;
    if (enabled) connect();
    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectTimer.current);
      stopHeartbeat();
      wsRef.current?.close(4000, 'Component unmount');
    };
  }, [enabled]); // re-run if enabled toggles

  // ── Expose convenience senders ─────────────────────────────────────────

  const claimEscalation = useCallback((ticketId, agentName) =>
    send(WS_EVENTS.CLAIM_ESCALATION, { ticket_id: ticketId, agent: agentName }), [send]);

  const sendTyping = useCallback((ticketId) =>
    send(WS_EVENTS.AGENT_TYPING, { ticket_id: ticketId }), [send]);

  const subscribeChannel = useCallback((channelName) =>
    send(WS_EVENTS.SUBSCRIBE, { channels: [channelName] }), [send]);

  const unsubscribeChannel = useCallback((channelName) =>
    send(WS_EVENTS.UNSUBSCRIBE, { channels: [channelName] }), [send]);

  return {
    // State
    status,
    connected: status === WS_STATUS.CONNECTED,
    reconnectCount,
    lastEventTime,

    // Core API
    on,
    onAny,
    send,
    disconnect,
    reconnect,

    // Convenience senders
    claimEscalation,
    sendTyping,
    subscribeChannel,
    unsubscribeChannel,
  };
}

// ── useTicketEvents — convenience hook for ticket/escalation streams ─────────

/**
 * Pre-wired event handlers for the most common real-time needs.
 *
 * @param {object} handlers
 * @param {(ticket: object) => void}     [handlers.onNewTicket]
 * @param {(ticket: object) => void}     [handlers.onTicketUpdated]
 * @param {(ticket: object) => void}     [handlers.onTicketResolved]
 * @param {(esc: object) => void}        [handlers.onNewEscalation]
 * @param {(esc: object) => void}        [handlers.onEscalationClaimed]
 * @param {(msg: object) => void}        [handlers.onNewMessage]
 * @param {(metrics: object) => void}    [handlers.onMetricsUpdate]
 * @param {(alert: object) => void}      [handlers.onSentimentAlert]
 * @param {(event: object) => void}      [handlers.onActivityEvent]
 */
export function useTicketEvents(handlers = {}, wsOptions = {}) {
  const ws = useWebSocket(wsOptions);

  useEffect(() => {
    const {
      onNewTicket, onTicketUpdated, onTicketResolved,
      onNewEscalation, onEscalationClaimed,
      onNewMessage, onMetricsUpdate, onSentimentAlert, onActivityEvent,
    } = handlers;

    const map = {
      ...(onNewTicket        && { [WS_EVENTS.TICKET_NEW]:         onNewTicket }),
      ...(onTicketUpdated    && { [WS_EVENTS.TICKET_UPDATED]:     onTicketUpdated }),
      ...(onTicketResolved   && { [WS_EVENTS.TICKET_RESOLVED]:    onTicketResolved }),
      ...(onNewEscalation    && { [WS_EVENTS.ESCALATION_NEW]:     onNewEscalation }),
      ...(onEscalationClaimed&& { [WS_EVENTS.ESCALATION_CLAIMED]: onEscalationClaimed }),
      ...(onNewMessage       && { [WS_EVENTS.MESSAGE_NEW]:        onNewMessage }),
      ...(onMetricsUpdate    && { [WS_EVENTS.METRICS_UPDATE]:     onMetricsUpdate }),
      ...(onSentimentAlert   && { [WS_EVENTS.SENTIMENT_ALERT]:    onSentimentAlert }),
      ...(onActivityEvent    && { [WS_EVENTS.ACTIVITY_EVENT]:     onActivityEvent }),
    };

    return ws.onAny(map);
  // handlers object identity changes each render, so we depend on the functions directly
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    ws.onAny,
    handlers.onNewTicket, handlers.onTicketUpdated, handlers.onTicketResolved,
    handlers.onNewEscalation, handlers.onEscalationClaimed,
    handlers.onNewMessage, handlers.onMetricsUpdate,
    handlers.onSentimentAlert, handlers.onActivityEvent,
  ]);

  return ws;
}

// ── useConnectionStatus — lightweight status-only hook ──────────────────────

export function useConnectionStatus() {
  const { status, connected, reconnectCount, lastEventTime, reconnect } = useWebSocket();
  return { status, connected, reconnectCount, lastEventTime, reconnect };
}

export default useWebSocket;
