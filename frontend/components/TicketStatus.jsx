/**
 * frontend/components/TicketStatus.jsx
 *
 * NimbusFlow — Ticket Status Checker
 * Customers enter their Ticket ID to view status, conversation timeline,
 * add a reply, escalate, or download the conversation.
 *
 * API endpoints used:
 *   GET  /support/ticket/{id}           — ticket metadata + status
 *   GET  /support/ticket/{id}/messages  — conversation history
 *   POST /support/ticket/{id}/reply     — add customer reply
 *   POST /support/ticket/{id}/escalate  — request human escalation
 *
 * Usage (Next.js):
 *   import TicketStatus from '@/components/TicketStatus';
 *   export default function StatusPage() {
 *     return <TicketStatus apiBase="/support" />;
 *   }
 *
 * Requirements: React 18+, Tailwind CSS
 */

import { useState, useRef, useCallback } from 'react';

// ── Constants ──────────────────────────────────────────────────────────────

const STATUS_CONFIG = {
  open:        { label: 'Open',        color: 'bg-blue-100 text-blue-700 ring-blue-200',   dot: 'bg-blue-500',   icon: '🔵' },
  in_progress: { label: 'In Progress', color: 'bg-amber-100 text-amber-700 ring-amber-200', dot: 'bg-amber-400 animate-pulse', icon: '🟡' },
  resolved:    { label: 'Resolved',    color: 'bg-green-100 text-green-700 ring-green-200', dot: 'bg-green-500',  icon: '🟢' },
  escalated:   { label: 'Escalated',   color: 'bg-red-100 text-red-700 ring-red-200',       dot: 'bg-red-500 animate-pulse',  icon: '🔴' },
};

const PRIORITY_CONFIG = {
  low:    { label: 'Low',    color: 'text-green-600 bg-green-50 ring-green-200' },
  medium: { label: 'Medium', color: 'text-amber-600 bg-amber-50 ring-amber-200' },
  high:   { label: 'High',   color: 'text-red-600 bg-red-50 ring-red-200' },
};

const CHANNEL_CONFIG = {
  email:    { label: 'Email',    icon: EmailIcon },
  whatsapp: { label: 'WhatsApp', icon: WhatsAppIcon },
  web_form: { label: 'Web',      icon: WebIcon },
};

// ── SVG icon components ─────────────────────────────────────────────────────

function EmailIcon({ className = 'h-3.5 w-3.5' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="currentColor">
      <path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z"/>
      <path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z"/>
    </svg>
  );
}

function WhatsAppIcon({ className = 'h-3.5 w-3.5' }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/>
      <path d="M12 0C5.373 0 0 5.373 0 12c0 2.127.558 4.126 1.532 5.862L.072 23.928l6.243-1.636A11.935 11.935 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.818 9.818 0 01-5.009-1.374l-.36-.213-3.708.972.989-3.617-.233-.371A9.818 9.818 0 1112 21.818z"/>
    </svg>
  );
}

function WebIcon({ className = 'h-3.5 w-3.5' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M4.083 9h1.946c.089-1.546.383-2.97.837-4.118A6.004 6.004 0 004.083 9zM10 2a8 8 0 100 16A8 8 0 0010 2zm0 2c-.076 0-.232.032-.465.262-.238.234-.497.623-.737 1.182-.389.907-.673 2.142-.766 3.556h3.936c-.093-1.414-.377-2.649-.766-3.556-.24-.56-.5-.948-.737-1.182C10.232 4.032 10.076 4 10 4zm3.971 5c-.089-1.546-.383-2.97-.837-4.118A6.004 6.004 0 0115.917 9h-1.946zm-2.003 2H8.032c.093 1.414.377 2.649.766 3.556.24.56.5.948.737 1.182.233.23.389.262.465.262.076 0 .232-.032.465-.262.238-.234.498-.623.737-1.182.389-.907.673-2.142.766-3.556zm1.166 4.118c.454-1.147.748-2.572.837-4.118h1.946a6.004 6.004 0 01-2.783 4.118zm-6.268 0C6.412 13.97 6.118 12.546 6.03 11H4.083a6.004 6.004 0 002.783 4.118z" clipRule="evenodd"/>
    </svg>
  );
}

function SpinnerIcon({ className = 'h-5 w-5' }) {
  return (
    <svg className={`animate-spin ${className}`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
    </svg>
  );
}

// ── Small UI helpers ────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.open;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ring-1 ${cfg.color}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

function PriorityBadge({ priority }) {
  const cfg = PRIORITY_CONFIG[priority] || PRIORITY_CONFIG.medium;
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${cfg.color}`}>
      {cfg.label}
    </span>
  );
}

function ChannelBadge({ channel }) {
  const cfg = CHANNEL_CONFIG[channel] || CHANNEL_CONFIG.web_form;
  const Icon = cfg.icon;
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
      <Icon />
      {cfg.label}
    </span>
  );
}

function MetaItem({ label, value }) {
  return (
    <div className="min-w-0">
      <p className="text-xs text-gray-400 uppercase tracking-wide font-medium mb-0.5">{label}</p>
      <p className="text-sm font-semibold text-gray-800 truncate">{value}</p>
    </div>
  );
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function formatTime(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

// ── Message bubble ──────────────────────────────────────────────────────────

function MessageBubble({ message }) {
  const isCustomer = message.role === 'customer';
  const ChannelIcon = (CHANNEL_CONFIG[message.channel] || CHANNEL_CONFIG.web_form).icon;

  return (
    <div className={`flex gap-3 ${isCustomer ? 'flex-row-reverse' : 'flex-row'}`}>

      {/* Avatar */}
      <div className={`flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold
        ${isCustomer
          ? 'bg-gradient-to-br from-blue-500 to-indigo-600 text-white'
          : 'bg-gradient-to-br from-gray-700 to-gray-900 text-white'}`}>
        {isCustomer ? 'U' : 'AI'}
      </div>

      {/* Bubble */}
      <div className={`max-w-[75%] ${isCustomer ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
        <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm
          ${isCustomer
            ? 'rounded-tr-sm bg-gradient-to-br from-blue-600 to-indigo-600 text-white'
            : 'rounded-tl-sm bg-white border border-gray-100 text-gray-800'}`}>
          {message.content}
        </div>

        {/* Metadata row */}
        <div className={`flex items-center gap-2 px-1 ${isCustomer ? 'flex-row-reverse' : 'flex-row'}`}>
          <span className="text-[11px] text-gray-400">{formatTime(message.created_at)}</span>
          <ChannelBadge channel={message.channel} />
          {message.delivery_status && message.delivery_status !== 'delivered' && (
            <span className="text-[11px] text-gray-400 italic">{message.delivery_status}</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Timeline connector ──────────────────────────────────────────────────────

function TimelineDivider({ label }) {
  return (
    <div className="flex items-center gap-3 py-1">
      <div className="flex-1 h-px bg-gray-100" />
      <span className="text-[11px] text-gray-400 font-medium whitespace-nowrap">{label}</span>
      <div className="flex-1 h-px bg-gray-100" />
    </div>
  );
}

// ── Reply form ──────────────────────────────────────────────────────────────

function ReplyForm({ ticketId, apiBase, onSent, onCancel }) {
  const [text,    setText]    = useState('');
  const [sending, setSending] = useState(false);
  const [error,   setError]   = useState('');
  const MAX = 1000;

  const handleSend = async () => {
    if (text.trim().length < 5) { setError('Message must be at least 5 characters.'); return; }
    setSending(true);
    setError('');
    try {
      const res  = await fetch(`${apiBase}/ticket/${ticketId}/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to send reply.');
      onSent();
    } catch (err) {
      setError(err.message);
      setSending(false);
    }
  };

  return (
    <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4 space-y-3">
      <p className="text-sm font-semibold text-gray-700">Add a reply</p>
      <textarea
        rows={3}
        placeholder="Type your message…"
        value={text}
        onChange={e => setText(e.target.value)}
        disabled={sending}
        maxLength={MAX}
        className="w-full rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm text-gray-800 shadow-sm outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400 resize-none transition-all"
      />
      <div className="flex items-center justify-between">
        <span className={`text-xs ${text.length > MAX * 0.9 ? 'text-amber-500' : 'text-gray-400'}`}>
          {text.length}/{MAX}
        </span>
        {error && <p className="text-xs text-red-500">{error}</p>}
      </div>
      <div className="flex gap-2 justify-end">
        <button
          onClick={onCancel}
          disabled={sending}
          className="rounded-lg px-4 py-2 text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleSend}
          disabled={sending || text.trim().length < 5}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {sending ? <><SpinnerIcon className="h-4 w-4" />Sending…</> : 'Send Reply'}
        </button>
      </div>
    </div>
  );
}

// ── Escalate confirm ────────────────────────────────────────────────────────

function EscalateConfirm({ ticketId, apiBase, onDone, onCancel }) {
  const [reason,    setReason]    = useState('');
  const [sending,   setSending]   = useState(false);
  const [error,     setError]     = useState('');

  const handleEscalate = async () => {
    setSending(true);
    setError('');
    try {
      const res  = await fetch(`${apiBase}/ticket/${ticketId}/escalate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: reason.trim() || 'Customer requested human support.' }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to escalate.');
      onDone();
    } catch (err) {
      setError(err.message);
      setSending(false);
    }
  };

  return (
    <div className="rounded-2xl border border-red-100 bg-red-50 p-4 space-y-3">
      <div className="flex items-start gap-2">
        <svg className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd"/>
        </svg>
        <div>
          <p className="text-sm font-semibold text-red-800">Request Human Support</p>
          <p className="text-xs text-red-600 mt-0.5">
            This will route your ticket to a human agent. Response may take 1–4 hours.
          </p>
        </div>
      </div>
      <textarea
        rows={2}
        placeholder="Optional: tell us why you'd like to speak with a human…"
        value={reason}
        onChange={e => setReason(e.target.value)}
        disabled={sending}
        className="w-full rounded-xl border border-red-200 bg-white px-4 py-2.5 text-sm text-gray-800 outline-none focus:ring-2 focus:ring-red-200 focus:border-red-400 resize-none transition-all"
      />
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex gap-2 justify-end">
        <button
          onClick={onCancel}
          disabled={sending}
          className="rounded-lg px-4 py-2 text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleEscalate}
          disabled={sending}
          className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-red-700 disabled:opacity-50 transition-colors"
        >
          {sending ? <><SpinnerIcon className="h-4 w-4" />Escalating…</> : 'Request Human Agent'}
        </button>
      </div>
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

export default function TicketStatus({ apiBase = '/support' }) {
  const [inputId,     setInputId]     = useState('');
  const [status,      setStatus]      = useState('idle');   // idle|loading|loaded|error
  const [ticket,      setTicket]      = useState(null);
  const [messages,    setMessages]    = useState([]);
  const [fetchError,  setFetchError]  = useState('');
  const [showReply,   setShowReply]   = useState(false);
  const [showEscalate,setShowEscalate]= useState(false);
  const [replySuccess,setReplySuccess]= useState(false);
  const [escalSuccess,setEscalSuccess]= useState(false);
  const printRef = useRef(null);

  // ── Fetch ────────────────────────────────────────────────────────────────

  const handleCheck = useCallback(async (e) => {
    e?.preventDefault();
    const id = inputId.trim();
    if (!id) return;

    setStatus('loading');
    setFetchError('');
    setTicket(null);
    setMessages([]);
    setShowReply(false);
    setShowEscalate(false);
    setReplySuccess(false);
    setEscalSuccess(false);

    try {
      const [ticketRes, msgsRes] = await Promise.all([
        fetch(`${apiBase}/ticket/${id}`),
        fetch(`${apiBase}/ticket/${id}/messages`),
      ]);

      if (ticketRes.status === 404) throw new Error('Ticket not found. Please check the ID and try again.');
      if (!ticketRes.ok) throw new Error('Service temporarily unavailable. Please try again.');

      const ticketData = await ticketRes.json();
      setTicket(ticketData);

      // Messages endpoint is optional — degrade gracefully if not available
      if (msgsRes.ok) {
        const msgsData = await msgsRes.json();
        setMessages(Array.isArray(msgsData) ? msgsData : msgsData.messages || []);
      }

      setStatus('loaded');
    } catch (err) {
      setFetchError(err.message || 'Unknown error. Please try again.');
      setStatus('error');
    }
  }, [inputId, apiBase]);

  // ── Print/Download ───────────────────────────────────────────────────────

  const handlePrint = () => window.print();

  const handleDownload = () => {
    if (!ticket) return;
    const lines = [
      `NimbusFlow Support — Ticket ${ticket.ticket_id}`,
      `Status: ${ticket.status}   Priority: ${ticket.priority}`,
      `Created: ${formatDate(ticket.created_at)}`,
      ticket.resolved_at ? `Resolved: ${formatDate(ticket.resolved_at)}` : '',
      '',
      '── Conversation ──',
      '',
      ...messages.map(m =>
        `[${formatDate(m.created_at)}] ${m.role === 'customer' ? 'You' : 'Agent'} (${m.channel}):\n${m.content}\n`
      ),
    ].filter(Boolean).join('\n');

    const blob = new Blob([lines], { type: 'text/plain' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `ticket-${ticket.ticket_id}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // ── Group messages by date ───────────────────────────────────────────────

  const groupedMessages = messages.reduce((groups, msg) => {
    const day = msg.created_at
      ? new Date(msg.created_at).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })
      : 'Unknown date';
    if (!groups[day]) groups[day] = [];
    groups[day].push(msg);
    return groups;
  }, {});

  const canEscalate = ticket && ['open', 'in_progress'].includes(ticket.status) && !escalSuccess;
  const canReply    = ticket && ticket.status !== 'resolved' && !replySuccess;

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <>
      <style>{`
        @keyframes fadeIn  { from { opacity:0; transform:translateY(8px) }  to { opacity:1; transform:translateY(0) } }
        @keyframes slideUp { from { opacity:0; transform:translateY(16px) } to { opacity:1; transform:translateY(0) } }
        .animate-fadeIn  { animation: fadeIn  0.3s ease both }
        .animate-slideUp { animation: slideUp 0.4s ease both }
        @media print {
          .no-print { display: none !important; }
          body { background: white !important; }
        }
      `}</style>

      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 p-4 flex items-start justify-center pt-10">
        <div className="w-full max-w-2xl space-y-4 animate-slideUp">

          {/* ── Search card ──────────────────────────────────────────── */}
          <div className="rounded-3xl bg-white shadow-2xl shadow-blue-900/30 overflow-hidden">

            {/* Header */}
            <div className="relative overflow-hidden bg-gradient-to-br from-blue-600 via-blue-500 to-indigo-600 px-8 py-6">
              <div className="absolute -top-6 -right-6 h-24 w-24 rounded-full bg-white/5" />
              <div className="absolute -bottom-8 -left-4 h-20 w-20 rounded-full bg-white/5" />
              <div className="relative flex items-center gap-4">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/15">
                  <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                  </svg>
                </div>
                <div>
                  <h1 className="text-lg font-bold text-white">Check Ticket Status</h1>
                  <p className="text-xs text-blue-200 mt-0.5">Enter your ticket ID to view updates</p>
                </div>
              </div>
            </div>

            {/* Search form */}
            <form onSubmit={handleCheck} className="px-8 py-6">
              <div className="flex gap-3">
                <input
                  type="text"
                  value={inputId}
                  onChange={e => setInputId(e.target.value)}
                  placeholder="e.g. 3f8a2c1d-4b5e-6789-abcd-ef0123456789"
                  className="flex-1 rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm font-mono text-gray-700 shadow-sm outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400 transition-all placeholder:text-gray-300 placeholder:font-sans"
                />
                <button
                  type="submit"
                  disabled={!inputId.trim() || status === 'loading'}
                  className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-md hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-95"
                >
                  {status === 'loading'
                    ? <><SpinnerIcon className="h-4 w-4" />Checking…</>
                    : <>
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                        </svg>
                        Check Status
                      </>}
                </button>
              </div>

              {/* Error */}
              {status === 'error' && (
                <div className="mt-4 flex items-center gap-2.5 rounded-xl bg-red-50 border border-red-100 px-4 py-3 animate-fadeIn">
                  <svg className="h-5 w-5 text-red-400 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd"/>
                  </svg>
                  <p className="text-sm text-red-700">{fetchError}</p>
                </div>
              )}
            </form>
          </div>

          {/* ── Ticket detail card ────────────────────────────────────── */}
          {status === 'loaded' && ticket && (
            <div ref={printRef} className="rounded-3xl bg-white shadow-2xl shadow-blue-900/20 overflow-hidden animate-fadeIn">

              {/* Ticket header */}
              <div className="px-8 py-5 border-b border-gray-100">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <StatusBadge status={ticket.status} />
                      <PriorityBadge priority={ticket.priority} />
                    </div>
                    <p className="font-mono text-xs text-gray-400 mt-2 break-all">{ticket.ticket_id}</p>
                  </div>

                  {/* Action buttons */}
                  <div className="no-print flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={handleDownload}
                      title="Download conversation"
                      className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-700 transition-colors shadow-sm"
                    >
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                      </svg>
                      Download
                    </button>
                    <button
                      onClick={handlePrint}
                      title="Print conversation"
                      className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-700 transition-colors shadow-sm"
                    >
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"/>
                      </svg>
                      Print
                    </button>
                  </div>
                </div>

                {/* Metadata grid */}
                <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <MetaItem label="Created"      value={formatDate(ticket.created_at)} />
                  <MetaItem label="Last Updated"  value={formatDate(ticket.updated_at || ticket.created_at)} />
                  <MetaItem label="Category"      value={ticket.category || '—'} />
                  <MetaItem
                    label="Assigned To"
                    value={
                      ticket.status === 'escalated' || ticket.assigned_to === 'human'
                        ? '👤 Human Agent'
                        : '🤖 AI Support'
                    }
                  />
                </div>

                {/* Resolution notes */}
                {ticket.resolution_notes && (
                  <div className="mt-4 rounded-xl bg-green-50 border border-green-100 px-4 py-3">
                    <p className="text-xs font-semibold text-green-700 mb-1">Resolution</p>
                    <p className="text-sm text-green-800">{ticket.resolution_notes}</p>
                  </div>
                )}
              </div>

              {/* ── Conversation timeline ──────────────────────────── */}
              <div className="px-8 py-6 space-y-6">
                <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                  <svg className="h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                  </svg>
                  Conversation History
                  {messages.length > 0 && (
                    <span className="ml-auto text-xs text-gray-400 font-normal">
                      {messages.length} message{messages.length !== 1 ? 's' : ''}
                    </span>
                  )}
                </h2>

                {messages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-10 text-center">
                    <div className="h-12 w-12 rounded-full bg-gray-100 flex items-center justify-center mb-3">
                      <svg className="h-6 w-6 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                          d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                      </svg>
                    </div>
                    <p className="text-sm text-gray-400">No messages yet.</p>
                    <p className="text-xs text-gray-300 mt-1">Your conversation will appear here once the agent responds.</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {Object.entries(groupedMessages).map(([day, dayMessages]) => (
                      <div key={day} className="space-y-4">
                        <TimelineDivider label={day} />
                        {dayMessages.map((msg, i) => (
                          <MessageBubble key={msg.id || i} message={msg} />
                        ))}
                      </div>
                    ))}
                  </div>
                )}

                {/* ── Action panels ──────────────────────────────── */}
                <div className="no-print space-y-3 pt-2 border-t border-gray-100">

                  {/* Success notices */}
                  {replySuccess && (
                    <div className="flex items-center gap-2 rounded-xl bg-green-50 border border-green-100 px-4 py-3 animate-fadeIn">
                      <svg className="h-4 w-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/>
                      </svg>
                      <p className="text-sm text-green-700">Reply sent! Refresh to see it in the timeline.</p>
                    </div>
                  )}
                  {escalSuccess && (
                    <div className="flex items-center gap-2 rounded-xl bg-orange-50 border border-orange-100 px-4 py-3 animate-fadeIn">
                      <svg className="h-4 w-4 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/>
                      </svg>
                      <p className="text-sm text-orange-700">Escalated to a human agent. You'll hear back within 1–4 hours.</p>
                    </div>
                  )}

                  {/* Reply / Escalate forms */}
                  {showReply && !replySuccess && (
                    <ReplyForm
                      ticketId={ticket.ticket_id}
                      apiBase={apiBase}
                      onSent={() => { setShowReply(false); setReplySuccess(true); }}
                      onCancel={() => setShowReply(false)}
                    />
                  )}
                  {showEscalate && !escalSuccess && (
                    <EscalateConfirm
                      ticketId={ticket.ticket_id}
                      apiBase={apiBase}
                      onDone={() => { setShowEscalate(false); setEscalSuccess(true); }}
                      onCancel={() => setShowEscalate(false)}
                    />
                  )}

                  {/* Buttons row */}
                  {!showReply && !showEscalate && (
                    <div className="flex flex-wrap gap-2 pt-1">
                      {canReply && (
                        <button
                          onClick={() => setShowReply(true)}
                          className="flex items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm font-medium text-blue-700 hover:bg-blue-100 transition-colors"
                        >
                          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
                          </svg>
                          Add Reply
                        </button>
                      )}
                      {canEscalate && (
                        <button
                          onClick={() => setShowEscalate(true)}
                          className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-medium text-red-600 hover:bg-red-100 transition-colors"
                        >
                          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>
                          </svg>
                          Request Human Agent
                        </button>
                      )}
                      <button
                        onClick={() => { setStatus('idle'); setTicket(null); setInputId(''); }}
                        className="ml-auto flex items-center gap-2 rounded-xl border border-gray-200 px-4 py-2.5 text-sm font-medium text-gray-500 hover:bg-gray-50 transition-colors"
                      >
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                        </svg>
                        Check Another
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          <p className="text-center text-xs text-blue-300/40 pb-6">
            Powered by NimbusFlow AI Support
          </p>
        </div>
      </div>
    </>
  );
}
