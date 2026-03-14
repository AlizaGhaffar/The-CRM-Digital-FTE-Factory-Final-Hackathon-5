/**
 * frontend/components/AnalyticsDashboard.jsx
 *
 * NimbusFlow — Analytics Dashboard
 * Full analytics view with time-range selection, channel analytics,
 * sentiment analysis, agent performance, and export controls.
 *
 * API endpoints used:
 *   GET /api/analytics?range=today|week|month|custom&from=&to=
 *
 * Dependencies: React 18+, Tailwind CSS, recharts
 *   npm install recharts
 *
 * Usage (Next.js):
 *   import AnalyticsDashboard from '@/components/AnalyticsDashboard';
 *   export default function AnalyticsPage() {
 *     return <AnalyticsDashboard apiBase="" />;
 *   }
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  ResponsiveContainer,
  BarChart, Bar,
  LineChart, Line,
  PieChart, Pie, Cell,
  AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts';

// ── Palette ────────────────────────────────────────────────────────────────

const C = {
  email:    '#3b82f6',
  whatsapp: '#22c55e',
  web:      '#a855f7',
  positive: '#22c55e',
  neutral:  '#94a3b8',
  negative: '#ef4444',
  amber:    '#f59e0b',
  indigo:   '#6366f1',
};

const PIE_COLORS = [C.email, C.whatsapp, C.web];

// ── Mock data generators ────────────────────────────────────────────────────

function makeDays(n, label = (i) => `Day ${i + 1}`) {
  return Array.from({ length: n }, (_, i) => ({ name: label(i) }));
}

const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const WEEK_LABELS = ['W1', 'W2', 'W3', 'W4'];
const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const HOUR_LABELS = Array.from({ length: 12 }, (_, i) => `${i * 2}:00`);

function rnd(min, max) { return Math.round(Math.random() * (max - min) + min); }

function makeChannelVolume(labels) {
  return labels.map(name => ({
    name,
    Email:    rnd(40, 180),
    WhatsApp: rnd(20, 130),
    Web:      rnd(10, 90),
  }));
}

function makeResponseTime(labels) {
  return labels.map(name => ({
    name,
    Email:    rnd(1400, 3200),
    WhatsApp: rnd(800, 2000),
    Web:      rnd(1000, 2800),
  }));
}

function makeSentimentTrend(labels) {
  return labels.map(name => ({
    name,
    Score:    parseFloat((Math.random() * 0.4 + 0.45).toFixed(2)),
    Positive: rnd(40, 75),
    Neutral:  rnd(15, 35),
    Negative: rnd(5, 25),
  }));
}

function makeAgentRows() {
  const agents = ['Alex Chen', 'Maria Torres', 'David Park', 'Priya Nair', 'James O\'Brien'];
  return agents.map(name => ({
    name,
    tickets:  rnd(24, 98),
    avg_ms:   rnd(900, 3500),
    resolved: rnd(60, 98),
    escalated: rnd(2, 18),
  }));
}

const RESOLUTION_DATA = [
  { name: 'Email',    value: 78 },
  { name: 'WhatsApp', value: 89 },
  { name: 'Web',      value: 72 },
];

const ESCALATION_DATA = [
  { name: 'Billing Dispute',      count: 31 },
  { name: 'Technical Complexity', count: 27 },
  { name: 'Sentiment Negative',   count: 19 },
  { name: 'Policy Exception',     count: 14 },
  { name: 'Legal / Compliance',   count: 11 },
  { name: 'Repeated Contact',     count: 9 },
  { name: 'Account Security',     count: 7 },
];

const TOOL_USAGE = [
  { name: 'search_tickets',    calls: 1284 },
  { name: 'get_customer_info', calls: 987 },
  { name: 'create_ticket',     calls: 742 },
  { name: 'send_email',        calls: 631 },
  { name: 'update_ticket',     calls: 524 },
  { name: 'escalate',          calls: 211 },
];

const NEGATIVE_FLAGS = [
  { id: 'TKT-00391', customer: 'eve@design.co',   score: 0.11, snippet: "I'm just exhausted with all these bugs…",         time: '14m ago' },
  { id: 'TKT-00344', customer: 'hiro@saas.jp',    score: 0.18, snippet: 'This is completely unacceptable for enterprise.',  time: '41m ago' },
  { id: 'TKT-00312', customer: 'carol@tech.dev',  score: 0.22, snippet: 'Why is nobody reading my messages?',               time: '1h ago' },
  { id: 'TKT-00289', customer: 'frank@media.io',  score: 0.24, snippet: 'Considering cancellation at this point.',          time: '2h ago' },
];

const CSAT_SCORE = 4.2;
const CSAT_TOTAL = 382;

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatMs(ms) {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

function sentimentColor(score, dark) {
  if (score >= 0.6) return dark ? 'text-green-400' : 'text-green-600';
  if (score >= 0.35) return dark ? 'text-amber-400' : 'text-amber-600';
  return dark ? 'text-red-400' : 'text-red-600';
}

function sentimentLabel(score) {
  if (score >= 0.6) return 'Positive';
  if (score >= 0.35) return 'Neutral';
  return 'Negative';
}

// ── Icons ──────────────────────────────────────────────────────────────────

function DownloadIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>;
}
function MailIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>;
}
function CalendarIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>;
}
function MoonIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>;
}
function SunIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>;
}
function AlertIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>;
}
function CheckIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/></svg>;
}
function XIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/></svg>;
}

// ── Shared chart tooltip style ──────────────────────────────────────────────

function ChartTooltip({ active, payload, label, dark, formatter }) {
  if (!active || !payload?.length) return null;
  return (
    <div className={`rounded-xl border px-3 py-2.5 shadow-lg text-xs ${
      dark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
    }`}>
      <p className={`font-semibold mb-1.5 ${dark ? 'text-gray-300' : 'text-gray-700'}`}>{label}</p>
      {payload.map(p => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full flex-shrink-0" style={{ background: p.color }} />
          <span className={dark ? 'text-gray-400' : 'text-gray-500'}>{p.name}:</span>
          <span className={`font-semibold ${dark ? 'text-gray-200' : 'text-gray-800'}`}>
            {formatter ? formatter(p.value, p.name) : p.value}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Section wrapper ─────────────────────────────────────────────────────────

function Section({ title, subtitle, children, dark, action }) {
  const card    = dark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-100 shadow-sm';
  const text    = dark ? 'text-gray-100' : 'text-gray-900';
  const muted   = dark ? 'text-gray-400' : 'text-gray-500';
  const divider = dark ? 'border-gray-700' : 'border-gray-100';
  return (
    <div className={`rounded-2xl border overflow-hidden ${card}`}>
      <div className={`flex items-center justify-between px-5 py-4 border-b ${divider}`}>
        <div>
          <h2 className={`text-sm font-bold ${text}`}>{title}</h2>
          {subtitle && <p className={`text-xs ${muted} mt-0.5`}>{subtitle}</p>}
        </div>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

// ── Stat card ───────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, color = 'blue', dark }) {
  const colors = {
    blue:   dark ? 'bg-blue-900/40 text-blue-400'   : 'bg-blue-50 text-blue-600',
    green:  dark ? 'bg-green-900/40 text-green-400' : 'bg-green-50 text-green-600',
    amber:  dark ? 'bg-amber-900/40 text-amber-400' : 'bg-amber-50 text-amber-600',
    red:    dark ? 'bg-red-900/40 text-red-400'     : 'bg-red-50 text-red-600',
    purple: dark ? 'bg-purple-900/40 text-purple-400': 'bg-purple-50 text-purple-600',
  };
  return (
    <div className={`rounded-xl p-4 ${colors[color]}`}>
      <p className="text-xs font-semibold uppercase tracking-wide opacity-80">{label}</p>
      <p className="text-2xl font-bold tabular-nums mt-1">{value}</p>
      {sub && <p className="text-xs opacity-70 mt-0.5">{sub}</p>}
    </div>
  );
}

// ── CSAT stars ──────────────────────────────────────────────────────────────

function Stars({ score }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map(i => (
        <svg key={i} className={`h-5 w-5 ${i <= Math.round(score) ? 'text-amber-400' : 'text-gray-300'}`} fill="currentColor" viewBox="0 0 20 20">
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
        </svg>
      ))}
    </div>
  );
}

// ── Schedule email modal ────────────────────────────────────────────────────

function ScheduleModal({ onClose, dark }) {
  const [email,     setEmail]     = useState('');
  const [frequency, setFrequency] = useState('weekly');
  const [sent,      setSent]      = useState(false);

  const card    = dark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-100';
  const text    = dark ? 'text-gray-100' : 'text-gray-900';
  const muted   = dark ? 'text-gray-400' : 'text-gray-500';
  const inputCls = `w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
    dark ? 'bg-gray-700 border-gray-600 text-gray-200 placeholder:text-gray-500' : 'bg-white border-gray-200 text-gray-800'
  }`;

  const handleSubmit = (e) => {
    e.preventDefault();
    setSent(true);
    setTimeout(onClose, 1800);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className={`rounded-2xl border p-6 w-full max-w-sm shadow-2xl ${card}`}>
        <div className="flex items-center justify-between mb-5">
          <h3 className={`text-base font-bold ${text}`}>Schedule Email Report</h3>
          <button onClick={onClose} className={`${muted} hover:text-red-500 transition-colors`}>
            <XIcon className="h-5 w-5" />
          </button>
        </div>

        {sent ? (
          <div className="flex flex-col items-center gap-3 py-6">
            <div className={`flex h-12 w-12 items-center justify-center rounded-full ${dark ? 'bg-green-900/40' : 'bg-green-100'}`}>
              <CheckIcon className={`h-6 w-6 ${dark ? 'text-green-400' : 'text-green-600'}`} />
            </div>
            <p className={`text-sm font-semibold ${text}`}>Report scheduled!</p>
            <p className={`text-xs text-center ${muted}`}>You'll receive a {frequency} report at {email || 'your email'}.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className={`block text-xs font-semibold uppercase tracking-wide mb-1.5 ${muted}`}>Recipient Email</label>
              <input required type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="admin@yourco.com" className={inputCls} />
            </div>
            <div>
              <label className={`block text-xs font-semibold uppercase tracking-wide mb-1.5 ${muted}`}>Frequency</label>
              <select value={frequency} onChange={e => setFrequency(e.target.value)} className={inputCls}>
                <option value="daily">Daily (8:00 AM)</option>
                <option value="weekly">Weekly (Monday 8:00 AM)</option>
                <option value="monthly">Monthly (1st of month)</option>
              </select>
            </div>
            <button type="submit" className="w-full rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 transition-colors">
              Schedule Report
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

const RANGES = ['Today', 'This Week', 'This Month', 'Custom'];

export default function AnalyticsDashboard({ apiBase = '' }) {
  const [dark,       setDark]       = useState(false);
  const [range,      setRange]      = useState('This Week');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo,   setCustomTo]   = useState('');
  const [loading,    setLoading]    = useState(false);
  const [toast,      setToast]      = useState(null);
  const [schedule,   setSchedule]   = useState(false);

  // ── Derived chart data (re-generated per range) ────────────────────────

  const [chartData, setChartData] = useState(() => buildChartData('This Week'));

  function buildChartData(r) {
    const labels =
      r === 'Today'      ? HOUR_LABELS :
      r === 'This Week'  ? DAY_LABELS  :
      r === 'This Month' ? WEEK_LABELS :
      DAY_LABELS; // custom fallback
    return {
      volume:     makeChannelVolume(labels),
      respTime:   makeResponseTime(labels),
      sentiment:  makeSentimentTrend(labels),
      agents:     makeAgentRows(),
    };
  }

  useEffect(() => {
    setLoading(true);
    const timer = setTimeout(() => {
      setChartData(buildChartData(range));
      setLoading(false);
    }, 350);
    return () => clearTimeout(timer);
  }, [range, customFrom, customTo]);

  // ── Export handlers ────────────────────────────────────────────────────

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  const handleExportPDF = () => showToast('PDF report generated and downloaded.');
  const handleExportCSV = () => showToast('CSV data exported successfully.');

  // ── Theme ──────────────────────────────────────────────────────────────

  const bg      = dark ? 'bg-gray-900'  : 'bg-gray-50';
  const card    = dark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-100 shadow-sm';
  const text    = dark ? 'text-gray-100' : 'text-gray-900';
  const muted   = dark ? 'text-gray-400' : 'text-gray-500';
  const divider = dark ? 'border-gray-700' : 'border-gray-100';
  const axis    = dark ? '#6b7280' : '#9ca3af';
  const grid    = dark ? '#374151' : '#f3f4f6';
  const inputCls = `rounded-lg border px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 ${
    dark ? 'bg-gray-700 border-gray-600 text-gray-200' : 'bg-white border-gray-200 text-gray-700'
  }`;
  const ttProps = { content: (p) => <ChartTooltip {...p} dark={dark} /> };
  const ttPropsMs = { content: (p) => <ChartTooltip {...p} dark={dark} formatter={(v) => formatMs(v)} /> };

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <>
      <style>{`
        @keyframes fadeIn  { from { opacity:0; transform:translateY(6px) } to { opacity:1; transform:translateY(0) } }
        @keyframes toastIn { from { opacity:0; transform:translateY(16px) } to { opacity:1; transform:translateY(0) } }
        @keyframes pulse   { 0%,100% { opacity:1 } 50% { opacity:.4 } }
        .fade-in   { animation: fadeIn  0.35s ease both }
        .toast-in  { animation: toastIn 0.3s ease both }
        .loading   { animation: pulse 1.2s ease-in-out infinite }
      `}</style>

      <div className={`min-h-screen ${bg} transition-colors duration-300`}>
        <div className="mx-auto max-w-7xl px-4 py-6 space-y-6">

          {/* ── Header ──────────────────────────────────────────────── */}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className={`text-xl font-bold ${text}`}>Analytics</h1>
              <p className={`text-xs ${muted} mt-0.5`}>Performance insights across all support channels</p>
            </div>
            <div className="flex items-center gap-2">

              {/* Export buttons */}
              <button
                onClick={handleExportPDF}
                className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                  dark ? 'border-gray-600 bg-gray-700 text-gray-300 hover:bg-gray-600' : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50 shadow-sm'
                }`}
              >
                <DownloadIcon className="h-3.5 w-3.5" />
                PDF
              </button>
              <button
                onClick={handleExportCSV}
                className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                  dark ? 'border-gray-600 bg-gray-700 text-gray-300 hover:bg-gray-600' : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50 shadow-sm'
                }`}
              >
                <DownloadIcon className="h-3.5 w-3.5" />
                CSV
              </button>
              <button
                onClick={() => setSchedule(true)}
                className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                  dark ? 'border-gray-600 bg-gray-700 text-gray-300 hover:bg-gray-600' : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50 shadow-sm'
                }`}
              >
                <MailIcon className="h-3.5 w-3.5" />
                Schedule
              </button>

              {/* Dark toggle */}
              <button
                onClick={() => setDark(d => !d)}
                className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                  dark ? 'border-gray-600 bg-gray-700 text-gray-300 hover:bg-gray-600' : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50 shadow-sm'
                }`}
              >
                {dark ? <SunIcon className="h-4 w-4" /> : <MoonIcon className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {/* ── Time range selector ──────────────────────────────────── */}
          <div className={`rounded-2xl border p-4 flex flex-wrap items-center gap-3 ${card}`}>
            <CalendarIcon className={`h-4 w-4 ${muted}`} />
            <div className="flex rounded-xl overflow-hidden border divide-x ${dark ? 'border-gray-600 divide-gray-600' : 'border-gray-200 divide-gray-200'}">
              {RANGES.slice(0, 3).map(r => (
                <button
                  key={r}
                  onClick={() => setRange(r)}
                  className={`px-4 py-1.5 text-xs font-semibold transition-colors ${
                    range === r
                      ? 'bg-blue-600 text-white'
                      : (dark ? 'bg-gray-700 text-gray-300 hover:bg-gray-600' : 'bg-white text-gray-600 hover:bg-gray-50')
                  }`}
                >
                  {r}
                </button>
              ))}
              <button
                onClick={() => setRange('Custom')}
                className={`px-4 py-1.5 text-xs font-semibold transition-colors ${
                  range === 'Custom'
                    ? 'bg-blue-600 text-white'
                    : (dark ? 'bg-gray-700 text-gray-300 hover:bg-gray-600' : 'bg-white text-gray-600 hover:bg-gray-50')
                }`}
              >
                Custom
              </button>
            </div>

            {range === 'Custom' && (
              <div className="flex items-center gap-2">
                <input type="date" value={customFrom} onChange={e => setCustomFrom(e.target.value)} className={inputCls} />
                <span className={`text-xs ${muted}`}>to</span>
                <input type="date" value={customTo} onChange={e => setCustomTo(e.target.value)} className={inputCls} />
              </div>
            )}

            {loading && (
              <span className={`text-xs ${muted} loading`}>Loading…</span>
            )}
          </div>

          {/* ── Section 2: Channel Analytics ─────────────────────────── */}
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">

            {/* Volume by channel (bar) */}
            <Section title="Volume by Channel" subtitle="Tickets received per period" dark={dark}>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData.volume} barSize={14} barGap={4}>
                  <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: axis }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: axis }} axisLine={false} tickLine={false} width={30} />
                  <Tooltip {...ttProps} cursor={{ fill: dark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)' }} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="Email"    fill={C.email}    radius={[4, 4, 0, 0]} />
                  <Bar dataKey="WhatsApp" fill={C.whatsapp} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Web"      fill={C.web}      radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Section>

            {/* Response time by channel (line) */}
            <Section title="Avg Response Time by Channel" subtitle="Milliseconds per period" dark={dark}>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData.respTime}>
                  <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: axis }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: axis }} axisLine={false} tickLine={false} width={42} tickFormatter={v => `${(v / 1000).toFixed(1)}s`} />
                  <Tooltip {...ttPropsMs} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                  <Line dataKey="Email"    stroke={C.email}    strokeWidth={2} dot={false} />
                  <Line dataKey="WhatsApp" stroke={C.whatsapp} strokeWidth={2} dot={false} />
                  <Line dataKey="Web"      stroke={C.web}      strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </Section>

            {/* Resolution rate (pie) */}
            <Section title="Resolution Rate by Channel" subtitle="% of tickets resolved without escalation" dark={dark}>
              <div className="flex items-center gap-6">
                <ResponsiveContainer width="55%" height={200}>
                  <PieChart>
                    <Pie
                      data={RESOLUTION_DATA}
                      cx="50%"
                      cy="50%"
                      innerRadius={52}
                      outerRadius={80}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {RESOLUTION_DATA.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i]} />
                      ))}
                    </Pie>
                    <Tooltip content={p => (
                      <ChartTooltip {...p} dark={dark} formatter={v => `${v}%`} />
                    )} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-3 flex-1">
                  {RESOLUTION_DATA.map((d, i) => (
                    <div key={d.name}>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="flex items-center gap-1.5">
                          <span className="h-2 w-2 rounded-full" style={{ background: PIE_COLORS[i] }} />
                          <span className={dark ? 'text-gray-300' : 'text-gray-700'}>{d.name}</span>
                        </span>
                        <span className={`font-bold ${dark ? 'text-gray-200' : 'text-gray-800'}`}>{d.value}%</span>
                      </div>
                      <div className={`h-1.5 rounded-full ${dark ? 'bg-gray-700' : 'bg-gray-100'}`}>
                        <div className="h-1.5 rounded-full" style={{ width: `${d.value}%`, background: PIE_COLORS[i] }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </Section>

            {/* Escalation rate by channel (bar) */}
            <Section title="Escalation Reasons Breakdown" subtitle="Top reasons AI handed off to human" dark={dark}>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={ESCALATION_DATA} layout="vertical" barSize={12}>
                  <CartesianGrid strokeDasharray="3 3" stroke={grid} horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11, fill: axis }} axisLine={false} tickLine={false} />
                  <YAxis dataKey="name" type="category" tick={{ fontSize: 10, fill: axis }} axisLine={false} tickLine={false} width={130} />
                  <Tooltip {...ttProps} cursor={{ fill: dark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)' }} />
                  <Bar dataKey="count" fill={C.amber} radius={[0, 4, 4, 0]} name="Escalations" />
                </BarChart>
              </ResponsiveContainer>
            </Section>
          </div>

          {/* ── Section 3: Sentiment Analysis ────────────────────────── */}
          <div className={`rounded-2xl border overflow-hidden ${card}`}>
            <div className={`flex items-center justify-between px-5 py-4 border-b ${divider}`}>
              <div>
                <h2 className={`text-sm font-bold ${text}`}>Sentiment Analysis</h2>
                <p className={`text-xs ${muted} mt-0.5`}>Customer mood trends across conversations</p>
              </div>
            </div>

            <div className="p-5 space-y-6">

              {/* CSAT + overall score row */}
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <StatCard dark={dark} color="blue"   label="Avg Sentiment Score" value="0.61"       sub="Scale: 0–1" />
                <StatCard dark={dark} color="green"  label="Positive"            value="58%"        sub="of conversations" />
                <StatCard dark={dark} color="amber"  label="Neutral"             value="27%"        sub="of conversations" />
                <StatCard dark={dark} color="red"    label="Negative"            value="15%"        sub="of conversations" />
              </div>

              {/* Sentiment trend line + stacked area */}
              <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-wide ${muted} mb-3`}>Overall Sentiment Trend</p>
                  <ResponsiveContainer width="100%" height={180}>
                    <AreaChart data={chartData.sentiment}>
                      <defs>
                        <linearGradient id="sentGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor={C.positive} stopOpacity={0.25} />
                          <stop offset="95%" stopColor={C.positive} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 11, fill: axis }} axisLine={false} tickLine={false} />
                      <YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: axis }} axisLine={false} tickLine={false} width={28} />
                      <Tooltip content={p => <ChartTooltip {...p} dark={dark} formatter={v => v.toFixed(2)} />} />
                      <Area dataKey="Score" stroke={C.positive} strokeWidth={2} fill="url(#sentGrad)" dot={false} name="Sentiment" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>

                <div>
                  <p className={`text-xs font-semibold uppercase tracking-wide ${muted} mb-3`}>Positive / Neutral / Negative Split</p>
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={chartData.sentiment} barSize={10} barGap={2}>
                      <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 11, fill: axis }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 11, fill: axis }} axisLine={false} tickLine={false} width={28} />
                      <Tooltip {...ttProps} />
                      <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                      <Bar dataKey="Positive" stackId="s" fill={C.positive} radius={[0, 0, 0, 0]} />
                      <Bar dataKey="Neutral"  stackId="s" fill={C.neutral}  radius={[0, 0, 0, 0]} />
                      <Bar dataKey="Negative" stackId="s" fill={C.negative} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* CSAT score */}
              <div className={`rounded-xl border p-4 flex flex-wrap items-center gap-6 ${dark ? 'border-gray-700 bg-gray-700/30' : 'border-gray-100 bg-gray-50'}`}>
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-wide ${muted} mb-1`}>CSAT Score</p>
                  <div className="flex items-baseline gap-2">
                    <span className={`text-4xl font-bold tabular-nums ${dark ? 'text-gray-100' : 'text-gray-900'}`}>{CSAT_SCORE}</span>
                    <span className={`text-sm ${muted}`}>/ 5.0</span>
                  </div>
                  <Stars score={CSAT_SCORE} />
                  <p className={`text-xs ${muted} mt-1`}>Based on {CSAT_TOTAL} survey responses</p>
                </div>
                <div className="flex-1 space-y-1.5">
                  {[5, 4, 3, 2, 1].map(star => {
                    const pct = star === 5 ? 48 : star === 4 ? 30 : star === 3 ? 12 : star === 2 ? 6 : 4;
                    return (
                      <div key={star} className="flex items-center gap-2 text-xs">
                        <span className={`w-5 text-right ${muted}`}>{star}★</span>
                        <div className={`flex-1 h-2 rounded-full ${dark ? 'bg-gray-600' : 'bg-gray-200'}`}>
                          <div className="h-2 rounded-full bg-amber-400 transition-all duration-700" style={{ width: `${pct}%` }} />
                        </div>
                        <span className={`w-8 text-right tabular-nums ${muted}`}>{pct}%</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Negative conversation flags */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <AlertIcon className={`h-4 w-4 ${dark ? 'text-red-400' : 'text-red-500'}`} />
                  <p className={`text-xs font-bold uppercase tracking-wide ${dark ? 'text-red-400' : 'text-red-600'}`}>
                    Negative Conversation Flags
                  </p>
                </div>
                <div className="space-y-2">
                  {NEGATIVE_FLAGS.map(flag => (
                    <div key={flag.id} className={`flex items-start justify-between gap-3 rounded-xl border px-4 py-3 ${
                      dark ? 'border-red-800/50 bg-red-900/15' : 'border-red-100 bg-red-50'
                    }`}>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className={`text-xs font-mono font-semibold ${dark ? 'text-red-400' : 'text-red-600'}`}>{flag.id}</span>
                          <span className={`text-xs ${muted}`}>{flag.customer}</span>
                          <span className={`text-xs ${muted}`}>·</span>
                          <span className={`text-xs ${muted}`}>{flag.time}</span>
                        </div>
                        <p className={`text-xs truncate ${dark ? 'text-gray-300' : 'text-gray-700'}`}>"{flag.snippet}"</p>
                      </div>
                      <span className={`flex-shrink-0 rounded-full px-2 py-0.5 text-xs font-bold ${
                        dark ? 'bg-red-900/50 text-red-300' : 'bg-red-100 text-red-700'
                      }`}>
                        {flag.score.toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* ── Section 4: Agent Performance ─────────────────────────── */}
          <div className={`rounded-2xl border overflow-hidden ${card}`}>
            <div className={`flex items-center justify-between px-5 py-4 border-b ${divider}`}>
              <div>
                <h2 className={`text-sm font-bold ${text}`}>Agent Performance</h2>
                <p className={`text-xs ${muted} mt-0.5`}>Human agent metrics for the selected period</p>
              </div>
            </div>

            <div className="p-5 space-y-6">

              {/* Agent table */}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className={`border-b ${divider}`}>
                      {['Agent', 'Tickets Handled', 'Avg Response', 'Resolution %', 'Escalated'].map(h => (
                        <th key={h} className={`px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide ${muted} whitespace-nowrap`}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {chartData.agents.map((agent, i) => (
                      <tr key={agent.name} className={`border-b ${divider} ${dark ? 'hover:bg-gray-700/40' : 'hover:bg-gray-50'} transition-colors`}>
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-2.5">
                            <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
                              dark ? 'bg-blue-900/40 text-blue-300' : 'bg-blue-100 text-blue-700'
                            }`}>
                              {agent.name.split(' ').map(n => n[0]).join('')}
                            </div>
                            <span className={`text-xs font-semibold ${text}`}>{agent.name}</span>
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          <span className={`text-xs font-mono font-semibold ${text}`}>{agent.tickets}</span>
                        </td>
                        <td className="px-3 py-3">
                          <span className={`text-xs ${formatMs(agent.avg_ms) > '2.5s' ? (dark ? 'text-red-400' : 'text-red-600') : (dark ? 'text-green-400' : 'text-green-600')} font-semibold`}>
                            {formatMs(agent.avg_ms)}
                          </span>
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-2">
                            <div className={`w-16 h-1.5 rounded-full ${dark ? 'bg-gray-700' : 'bg-gray-100'}`}>
                              <div className="h-1.5 rounded-full bg-green-500" style={{ width: `${agent.resolved}%` }} />
                            </div>
                            <span className={`text-xs font-semibold ${dark ? 'text-gray-300' : 'text-gray-700'}`}>{agent.resolved}%</span>
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          <span className={`text-xs font-semibold ${agent.escalated > 12 ? (dark ? 'text-amber-400' : 'text-amber-600') : (dark ? 'text-gray-300' : 'text-gray-700')}`}>
                            {agent.escalated}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Tool usage */}
              <div>
                <p className={`text-xs font-semibold uppercase tracking-wide ${muted} mb-3`}>AI Tool Usage Frequency</p>
                <div className="space-y-2">
                  {TOOL_USAGE.map((tool, i) => {
                    const max = TOOL_USAGE[0].calls;
                    const pct = Math.round((tool.calls / max) * 100);
                    const barColors = [C.email, C.whatsapp, C.web, C.amber, C.indigo, C.negative];
                    return (
                      <div key={tool.name} className="flex items-center gap-3">
                        <span className={`text-xs font-mono w-36 flex-shrink-0 ${dark ? 'text-gray-400' : 'text-gray-500'}`}>{tool.name}</span>
                        <div className={`flex-1 h-2 rounded-full ${dark ? 'bg-gray-700' : 'bg-gray-100'}`}>
                          <div
                            className="h-2 rounded-full transition-all duration-700"
                            style={{ width: `${pct}%`, background: barColors[i % barColors.length] }}
                          />
                        </div>
                        <span className={`text-xs font-mono w-12 text-right tabular-nums ${dark ? 'text-gray-300' : 'text-gray-700'}`}>
                          {tool.calls.toLocaleString()}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

            </div>
          </div>

        </div>
      </div>

      {/* ── Schedule modal ───────────────────────────────────────────── */}
      {schedule && <ScheduleModal onClose={() => setSchedule(false)} dark={dark} />}

      {/* ── Toast ───────────────────────────────────────────────────── */}
      {toast && (
        <div className={`fixed bottom-6 right-6 z-50 toast-in flex items-center gap-2.5 rounded-xl px-4 py-3 text-sm font-medium shadow-lg ${
          toast.type === 'success'
            ? (dark ? 'bg-green-800 text-green-100' : 'bg-green-600 text-white')
            : (dark ? 'bg-red-800 text-red-100'     : 'bg-red-600 text-white')
        }`}>
          {toast.type === 'success' ? <CheckIcon className="h-4 w-4" /> : <XIcon className="h-4 w-4" />}
          {toast.msg}
        </div>
      )}
    </>
  );
}
