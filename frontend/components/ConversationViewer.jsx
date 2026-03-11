/**
 * frontend/components/ConversationViewer.jsx
 *
 * NimbusFlow — Admin Conversation Viewer
 * Split-view: ticket details (left) + full conversation thread (right).
 * Supports AI / customer / human / internal-note message types,
 * channel-aware reply, and all ticket lifecycle actions.
 *
 * API endpoints used:
 *   GET  /api/tickets/{id}            — ticket + customer details
 *   GET  /api/tickets/{id}/messages   — full conversation thread
 *   POST /api/tickets/{id}/reply      — send reply on chosen channel
 *   POST /api/tickets/{id}/resolve    — resolve ticket
 *   POST /api/tickets/{id}/escalate   — escalate to human
 *   POST /api/tickets/{id}/assign     — assign to specific agent
 *   POST /api/tickets/{id}/note       — add internal admin note
 *
 * Usage (Next.js):
 *   import ConversationViewer from '@/components/ConversationViewer';
 *   export default function TicketPage({ params }) {
 *     return <ConversationViewer ticketId={params.id} apiBase="" />;
 *   }
 *
 * Requirements: React 18+, Tailwind CSS
 */

import { useState, useEffect, useRef, useCallback } from 'react';

// ── Mock data ──────────────────────────────────────────────────────────────

const MOCK_TICKET = {
  ticket_id:        'c3d4e5f6-7081-9012-def0-123456789012',
  status:           'escalated',
  priority:         'high',
  category:         'technical',
  source_channel:   'email',
  created_at:       new Date(Date.now() - 45 * 60000).toISOString(),
  updated_at:       new Date(Date.now() - 8 * 60000).toISOString(),
  resolved_at:      null,
  escalation_reason:'Customer requested human — SSO issue affects 50 users',
  assigned_to:      'human',
  resolution_notes: null,
  customer: {
    id:      'cust-abc123',
    name:    'Dave Anderson',
    email:   'dave@bigco.com',
    phone:   '+1 (415) 555-0192',
    company: 'BigCo Inc.',
    plan:    'Enterprise',
    channels_used: ['email', 'whatsapp'],
    total_tickets: 7,
    since:   '2024-03-15',
  },
};

const MOCK_MESSAGES = [
  {
    id: 'm1', role: 'customer', sender_name: 'Dave Anderson',
    channel: 'email', content: 'Hi, our entire SSO integration is broken. 50 users cannot log in since 09:00 this morning. This is blocking our entire team.',
    created_at: new Date(Date.now() - 45 * 60000).toISOString(), delivery_status: 'delivered',
  },
  {
    id: 'm2', role: 'ai', sender_name: 'NimbusFlow AI',
    channel: 'email', content: 'Dear Dave,\n\nThank you for reaching out. I\'ve created a high-priority ticket for your SSO issue. I\'m checking our knowledge base now.\n\nTicket ID: c3d4e5f6\n\nBest regards,\nNimbusFlow Support',
    created_at: new Date(Date.now() - 44 * 60000).toISOString(), delivery_status: 'delivered', latency_ms: 1240,
  },
  {
    id: 'm3', role: 'ai', sender_name: 'NimbusFlow AI',
    channel: 'email', content: 'I found relevant documentation for SAML SSO issues. Common causes include: expired certificates, incorrect ACS URL, or metadata mismatch. Could you confirm which identity provider you\'re using (Okta, Azure AD, Google Workspace)?',
    created_at: new Date(Date.now() - 43 * 60000).toISOString(), delivery_status: 'delivered', latency_ms: 1850,
  },
  {
    id: 'm4', role: 'customer', sender_name: 'Dave Anderson',
    channel: 'whatsapp', content: 'We use Okta. This was working yesterday. Nothing changed on our end. We need this fixed NOW.',
    created_at: new Date(Date.now() - 30 * 60000).toISOString(), delivery_status: 'delivered',
  },
  {
    id: 'm5', role: 'internal_note', sender_name: 'AI System',
    channel: 'system', content: 'Sentiment score: 0.18 (angry). Escalation triggered: legal threat threshold not met but urgency HIGH. Routing to human support.',
    created_at: new Date(Date.now() - 29 * 60000).toISOString(), delivery_status: 'internal',
  },
  {
    id: 'm6', role: 'ai', sender_name: 'NimbusFlow AI',
    channel: 'whatsapp', content: 'I completely understand this is urgent — 50 users being locked out is a critical situation. I\'m escalating this to our senior support team right now. They\'ll contact you within 15 minutes.',
    created_at: new Date(Date.now() - 28 * 60000).toISOString(), delivery_status: 'delivered', latency_ms: 920,
  },
  {
    id: 'm7', role: 'human', sender_name: 'Sarah K. (Support)',
    channel: 'email', content: 'Hi Dave,\n\nI\'m Sarah from the senior support team. I\'ve reviewed your case. This looks like an Okta metadata refresh issue that affects SAML tokens. I\'m sending you a direct Zoom link — can you join in 5 minutes?\n\nhttps://zoom.us/j/example\n\nWe\'ll get this resolved quickly.',
    created_at: new Date(Date.now() - 8 * 60000).toISOString(), delivery_status: 'delivered',
  },
];

// ── Config ─────────────────────────────────────────────────────────────────

const STATUS_CFG = {
  open:        { label: 'Open',        light: 'bg-blue-100 text-blue-700 ring-blue-200',    dot: 'bg-blue-500' },
  in_progress: { label: 'In Progress', light: 'bg-amber-100 text-amber-700 ring-amber-200', dot: 'bg-amber-400 animate-pulse' },
  resolved:    { label: 'Resolved',    light: 'bg-green-100 text-green-700 ring-green-200', dot: 'bg-green-500' },
  escalated:   { label: 'Escalated',   light: 'bg-red-100 text-red-700 ring-red-200',       dot: 'bg-red-500 animate-pulse' },
};

const PRIORITY_CFG = {
  high:   'text-red-600 bg-red-50 ring-red-200',
  medium: 'text-amber-600 bg-amber-50 ring-amber-200',
  low:    'text-green-600 bg-green-50 ring-green-200',
};

const CHANNELS = [
  { value: 'email',    label: 'Email' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'web_form', label: 'Web' },
];

// ── SVG Icons ──────────────────────────────────────────────────────────────

const Icon = {
  Email: (p) => <svg {...p} viewBox="0 0 20 20" fill="currentColor"><path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z"/><path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z"/></svg>,
  WhatsApp: (p) => <svg {...p} viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.127.558 4.126 1.532 5.862L.072 23.928l6.243-1.636A11.935 11.935 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.818 9.818 0 01-5.009-1.374l-.36-.213-3.708.972.989-3.617-.233-.371A9.818 9.818 0 1112 21.818z"/></svg>,
  Web: (p) => <svg {...p} viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M4.083 9h1.946c.089-1.546.383-2.97.837-4.118A6.004 6.004 0 004.083 9zM10 2a8 8 0 100 16A8 8 0 0010 2zm0 2c-.076 0-.232.032-.465.262-.238.234-.497.623-.737 1.182-.389.907-.673 2.142-.766 3.556h3.936c-.093-1.414-.377-2.649-.766-3.556-.24-.56-.5-.948-.737-1.182C10.232 4.032 10.076 4 10 4zm3.971 5c-.089-1.546-.383-2.97-.837-4.118A6.004 6.004 0 0115.917 9h-1.946zm-2.003 2H8.032c.093 1.414.377 2.649.766 3.556.24.56.5.948.737 1.182.233.23.389.262.465.262.076 0 .232-.032.465-.262.238-.234.498-.623.737-1.182.389-.907.673-2.142.766-3.556zm1.166 4.118c.454-1.147.748-2.572.837-4.118h1.946a6.004 6.004 0 01-2.783 4.118zm-6.268 0C6.412 13.97 6.118 12.546 6.03 11H4.083a6.004 6.004 0 002.783 4.118z" clipRule="evenodd"/></svg>,
  System: (p) => <svg {...p} viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd"/></svg>,
  Send: (p) => <svg {...p} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg>,
  Note: (p) => <svg {...p} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>,
  Check: (p) => <svg {...p} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>,
  Escalate: (p) => <svg {...p} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>,
  Assign: (p) => <svg {...p} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>,
  Copy: (p) => <svg {...p} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>,
  Spin: (p) => <svg {...p} fill="none" viewBox="0 0 24 24" className={`animate-spin ${p.className}`}><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/></svg>,
};

const CHANNEL_ICON = { email: Icon.Email, whatsapp: Icon.WhatsApp, web_form: Icon.Web, system: Icon.System };
const CHANNEL_COLOR = {
  email:    'text-blue-600 bg-blue-100',
  whatsapp: 'text-green-600 bg-green-100',
  web_form: 'text-purple-600 bg-purple-100',
  system:   'text-gray-500 bg-gray-100',
};

// ── Helpers ─────────────────────────────────────────────────────────────────

function fmt(iso, opts = {}) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', ...opts,
  });
}

function relTime(iso) {
  if (!iso) return '';
  const s = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (s < 60)   return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

function initials(name = '') {
  return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

// ── Small UI atoms ──────────────────────────────────────────────────────────

function Badge({ children, className }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${className}`}>
      {children}
    </span>
  );
}

function SectionTitle({ children }) {
  return <p className="text-[11px] font-semibold uppercase tracking-widest text-gray-400 mb-3">{children}</p>;
}

function ActionBtn({ icon: Ic, label, onClick, variant = 'default', disabled, loading }) {
  const styles = {
    default:  'border-gray-200 text-gray-600 hover:bg-gray-50',
    green:    'border-green-200 text-green-700 bg-green-50 hover:bg-green-100',
    red:      'border-red-200 text-red-600 hover:bg-red-50',
    indigo:   'border-indigo-200 text-indigo-600 hover:bg-indigo-50',
    amber:    'border-amber-200 text-amber-700 bg-amber-50 hover:bg-amber-100',
  };
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${styles[variant]}`}
    >
      {loading ? <Icon.Spin className="h-3.5 w-3.5" /> : <Ic className="h-3.5 w-3.5" />}
      {label}
    </button>
  );
}

// ── Channel pill ────────────────────────────────────────────────────────────

function ChannelPill({ channel }) {
  const Ic = CHANNEL_ICON[channel] || Icon.Web;
  const col = CHANNEL_COLOR[channel] || CHANNEL_COLOR.web_form;
  return (
    <span className={`inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-xs font-medium ${col}`}>
      <Ic className="h-3 w-3" />
      {channel?.replace('_', ' ')}
    </span>
  );
}

// ── Message bubble ──────────────────────────────────────────────────────────

function MessageBubble({ msg, isLast }) {
  const isCustomer = msg.role === 'customer';
  const isAI       = msg.role === 'ai';
  const isHuman    = msg.role === 'human';
  const isNote     = msg.role === 'internal_note';

  const ChIc = CHANNEL_ICON[msg.channel] || Icon.Web;

  // Internal note — full-width yellow banner
  if (isNote) {
    return (
      <div className="flex items-start gap-2 px-2 py-2.5 rounded-xl bg-amber-50 border border-amber-100">
        <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-amber-200 flex-shrink-0 mt-0.5">
          <Icon.Note className="h-3.5 w-3.5 text-amber-700" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[11px] font-semibold text-amber-700 mb-0.5">Internal Note · {msg.sender_name}</p>
          <p className="text-xs text-amber-800 leading-relaxed whitespace-pre-line">{msg.content}</p>
          <p className="text-[10px] text-amber-500 mt-1">{fmt(msg.created_at)}</p>
        </div>
      </div>
    );
  }

  // Avatar config
  const avatarCls = isCustomer
    ? 'bg-gradient-to-br from-blue-500 to-indigo-600 text-white'
    : isAI
    ? 'bg-gradient-to-br from-gray-600 to-gray-800 text-white'
    : 'bg-gradient-to-br from-indigo-500 to-purple-600 text-white';

  // Bubble config
  const bubbleCls = isCustomer
    ? 'bg-gradient-to-br from-blue-600 to-indigo-600 text-white rounded-tr-sm'
    : isAI
    ? 'bg-white border border-gray-100 text-gray-800 rounded-tl-sm shadow-sm'
    : 'bg-gradient-to-br from-indigo-50 to-purple-50 border border-indigo-100 text-indigo-900 rounded-tl-sm';

  const align = isCustomer ? 'flex-row-reverse' : 'flex-row';

  return (
    <div className={`flex gap-3 ${align}`}>
      {/* Avatar */}
      <div className={`flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold ${avatarCls}`}>
        {initials(msg.sender_name)}
      </div>

      {/* Content column */}
      <div className={`max-w-[72%] flex flex-col gap-1 ${isCustomer ? 'items-end' : 'items-start'}`}>
        {/* Sender label */}
        <div className={`flex items-center gap-2 px-1 ${isCustomer ? 'flex-row-reverse' : 'flex-row'}`}>
          <span className="text-[11px] font-semibold text-gray-500">{msg.sender_name}</span>
          {isHuman && (
            <span className="rounded-full bg-indigo-100 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-600">
              Human Agent
            </span>
          )}
        </div>

        {/* Bubble */}
        <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${bubbleCls}`}>
          <p className="whitespace-pre-line">{msg.content}</p>
        </div>

        {/* Meta row */}
        <div className={`flex items-center gap-2 px-1 flex-wrap ${isCustomer ? 'flex-row-reverse' : 'flex-row'}`}>
          <span className="text-[11px] text-gray-400">{relTime(msg.created_at)}</span>
          <ChannelPill channel={msg.channel} />
          {msg.latency_ms && (
            <span className="text-[11px] text-gray-400">{(msg.latency_ms / 1000).toFixed(1)}s</span>
          )}
          {msg.delivery_status && msg.delivery_status !== 'delivered' && msg.delivery_status !== 'internal' && (
            <span className="text-[11px] italic text-gray-400">{msg.delivery_status}</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Left panel: Ticket details ──────────────────────────────────────────────

function TicketDetails({ ticket, onAction, actionLoading }) {
  const [copied, setCopied] = useState(false);
  const sc = STATUS_CFG[ticket.status] || STATUS_CFG.open;

  const copyId = () => {
    navigator.clipboard.writeText(ticket.ticket_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const c = ticket.customer;

  return (
    <div className="h-full flex flex-col overflow-y-auto space-y-5 p-5">

      {/* Ticket ID + status */}
      <div className="space-y-2">
        <SectionTitle>Ticket</SectionTitle>
        <div className="flex items-center justify-between">
          <Badge className={sc.light}>
            <span className={`h-1.5 w-1.5 rounded-full ${sc.dot}`} />
            {sc.label}
          </Badge>
          <Badge className={PRIORITY_CFG[ticket.priority]}>
            {ticket.priority?.toUpperCase()}
          </Badge>
        </div>
        <button
          onClick={copyId}
          className="flex items-center gap-1.5 w-full rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 hover:bg-gray-100 transition-colors group"
        >
          <span className="font-mono text-xs text-gray-500 truncate flex-1 text-left">
            {ticket.ticket_id}
          </span>
          <Icon.Copy className={`h-3.5 w-3.5 flex-shrink-0 transition-colors ${copied ? 'text-green-500' : 'text-gray-300 group-hover:text-gray-500'}`} />
        </button>
        {copied && <p className="text-[11px] text-green-600 text-center">Copied!</p>}
      </div>

      {/* Times */}
      <div className="space-y-2">
        <SectionTitle>Timeline</SectionTitle>
        <div className="space-y-1.5">
          {[
            { label: 'Created',     value: fmt(ticket.created_at) },
            { label: 'Updated',     value: fmt(ticket.updated_at) },
            ticket.resolved_at && { label: 'Resolved', value: fmt(ticket.resolved_at) },
          ].filter(Boolean).map(({ label, value }) => (
            <div key={label} className="flex justify-between items-baseline">
              <span className="text-xs text-gray-400">{label}</span>
              <span className="text-xs font-medium text-gray-700">{value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Category + channel */}
      <div className="space-y-2">
        <SectionTitle>Classification</SectionTitle>
        <div className="flex flex-wrap gap-2">
          <span className="rounded-lg bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600 capitalize">
            {ticket.category}
          </span>
          <ChannelPill channel={ticket.source_channel} />
        </div>
      </div>

      {/* Escalation reason */}
      {ticket.escalation_reason && (
        <div className="rounded-xl border border-red-100 bg-red-50 p-3 space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-red-500">Escalation Reason</p>
          <p className="text-xs text-red-700 leading-relaxed">{ticket.escalation_reason}</p>
        </div>
      )}

      <hr className="border-gray-100" />

      {/* Customer */}
      <div className="space-y-3">
        <SectionTitle>Customer</SectionTitle>

        {/* Avatar + name */}
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-sm font-bold text-white flex-shrink-0">
            {initials(c.name)}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-gray-900 truncate">{c.name}</p>
            <p className="text-xs text-gray-400 truncate">{c.company}</p>
          </div>
        </div>

        {/* Contact details */}
        <div className="space-y-1.5">
          {[
            { label: 'Email',   value: c.email },
            { label: 'Phone',   value: c.phone },
            { label: 'Plan',    value: c.plan },
            { label: 'Tickets', value: `${c.total_tickets} total` },
            { label: 'Customer since', value: fmt(c.since + 'T00:00:00Z', { year: 'numeric', month: 'short', day: 'numeric', hour: undefined, minute: undefined }) },
          ].filter(r => r.value).map(({ label, value }) => (
            <div key={label} className="flex justify-between items-baseline gap-2">
              <span className="text-xs text-gray-400 flex-shrink-0">{label}</span>
              <span className="text-xs font-medium text-gray-700 text-right truncate">{value}</span>
            </div>
          ))}
        </div>

        {/* Channel history */}
        <div className="space-y-1">
          <p className="text-[11px] text-gray-400 font-medium">Channels Used</p>
          <div className="flex flex-wrap gap-1.5">
            {(c.channels_used || [ticket.source_channel]).map(ch => (
              <ChannelPill key={ch} channel={ch} />
            ))}
          </div>
        </div>
      </div>

      <hr className="border-gray-100" />

      {/* Action buttons */}
      <div className="space-y-2">
        <SectionTitle>Actions</SectionTitle>
        <div className="flex flex-col gap-2">
          {ticket.status !== 'resolved' && (
            <ActionBtn
              icon={Icon.Check}
              label="Mark Resolved"
              variant="green"
              onClick={() => onAction('resolve')}
              loading={actionLoading === 'resolve'}
            />
          )}
          {['open', 'in_progress'].includes(ticket.status) && (
            <ActionBtn
              icon={Icon.Escalate}
              label="Escalate to Human"
              variant="red"
              onClick={() => onAction('escalate')}
              loading={actionLoading === 'escalate'}
            />
          )}
          <ActionBtn
            icon={Icon.Assign}
            label="Assign to Agent"
            variant="indigo"
            onClick={() => onAction('assign')}
            loading={actionLoading === 'assign'}
          />
        </div>
      </div>
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

export default function ConversationViewer({ ticketId, apiBase = '' }) {
  const [ticket,      setTicket]      = useState(null);
  const [messages,    setMessages]    = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [fetchError,  setFetchError]  = useState('');
  const [actionLoad,  setActionLoad]  = useState(null);  // 'resolve'|'escalate'|'assign'|null
  const [actionToast, setActionToast] = useState('');

  // Reply box state
  const [replyText,   setReplyText]   = useState('');
  const [replyMode,   setReplyMode]   = useState('reply');  // 'reply' | 'note'
  const [replyCh,     setReplyCh]     = useState('email');
  const [replySending,setReplySending]= useState(false);
  const [replyError,  setReplyError]  = useState('');

  const threadRef = useRef(null);

  // ── Fetch ──────────────────────────────────────────────────────────────

  useEffect(() => {
    if (!ticketId) { setLoading(false); return; }

    async function load() {
      setLoading(true);
      setFetchError('');
      try {
        const [tRes, mRes] = await Promise.all([
          fetch(`${apiBase}/api/tickets/${ticketId}`),
          fetch(`${apiBase}/api/tickets/${ticketId}/messages`),
        ]);
        if (!tRes.ok) throw new Error(tRes.status === 404 ? 'Ticket not found.' : 'Failed to load ticket.');
        const tData = await tRes.json();
        setTicket(tData);
        if (tRes.ok) setReplyCh(tData.source_channel || 'email');

        if (mRes.ok) {
          const mData = await mRes.json();
          setMessages(Array.isArray(mData) ? mData : mData.messages || []);
        }
      } catch (err) {
        setFetchError(err.message);
        // Fallback to mock data for demo
        setTicket(MOCK_TICKET);
        setMessages(MOCK_MESSAGES);
        setReplyCh(MOCK_TICKET.source_channel);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [ticketId, apiBase]);

  // Scroll thread to bottom when messages load/update
  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [messages]);

  // ── Actions ────────────────────────────────────────────────────────────

  const handleAction = useCallback(async (type) => {
    setActionLoad(type);
    const url = `${apiBase}/api/tickets/${ticket.ticket_id}/${type}`;
    try {
      const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      if (!res.ok) throw new Error('Action failed.');
      const updates = {
        resolve:  { status: 'resolved',    resolved_at: new Date().toISOString() },
        escalate: { status: 'escalated' },
        assign:   { assigned_to: 'human' },
      };
      setTicket(prev => ({ ...prev, ...(updates[type] || {}) }));
      setActionToast({ resolve: 'Ticket resolved ✓', escalate: 'Escalated to human ✓', assign: 'Assigned to human agent ✓' }[type]);
    } catch {
      // Optimistic update even on demo (no real API)
      const updates = {
        resolve:  { status: 'resolved',    resolved_at: new Date().toISOString() },
        escalate: { status: 'escalated' },
        assign:   { assigned_to: 'human' },
      };
      setTicket(prev => ({ ...prev, ...(updates[type] || {}) }));
      setActionToast({ resolve: 'Resolved ✓', escalate: 'Escalated ✓', assign: 'Assigned ✓' }[type]);
    } finally {
      setActionLoad(null);
      setTimeout(() => setActionToast(''), 3000);
    }
  }, [ticket, apiBase]);

  // ── Reply / Note send ──────────────────────────────────────────────────

  const handleSend = async () => {
    const text = replyText.trim();
    if (!text || text.length < 2) { setReplyError('Message is too short.'); return; }
    setReplySending(true);
    setReplyError('');

    const endpoint = replyMode === 'note'
      ? `${apiBase}/api/tickets/${ticket.ticket_id}/note`
      : `${apiBase}/api/tickets/${ticket.ticket_id}/reply`;

    const body = replyMode === 'note'
      ? { content: text }
      : { message: text, channel: replyCh };

    try {
      await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch { /* demo: optimistic add */ }

    // Optimistically append to thread
    const newMsg = {
      id: `local-${Date.now()}`,
      role: replyMode === 'note' ? 'internal_note' : 'human',
      sender_name: replyMode === 'note' ? 'Admin (You)' : 'You (Agent)',
      channel: replyMode === 'note' ? 'system' : replyCh,
      content: text,
      created_at: new Date().toISOString(),
      delivery_status: replyMode === 'note' ? 'internal' : 'sent',
    };
    setMessages(prev => [...prev, newMsg]);
    setReplyText('');
    setReplySending(false);
  };

  // ── Loading / Error states ─────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-3">
          <Icon.Spin className="h-8 w-8 text-blue-500" />
          <p className="text-sm text-gray-500">Loading conversation…</p>
        </div>
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-gray-700 font-medium">Ticket not found</p>
          <p className="text-sm text-gray-400 mt-1">{fetchError || 'Please check the ticket ID.'}</p>
        </div>
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <>
      <style>{`
        @keyframes fadeUp { from { opacity:0; transform:translateY(6px) } to { opacity:1; transform:translateY(0) } }
        .fade-up { animation: fadeUp 0.3s ease both }
        @keyframes toastIn { from { opacity:0; transform:translateY(8px) } to { opacity:1; transform:translateY(0) } }
        .toast-in { animation: toastIn 0.25s ease both }
      `}</style>

      <div className="flex h-screen overflow-hidden bg-gray-50 font-sans">

        {/* ── LEFT PANEL: Ticket Details ─────────────────────────── */}
        <aside className="w-72 flex-shrink-0 border-r border-gray-200 bg-white overflow-hidden flex flex-col">

          {/* Panel header */}
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-900">Ticket Details</h2>
            <a href="/admin" className="text-xs text-blue-600 hover:text-blue-700">← Back</a>
          </div>

          <div className="flex-1 overflow-y-auto">
            <TicketDetails
              ticket={ticket}
              onAction={handleAction}
              actionLoading={actionLoad}
            />
          </div>
        </aside>

        {/* ── RIGHT PANEL: Conversation ──────────────────────────── */}
        <main className="flex-1 flex flex-col overflow-hidden">

          {/* Thread header */}
          <div className="flex-shrink-0 flex items-center justify-between gap-3 px-6 py-4 border-b border-gray-200 bg-white">
            <div className="flex items-center gap-3 min-w-0">
              <div className="h-9 w-9 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-sm font-bold text-white flex-shrink-0">
                {initials(ticket.customer?.name || 'U')}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-gray-900 truncate">{ticket.customer?.name}</p>
                <p className="text-xs text-gray-400 truncate">{ticket.customer?.email}</p>
              </div>
            </div>

            {/* Status + message count */}
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="text-xs text-gray-400">{messages.length} messages</span>
              <Badge className={STATUS_CFG[ticket.status]?.light}>
                <span className={`h-1.5 w-1.5 rounded-full ${STATUS_CFG[ticket.status]?.dot}`} />
                {STATUS_CFG[ticket.status]?.label}
              </Badge>
            </div>
          </div>

          {/* Action toast */}
          {actionToast && (
            <div className="mx-6 mt-3 flex items-center gap-2 rounded-xl bg-green-50 border border-green-100 px-4 py-2.5 toast-in">
              <Icon.Check className="h-4 w-4 text-green-500" />
              <p className="text-sm text-green-700 font-medium">{actionToast}</p>
            </div>
          )}

          {/* Thread */}
          <div
            ref={threadRef}
            className="flex-1 overflow-y-auto px-6 py-4 space-y-4"
          >
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center opacity-60">
                <p className="text-sm text-gray-400">No messages yet.</p>
              </div>
            ) : (
              messages.map((msg, i) => (
                <div key={msg.id || i} className="fade-up" style={{ animationDelay: `${Math.min(i * 40, 200)}ms` }}>
                  <MessageBubble msg={msg} isLast={i === messages.length - 1} />
                </div>
              ))
            )}
          </div>

          {/* ── Reply box ──────────────────────────────────────── */}
          {ticket.status !== 'resolved' && (
            <div className="flex-shrink-0 border-t border-gray-200 bg-white px-6 py-4 space-y-3">

              {/* Mode + channel toggles */}
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-1 rounded-xl bg-gray-100 p-1">
                  {[
                    { id: 'reply', label: 'Reply', icon: Icon.Send },
                    { id: 'note',  label: 'Internal Note', icon: Icon.Note },
                  ].map(({ id, label, icon: Ic }) => (
                    <button
                      key={id}
                      onClick={() => setReplyMode(id)}
                      className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                        replyMode === id
                          ? id === 'note'
                            ? 'bg-amber-100 text-amber-700 shadow-sm'
                            : 'bg-white text-gray-900 shadow-sm'
                          : 'text-gray-500 hover:text-gray-700'
                      }`}
                    >
                      <Ic className="h-3.5 w-3.5" />
                      {label}
                    </button>
                  ))}
                </div>

                {/* Channel selector (only in reply mode) */}
                {replyMode === 'reply' && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">via</span>
                    <select
                      value={replyCh}
                      onChange={e => setReplyCh(e.target.value)}
                      className="rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1.5 text-xs text-gray-700 outline-none focus:ring-2 focus:ring-blue-200"
                    >
                      {CHANNELS.map(({ value, label }) => (
                        <option key={value} value={value}>{label}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              {/* Textarea + send */}
              <div className={`flex gap-3 items-end rounded-2xl border p-3 transition-colors ${
                replyMode === 'note'
                  ? 'border-amber-200 bg-amber-50'
                  : 'border-gray-200 bg-gray-50'
              }`}>
                <textarea
                  rows={3}
                  value={replyText}
                  onChange={e => { setReplyText(e.target.value); setReplyError(''); }}
                  onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleSend(); }}
                  placeholder={
                    replyMode === 'note'
                      ? 'Add an internal note (only visible to agents)…'
                      : `Type your reply to ${ticket.customer?.name?.split(' ')[0] || 'customer'}… (Ctrl+Enter to send)`
                  }
                  disabled={replySending}
                  className={`flex-1 resize-none bg-transparent text-sm text-gray-800 outline-none placeholder:text-gray-400 ${
                    replyMode === 'note' ? 'placeholder:text-amber-400' : ''
                  }`}
                />

                <button
                  onClick={handleSend}
                  disabled={replySending || replyText.trim().length < 2}
                  className={`flex-shrink-0 flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-xs font-semibold text-white shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed active:scale-95 ${
                    replyMode === 'note'
                      ? 'bg-amber-500 hover:bg-amber-600'
                      : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500'
                  }`}
                >
                  {replySending
                    ? <><Icon.Spin className="h-4 w-4" />Sending…</>
                    : replyMode === 'note'
                    ? <><Icon.Note className="h-4 w-4" />Add Note</>
                    : <><Icon.Send className="h-4 w-4" />Send</>}
                </button>
              </div>

              {replyError && <p className="text-xs text-red-500 px-1">{replyError}</p>}

              <p className="text-[11px] text-gray-400 text-center">
                {replyMode === 'note'
                  ? 'Internal notes are not sent to the customer.'
                  : `Reply will be sent via ${CHANNELS.find(c => c.value === replyCh)?.label}.`}
              </p>
            </div>
          )}

          {/* Resolved notice */}
          {ticket.status === 'resolved' && (
            <div className="flex-shrink-0 border-t border-green-100 bg-green-50 px-6 py-4 flex items-center gap-3">
              <Icon.Check className="h-5 w-5 text-green-500 flex-shrink-0" />
              <p className="text-sm text-green-700">
                This ticket was resolved on {fmt(ticket.resolved_at)}.
                {ticket.resolution_notes && ` · ${ticket.resolution_notes}`}
              </p>
            </div>
          )}
        </main>
      </div>
    </>
  );
}
