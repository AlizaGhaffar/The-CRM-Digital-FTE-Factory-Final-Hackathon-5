/**
 * frontend/components/AdminDashboard.jsx
 *
 * NimbusFlow — Admin Dashboard
 * Real-time overview of the Customer Success FTE system.
 * Supports dark/light mode, auto-refresh, and live activity feed.
 *
 * API endpoints used:
 *   GET /api/metrics          — system metrics + channel breakdown
 *   GET /api/tickets          — recent tickets list
 *   GET /api/activity         — live activity feed
 *   POST /support/ticket/{id}/escalate — escalate from table
 *
 * Usage (Next.js):
 *   import AdminDashboard from '@/components/AdminDashboard';
 *   export default function AdminPage() {
 *     return <AdminDashboard apiBase="" refreshInterval={30000} />;
 *   }
 *
 * Requirements: React 18+, Tailwind CSS
 */

import { useState, useEffect, useCallback, useRef } from 'react';

// ── Mock data (fallback when API is unavailable) ───────────────────────────

const MOCK_METRICS = {
  total_tickets:        1284,
  total_tickets_trend:  12.5,
  avg_response_time_ms: 1840,
  response_time_target: 2000,
  active_conversations: 37,
  escalations_count:    24,
  escalation_rate:      18.7,
  channels: {
    email:    { count: 612, avg_sentiment: 0.48, escalation_rate: 22.1, avg_response_ms: 2100 },
    whatsapp: { count: 418, avg_sentiment: 0.73, escalation_rate: 12.4, avg_response_ms: 1400 },
    web_form: { count: 254, avg_sentiment: 0.61, escalation_rate: 21.3, avg_response_ms: 1900 },
  },
};

const MOCK_TICKETS = [
  { ticket_id: '3f8a2c1d-4b5e-6789-abcd-ef0123456789', customer_email: 'alice@corp.com',  channel: 'email',    subject: 'GitHub integration not syncing',     status: 'open',        priority: 'high',   created_at: new Date(Date.now() - 4 * 60000).toISOString() },
  { ticket_id: 'a1b2c3d4-5e6f-7890-bcde-f01234567890', customer_email: 'bob@startup.io',  channel: 'whatsapp', subject: 'API rate limit exceeded',             status: 'in_progress', priority: 'high',   created_at: new Date(Date.now() - 12 * 60000).toISOString() },
  { ticket_id: 'b2c3d4e5-6f70-8901-cdef-012345678901', customer_email: 'carol@tech.dev',  channel: 'web_form', subject: 'Cannot export CSV report',            status: 'resolved',    priority: 'medium', created_at: new Date(Date.now() - 28 * 60000).toISOString() },
  { ticket_id: 'c3d4e5f6-7081-9012-def0-123456789012', customer_email: 'dave@bigco.com',  channel: 'email',    subject: 'SSO configuration help needed',       status: 'escalated',   priority: 'high',   created_at: new Date(Date.now() - 45 * 60000).toISOString() },
  { ticket_id: 'd4e5f607-8192-0123-ef01-234567890123', customer_email: 'eve@design.co',   channel: 'whatsapp', subject: 'Dashboard charts not loading',        status: 'open',        priority: 'medium', created_at: new Date(Date.now() - 67 * 60000).toISOString() },
  { ticket_id: 'e5f60718-9203-1234-f012-345678901234', customer_email: 'frank@media.io',  channel: 'web_form', subject: 'Billing cycle question',              status: 'open',        priority: 'low',    created_at: new Date(Date.now() - 92 * 60000).toISOString() },
];

const MOCK_ACTIVITY = [
  { id: 1, type: 'ticket_opened',   channel: 'email',    message: 'alice@corp.com opened a new ticket',         time: new Date(Date.now() - 2 * 60000).toISOString() },
  { id: 2, type: 'escalated',       channel: 'whatsapp', message: 'dave@bigco.com escalated to human agent',    time: new Date(Date.now() - 5 * 60000).toISOString() },
  { id: 3, type: 'resolved',        channel: 'web_form', message: 'carol@tech.dev ticket resolved by AI',       time: new Date(Date.now() - 9 * 60000).toISOString() },
  { id: 4, type: 'ticket_opened',   channel: 'whatsapp', message: 'bob@startup.io opened a new ticket',         time: new Date(Date.now() - 14 * 60000).toISOString() },
  { id: 5, type: 'reply_sent',      channel: 'email',    message: 'AI replied to frank@media.io in 1.2s',       time: new Date(Date.now() - 18 * 60000).toISOString() },
  { id: 6, type: 'ticket_opened',   channel: 'web_form', message: 'eve@design.co opened a new ticket',          time: new Date(Date.now() - 23 * 60000).toISOString() },
  { id: 7, type: 'sentiment_alert', channel: 'email',    message: 'Low sentiment (0.22) detected — monitoring', time: new Date(Date.now() - 31 * 60000).toISOString() },
];

// ── Config ─────────────────────────────────────────────────────────────────

const STATUS_CFG = {
  open:        { label: 'Open',        light: 'bg-blue-100 text-blue-700 ring-blue-200',   dark: 'bg-blue-900/50 text-blue-300 ring-blue-700',   dot: 'bg-blue-500' },
  in_progress: { label: 'In Progress', light: 'bg-amber-100 text-amber-700 ring-amber-200', dark: 'bg-amber-900/40 text-amber-300 ring-amber-700', dot: 'bg-amber-400 animate-pulse' },
  resolved:    { label: 'Resolved',    light: 'bg-green-100 text-green-700 ring-green-200', dark: 'bg-green-900/40 text-green-300 ring-green-700', dot: 'bg-green-500' },
  escalated:   { label: 'Escalated',   light: 'bg-red-100 text-red-700 ring-red-200',       dark: 'bg-red-900/40 text-red-300 ring-red-700',       dot: 'bg-red-500 animate-pulse' },
};

const PRIORITY_CFG = {
  high:   { light: 'text-red-600',    dark: 'text-red-400' },
  medium: { light: 'text-amber-600',  dark: 'text-amber-400' },
  low:    { light: 'text-green-600',  dark: 'text-green-400' },
};

const ACTIVITY_CFG = {
  ticket_opened:   { icon: '🎫', color: 'bg-blue-500' },
  escalated:       { icon: '🔺', color: 'bg-red-500' },
  resolved:        { icon: '✅', color: 'bg-green-500' },
  reply_sent:      { icon: '💬', color: 'bg-indigo-500' },
  sentiment_alert: { icon: '⚠️', color: 'bg-amber-500' },
};

// ── Icon components ─────────────────────────────────────────────────────────

function EmailIcon({ className }) {
  return <svg className={className} viewBox="0 0 20 20" fill="currentColor"><path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z"/><path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z"/></svg>;
}
function WhatsAppIcon({ className }) {
  return <svg className={className} viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.127.558 4.126 1.532 5.862L.072 23.928l6.243-1.636A11.935 11.935 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.818 9.818 0 01-5.009-1.374l-.36-.213-3.708.972.989-3.617-.233-.371A9.818 9.818 0 1112 21.818z"/></svg>;
}
function WebIcon({ className }) {
  return <svg className={className} viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M4.083 9h1.946c.089-1.546.383-2.97.837-4.118A6.004 6.004 0 004.083 9zM10 2a8 8 0 100 16A8 8 0 0010 2zm0 2c-.076 0-.232.032-.465.262-.238.234-.497.623-.737 1.182-.389.907-.673 2.142-.766 3.556h3.936c-.093-1.414-.377-2.649-.766-3.556-.24-.56-.5-.948-.737-1.182C10.232 4.032 10.076 4 10 4zm3.971 5c-.089-1.546-.383-2.97-.837-4.118A6.004 6.004 0 0115.917 9h-1.946zm-2.003 2H8.032c.093 1.414.377 2.649.766 3.556.24.56.5.948.737 1.182.233.23.389.262.465.262.076 0 .232-.032.465-.262.238-.234.498-.623.737-1.182.389-.907.673-2.142.766-3.556zm1.166 4.118c.454-1.147.748-2.572.837-4.118h1.946a6.004 6.004 0 01-2.783 4.118zm-6.268 0C6.412 13.97 6.118 12.546 6.03 11H4.083a6.004 6.004 0 002.783 4.118z" clipRule="evenodd"/></svg>;
}
function RefreshIcon({ className, spinning }) {
  return <svg className={`${className} ${spinning ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>;
}
function MoonIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>;
}
function SunIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>;
}

const CHANNEL_ICON = { email: EmailIcon, whatsapp: WhatsAppIcon, web_form: WebIcon };
const CHANNEL_COLOR = {
  email:    { light: 'text-blue-600 bg-blue-100',   dark: 'text-blue-400 bg-blue-900/40' },
  whatsapp: { light: 'text-green-600 bg-green-100', dark: 'text-green-400 bg-green-900/40' },
  web_form: { light: 'text-purple-600 bg-purple-100', dark: 'text-purple-400 bg-purple-900/40' },
};

// ── Helpers ─────────────────────────────────────────────────────────────────

function relativeTime(iso) {
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (diff < 60)   return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400)return `${Math.floor(diff / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

function formatMs(ms) {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

function truncateId(id) {
  return id ? id.slice(0, 8) + '…' : '—';
}

// ── Mini sparkline (SVG) ────────────────────────────────────────────────────

function Sparkline({ values, color = '#3b82f6', dark }) {
  const w = 80, h = 28, pad = 2;
  const min = Math.min(...values), max = Math.max(...values);
  const range = max - min || 1;
  const pts = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (w - pad * 2);
    const y = h - pad - ((v - min) / range) * (h - pad * 2);
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity="0.8"
      />
    </svg>
  );
}

// ── Channel bar ─────────────────────────────────────────────────────────────

function ChannelBar({ label, icon: Icon, count, total, sentiment, escalation_rate, dark }) {
  const pct  = total > 0 ? Math.round((count / total) * 100) : 0;
  const mode = dark ? 'dark' : 'light';
  const colorCls = CHANNEL_COLOR[label.toLowerCase().replace(' ', '_')] || CHANNEL_COLOR.web_form;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`flex h-6 w-6 items-center justify-center rounded-md ${colorCls[mode]}`}>
            <Icon className="h-3.5 w-3.5" />
          </div>
          <span className={`text-sm font-medium ${dark ? 'text-gray-200' : 'text-gray-700'}`}>{label}</span>
        </div>
        <span className={`text-xs font-mono ${dark ? 'text-gray-400' : 'text-gray-500'}`}>
          {count.toLocaleString()} ({pct}%)
        </span>
      </div>

      {/* Progress bar */}
      <div className={`h-2 rounded-full ${dark ? 'bg-gray-700' : 'bg-gray-100'}`}>
        <div
          className="h-2 rounded-full transition-all duration-700"
          style={{
            width: `${pct}%`,
            background: label === 'Email' ? '#3b82f6' : label === 'WhatsApp' ? '#22c55e' : '#a855f7',
          }}
        />
      </div>

      {/* Micro stats */}
      <div className={`flex gap-4 text-xs ${dark ? 'text-gray-500' : 'text-gray-400'}`}>
        <span>Sentiment <strong className={dark ? 'text-gray-300' : 'text-gray-600'}>{sentiment?.toFixed(2)}</strong></span>
        <span>Escalation <strong className={dark ? 'text-gray-300' : 'text-gray-600'}>{escalation_rate?.toFixed(1)}%</strong></span>
      </div>
    </div>
  );
}

// ── Metric card ─────────────────────────────────────────────────────────────

function MetricCard({ title, value, sub, trend, trendLabel, sparkData, sparkColor, dark, icon }) {
  const up = trend >= 0;

  return (
    <div className={`rounded-2xl p-5 transition-all ${
      dark ? 'bg-gray-800 border border-gray-700' : 'bg-white border border-gray-100 shadow-sm'
    }`}>
      <div className="flex items-start justify-between">
        <div>
          <p className={`text-xs font-semibold uppercase tracking-wide ${dark ? 'text-gray-400' : 'text-gray-500'}`}>
            {title}
          </p>
          <p className={`mt-1.5 text-3xl font-bold tabular-nums ${dark ? 'text-white' : 'text-gray-900'}`}>
            {value}
          </p>
          {sub && (
            <p className={`mt-0.5 text-xs ${dark ? 'text-gray-500' : 'text-gray-400'}`}>{sub}</p>
          )}
        </div>
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${
          dark ? 'bg-gray-700' : 'bg-gray-50'
        }`}>
          {icon}
        </div>
      </div>

      <div className="mt-4 flex items-end justify-between">
        {trend !== undefined && (
          <div className={`flex items-center gap-1 text-xs font-semibold ${
            up ? 'text-green-500' : 'text-red-500'
          }`}>
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
                d={up ? 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' : 'M13 17h8m0 0V9m0 8l-8-8-4 4-6-6'} />
            </svg>
            {Math.abs(trend)}% {trendLabel || 'vs last week'}
          </div>
        )}
        {sparkData && <Sparkline values={sparkData} color={sparkColor} dark={dark} />}
      </div>
    </div>
  );
}

// ── Status badge (table) ────────────────────────────────────────────────────

function StatusBadge({ status, dark }) {
  const cfg  = STATUS_CFG[status] || STATUS_CFG.open;
  const mode = dark ? 'dark' : 'light';
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${cfg[mode]}`}>
      <span className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

// ── Main Dashboard ──────────────────────────────────────────────────────────

export default function AdminDashboard({
  apiBase = '',
  refreshInterval = 30000,
}) {
  const [dark,      setDark]      = useState(false);
  const [metrics,   setMetrics]   = useState(MOCK_METRICS);
  const [tickets,   setTickets]   = useState(MOCK_TICKETS);
  const [activity,  setActivity]  = useState(MOCK_ACTIVITY);
  const [online,    setOnline]    = useState(true);
  const [lastUpdate,setLastUpdate]= useState(new Date());
  const [refreshing,setRefreshing]= useState(false);
  const [escalating,setEscalating]= useState(null);    // ticket_id being escalated
  const intervalRef = useRef(null);

  // ── Fetch ────────────────────────────────────────────────────────────────

  const fetchAll = useCallback(async (showSpinner = false) => {
    if (showSpinner) setRefreshing(true);

    try {
      const [mRes, tRes, aRes] = await Promise.allSettled([
        fetch(`${apiBase}/api/metrics`),
        fetch(`${apiBase}/api/tickets?limit=6`),
        fetch(`${apiBase}/api/activity?limit=7`),
      ]);

      if (mRes.status === 'fulfilled' && mRes.value.ok)
        setMetrics(await mRes.value.json());

      if (tRes.status === 'fulfilled' && tRes.value.ok) {
        const data = await tRes.value.json();
        setTickets(data.tickets || data);
      }

      if (aRes.status === 'fulfilled' && aRes.value.ok)
        setActivity(await aRes.value.json());

      setOnline(true);
    } catch {
      setOnline(false);
    } finally {
      setLastUpdate(new Date());
      if (showSpinner) setRefreshing(false);
    }
  }, [apiBase]);

  useEffect(() => {
    fetchAll();
    intervalRef.current = setInterval(() => fetchAll(), refreshInterval);
    return () => clearInterval(intervalRef.current);
  }, [fetchAll, refreshInterval]);

  // ── Escalate ─────────────────────────────────────────────────────────────

  const handleEscalate = async (ticketId) => {
    setEscalating(ticketId);
    try {
      await fetch(`${apiBase}/support/ticket/${ticketId}/escalate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'Admin escalation from dashboard' }),
      });
      setTickets(prev =>
        prev.map(t => t.ticket_id === ticketId ? { ...t, status: 'escalated' } : t)
      );
    } finally {
      setEscalating(null);
    }
  };

  // ── Derived values ───────────────────────────────────────────────────────

  const ch      = metrics.channels;
  const total   = Object.values(ch).reduce((s, c) => s + c.count, 0);
  const rtMs    = metrics.avg_response_time_ms;
  const rtPct   = Math.min((rtMs / metrics.response_time_target) * 100, 100);
  const rtGood  = rtMs <= metrics.response_time_target;

  // ── Theme classes ─────────────────────────────────────────────────────────

  const bg    = dark ? 'bg-gray-900'  : 'bg-gray-50';
  const card  = dark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-100 shadow-sm';
  const text  = dark ? 'text-gray-100' : 'text-gray-900';
  const muted = dark ? 'text-gray-400' : 'text-gray-500';
  const divider = dark ? 'border-gray-700' : 'border-gray-100';
  const hover = dark ? 'hover:bg-gray-700' : 'hover:bg-gray-50';
  const inputBg = dark ? 'bg-gray-700 border-gray-600 text-gray-200' : 'bg-gray-50 border-gray-200 text-gray-700';

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <>
      <style>{`
        @keyframes fadeIn  { from { opacity:0; transform:translateY(6px) }  to { opacity:1; transform:translateY(0) } }
        @keyframes slideIn { from { opacity:0; transform:translateX(-8px) } to { opacity:1; transform:translateX(0) } }
        .fade-in  { animation: fadeIn  0.35s ease both }
        .slide-in { animation: slideIn 0.3s ease both }
      `}</style>

      <div className={`min-h-screen ${bg} transition-colors duration-300`}>
        <div className="mx-auto max-w-7xl px-4 py-6 space-y-6">

          {/* ── Header ─────────────────────────────────────────────── */}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className={`text-2xl font-bold ${text}`}>Admin Dashboard</h1>
              <div className="flex items-center gap-2 mt-1">
                {/* Online dot */}
                <span className={`flex h-2 w-2 rounded-full ${online ? 'bg-green-500' : 'bg-red-500'}`}>
                  {online && <span className="h-2 w-2 rounded-full bg-green-400 animate-ping absolute" />}
                </span>
                <span className={`text-xs ${muted}`}>
                  {online ? 'System Online' : 'System Offline'}
                </span>
                <span className={`text-xs ${muted}`}>·</span>
                <span className={`text-xs ${muted}`}>
                  Updated {relativeTime(lastUpdate.toISOString())}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Dark mode toggle */}
              <button
                onClick={() => setDark(d => !d)}
                className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                  dark
                    ? 'border-gray-600 bg-gray-700 text-gray-300 hover:bg-gray-600'
                    : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
                }`}
              >
                {dark ? <SunIcon className="h-4 w-4" /> : <MoonIcon className="h-4 w-4" />}
                {dark ? 'Light' : 'Dark'}
              </button>

              {/* Refresh */}
              <button
                onClick={() => fetchAll(true)}
                disabled={refreshing}
                className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                  dark
                    ? 'border-gray-600 bg-gray-700 text-gray-300 hover:bg-gray-600'
                    : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50 shadow-sm'
                }`}
              >
                <RefreshIcon className="h-4 w-4" spinning={refreshing} />
                Refresh
              </button>
            </div>
          </div>

          {/* ── Metric cards ───────────────────────────────────────── */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">

            <MetricCard
              dark={dark}
              title="Total Tickets"
              value={metrics.total_tickets.toLocaleString()}
              trend={metrics.total_tickets_trend}
              sparkData={[980, 1020, 1055, 1100, 1180, 1240, 1284]}
              sparkColor="#3b82f6"
              icon={<svg className={`h-5 w-5 ${dark ? 'text-blue-400' : 'text-blue-600'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>}
            />

            <MetricCard
              dark={dark}
              title="Avg Response Time"
              value={formatMs(rtMs)}
              sub={`Target: ${formatMs(metrics.response_time_target)}`}
              trend={rtGood ? -8.2 : 14.1}
              trendLabel="vs last week"
              sparkData={[2400, 2100, 1950, 2200, 1800, 1750, rtMs]}
              sparkColor={rtGood ? '#22c55e' : '#ef4444'}
              icon={<svg className={`h-5 w-5 ${rtGood ? (dark ? 'text-green-400' : 'text-green-600') : (dark ? 'text-red-400' : 'text-red-600')}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>}
            />

            <MetricCard
              dark={dark}
              title="Active Conversations"
              value={metrics.active_conversations}
              trend={3.4}
              sparkData={[28, 32, 41, 35, 38, 40, 37]}
              sparkColor="#8b5cf6"
              icon={<svg className={`h-5 w-5 ${dark ? 'text-purple-400' : 'text-purple-600'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>}
            />

            <MetricCard
              dark={dark}
              title="Escalations"
              value={metrics.escalations_count}
              sub={`Rate: ${metrics.escalation_rate}% (target <20%)`}
              trend={-5.1}
              sparkData={[32, 29, 31, 27, 25, 26, 24]}
              sparkColor="#f59e0b"
              icon={<svg className={`h-5 w-5 ${dark ? 'text-amber-400' : 'text-amber-600'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>}
            />
          </div>

          {/* ── Channel breakdown + Activity feed ─────────────────── */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">

            {/* Channel breakdown */}
            <div className={`rounded-2xl border p-6 space-y-5 lg:col-span-1 ${card}`}>
              <h2 className={`text-sm font-semibold ${text}`}>Channel Breakdown</h2>

              <ChannelBar
                label="Email"
                icon={EmailIcon}
                count={ch.email.count}
                total={total}
                sentiment={ch.email.avg_sentiment}
                escalation_rate={ch.email.escalation_rate}
                dark={dark}
              />
              <ChannelBar
                label="WhatsApp"
                icon={WhatsAppIcon}
                count={ch.whatsapp.count}
                total={total}
                sentiment={ch.whatsapp.avg_sentiment}
                escalation_rate={ch.whatsapp.escalation_rate}
                dark={dark}
              />
              <ChannelBar
                label="Web Form"
                icon={WebIcon}
                count={ch.web_form.count}
                total={total}
                sentiment={ch.web_form.avg_sentiment}
                escalation_rate={ch.web_form.escalation_rate}
                dark={dark}
              />

              {/* Response time mini comparison */}
              <div className={`rounded-xl p-3 space-y-2 ${dark ? 'bg-gray-700/50' : 'bg-gray-50'}`}>
                <p className={`text-xs font-semibold ${muted} uppercase tracking-wide`}>Avg Response Time</p>
                {[
                  { label: 'Email',    ms: ch.email.avg_response_ms,    color: '#3b82f6' },
                  { label: 'WhatsApp', ms: ch.whatsapp.avg_response_ms, color: '#22c55e' },
                  { label: 'Web Form', ms: ch.web_form.avg_response_ms, color: '#a855f7' },
                ].map(({ label, ms, color }) => (
                  <div key={label} className="flex items-center gap-2">
                    <span className={`w-16 text-xs ${muted}`}>{label}</span>
                    <div className={`flex-1 h-1.5 rounded-full ${dark ? 'bg-gray-600' : 'bg-gray-200'}`}>
                      <div className="h-1.5 rounded-full" style={{ width: `${Math.min(ms / 30, 100)}%`, background: color }} />
                    </div>
                    <span className={`text-xs font-mono w-12 text-right ${text}`}>{formatMs(ms)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Live activity feed */}
            <div className={`rounded-2xl border p-6 lg:col-span-2 ${card}`}>
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-2">
                  <h2 className={`text-sm font-semibold ${text}`}>Live Activity Feed</h2>
                  <span className="flex h-2 w-2 rounded-full bg-green-500">
                    <span className="h-2 w-2 rounded-full bg-green-400 animate-ping" />
                  </span>
                </div>
                <button className={`text-xs font-medium ${dark ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'}`}>
                  View All Activity →
                </button>
              </div>

              <div className="space-y-1">
                {activity.map((item, i) => {
                  const cfg  = ACTIVITY_CFG[item.type] || ACTIVITY_CFG.ticket_opened;
                  const ChIcon = CHANNEL_ICON[item.channel] || WebIcon;
                  return (
                    <div
                      key={item.id}
                      className={`flex items-start gap-3 rounded-xl px-3 py-2.5 transition-colors ${hover} slide-in`}
                      style={{ animationDelay: `${i * 40}ms` }}
                    >
                      {/* Activity dot */}
                      <div className="relative flex-shrink-0 mt-0.5">
                        <div className={`h-7 w-7 rounded-full ${cfg.color} flex items-center justify-center text-xs`}>
                          {cfg.icon}
                        </div>
                        {i < activity.length - 1 && (
                          <div className={`absolute left-1/2 top-7 w-px h-3 -translate-x-1/2 ${dark ? 'bg-gray-700' : 'bg-gray-200'}`} />
                        )}
                      </div>

                      <div className="flex-1 min-w-0">
                        <p className={`text-sm ${text} leading-snug`}>{item.message}</p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className={`text-xs ${muted}`}>{relativeTime(item.time)}</span>
                          <span className={`flex items-center gap-1 text-xs ${muted}`}>
                            <ChIcon className="h-3 w-3" />
                            {item.channel?.replace('_', ' ')}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* ── Recent tickets table ───────────────────────────────── */}
          <div className={`rounded-2xl border overflow-hidden ${card}`}>
            <div className={`flex items-center justify-between px-6 py-4 border-b ${divider}`}>
              <h2 className={`text-sm font-semibold ${text}`}>Recent Tickets</h2>
              <a
                href="/admin/tickets"
                className={`text-xs font-medium ${dark ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'}`}
              >
                View all →
              </a>
            </div>

            {/* Table — scrollable on small screens */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className={`border-b ${divider}`}>
                    {['Ticket ID', 'Customer', 'Channel', 'Subject', 'Status', 'Priority', 'Created', 'Actions'].map(h => (
                      <th
                        key={h}
                        className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide ${muted} whitespace-nowrap`}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-transparent">
                  {tickets.map((t, i) => {
                    const ChIcon = CHANNEL_ICON[t.channel] || WebIcon;
                    const chColor = CHANNEL_COLOR[t.channel] || CHANNEL_COLOR.web_form;
                    const priCfg  = PRIORITY_CFG[t.priority] || PRIORITY_CFG.medium;
                    const mode    = dark ? 'dark' : 'light';

                    return (
                      <tr
                        key={t.ticket_id}
                        className={`border-b ${divider} ${hover} transition-colors fade-in`}
                        style={{ animationDelay: `${i * 30}ms` }}
                      >
                        {/* Ticket ID */}
                        <td className="px-4 py-3">
                          <span className={`font-mono text-xs ${dark ? 'text-gray-300' : 'text-gray-600'}`}>
                            {truncateId(t.ticket_id)}
                          </span>
                        </td>

                        {/* Customer */}
                        <td className="px-4 py-3">
                          <span className={`text-xs ${text} truncate max-w-[120px] block`}>
                            {t.customer_email}
                          </span>
                        </td>

                        {/* Channel */}
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium ${chColor[mode]}`}>
                            <ChIcon className="h-3 w-3" />
                            {t.channel?.replace('_', ' ')}
                          </span>
                        </td>

                        {/* Subject */}
                        <td className="px-4 py-3">
                          <span className={`text-xs ${text} truncate max-w-[160px] block`} title={t.subject}>
                            {t.subject}
                          </span>
                        </td>

                        {/* Status */}
                        <td className="px-4 py-3">
                          <StatusBadge status={t.status} dark={dark} />
                        </td>

                        {/* Priority */}
                        <td className="px-4 py-3">
                          <span className={`text-xs font-semibold capitalize ${priCfg[mode]}`}>
                            {t.priority}
                          </span>
                        </td>

                        {/* Created */}
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className={`text-xs ${muted}`}>{relativeTime(t.created_at)}</span>
                        </td>

                        {/* Actions */}
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5">
                            <a
                              href={`/support/ticket/${t.ticket_id}`}
                              className={`rounded-lg px-2.5 py-1.5 text-xs font-medium border transition-colors ${
                                dark
                                  ? 'border-gray-600 text-gray-300 hover:bg-gray-700'
                                  : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                              }`}
                            >
                              View
                            </a>
                            {['open', 'in_progress'].includes(t.status) && (
                              <button
                                onClick={() => handleEscalate(t.ticket_id)}
                                disabled={escalating === t.ticket_id}
                                className={`rounded-lg px-2.5 py-1.5 text-xs font-medium border transition-colors disabled:opacity-50 ${
                                  dark
                                    ? 'border-red-700 text-red-400 hover:bg-red-900/30'
                                    : 'border-red-200 text-red-600 hover:bg-red-50'
                                }`}
                              >
                                {escalating === t.ticket_id ? '…' : 'Escalate'}
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Response time gauge bar */}
            <div className={`px-6 py-4 border-t ${divider}`}>
              <div className="flex items-center justify-between mb-1.5">
                <span className={`text-xs font-medium ${muted}`}>
                  Avg Response vs Target
                </span>
                <span className={`text-xs font-mono font-semibold ${rtGood ? 'text-green-500' : 'text-red-500'}`}>
                  {formatMs(rtMs)} / {formatMs(metrics.response_time_target)}
                </span>
              </div>
              <div className={`h-2 rounded-full ${dark ? 'bg-gray-700' : 'bg-gray-100'}`}>
                <div
                  className={`h-2 rounded-full transition-all duration-1000 ${rtGood ? 'bg-green-500' : 'bg-red-500'}`}
                  style={{ width: `${rtPct}%` }}
                />
              </div>
            </div>
          </div>

        </div>
      </div>
    </>
  );
}
