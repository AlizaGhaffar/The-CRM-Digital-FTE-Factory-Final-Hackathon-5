/**
 * frontend/components/LandingPage.jsx
 * NimbusFlow — Purple-themed Landing Page (improved layout + centering)
 */

import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import SupportForm from './SupportForm';

function genTicket(prefix) {
  return `${prefix}-${Math.random().toString(36).substring(2, 8).toUpperCase()}`;
}

// ── Robot SVG (purple palette) ──────────────────────────────────────────────

function RobotIllustration() {
  return (
    <div className="relative w-full max-w-[300px] mx-auto select-none">
      {/* Floating badges */}
      <div className="absolute top-4 right-0 z-10 bg-violet-950/90 border border-violet-500/40
                      rounded-xl px-3 py-1.5 text-xs font-mono text-violet-300 backdrop-blur-sm
                      shadow-lg shadow-violet-500/20 animate-pulse">
        TK-1042
      </div>
      <div className="absolute top-32 -left-2 z-10 bg-purple-950/90 border border-purple-500/30
                      rounded-xl px-3 py-1.5 text-xs font-mono text-fuchsia-300 shadow-lg">
        ILP-3310
      </div>
      <div className="absolute bottom-20 right-2 z-10 bg-violet-950/70 border border-violet-400/30
                      rounded-lg px-2 py-1 text-xs font-mono text-violet-300 shadow-lg">
        #781
      </div>

      {/* Robot */}
      <svg viewBox="0 0 220 290" className="w-full drop-shadow-2xl" fill="none">
        {/* Ground glow */}
        <ellipse cx="110" cy="282" rx="65" ry="8" fill="#7c3aed" opacity="0.15" />

        {/* Head */}
        <rect x="62" y="38" width="96" height="86" rx="20" fill="#0f0720" stroke="#7c3aed" strokeWidth="1.5" />
        <rect x="68" y="44" width="84" height="74" rx="15" fill="#080414" />

        {/* Eyes */}
        <circle cx="92" cy="72" r="15" fill="#2d1b69" />
        <circle cx="92" cy="72" r="11" fill="#8b5cf6" opacity="0.95" />
        <circle cx="92" cy="72" r="6"  fill="white" />
        <circle cx="94" cy="70" r="2.5" fill="#0f0720" />
        <circle cx="96" cy="69" r="1"  fill="white" opacity="0.6" />

        <circle cx="128" cy="72" r="15" fill="#2d1b69" />
        <circle cx="128" cy="72" r="11" fill="#8b5cf6" opacity="0.95" />
        <circle cx="128" cy="72" r="6"  fill="white" />
        <circle cx="130" cy="70" r="2.5" fill="#0f0720" />
        <circle cx="132" cy="69" r="1"  fill="white" opacity="0.6" />

        {/* Mouth */}
        <rect x="86" y="98" width="48" height="12" rx="6" fill="#3b1f7a" opacity="0.9" />
        <rect x="90" y="100" width="40" height="8"  rx="4" fill="#7c3aed" opacity="0.5" />

        {/* Antenna */}
        <line x1="110" y1="38" x2="110" y2="16" stroke="#7c3aed" strokeWidth="2.5" strokeLinecap="round" />
        <circle cx="110" cy="10" r="7" fill="#a78bfa" />
        <circle cx="110" cy="10" r="3.5" fill="white" opacity="0.5" />

        {/* Ear bolts */}
        <circle cx="62" cy="78" r="5" fill="#2d1b69" stroke="#7c3aed" strokeWidth="1" />
        <circle cx="158" cy="78" r="5" fill="#2d1b69" stroke="#7c3aed" strokeWidth="1" />

        {/* Neck */}
        <rect x="98" y="124" width="24" height="14" rx="5" fill="#0f0720" stroke="#2d1b69" strokeWidth="1" />

        {/* Body */}
        <rect x="42" y="138" width="136" height="108" rx="18" fill="#0f0720" stroke="#7c3aed" strokeWidth="1.5" />

        {/* Chest panel */}
        <rect x="58" y="154" width="104" height="76" rx="12" fill="#080414" />
        <rect x="63" y="159" width="94" height="66" rx="9" fill="#09051a" />

        {/* Status indicators */}
        <circle cx="81" cy="172" r="8" fill="#065f46" />
        <circle cx="81" cy="172" r="5" fill="#10b981" />
        <circle cx="81" cy="172" r="2.5" fill="#34d399" opacity="0.8" />

        <circle cx="110" cy="172" r="8" fill="#2d1b69" />
        <circle cx="110" cy="172" r="5" fill="#7c3aed" />
        <circle cx="110" cy="172" r="2.5" fill="#a78bfa" opacity="0.8" />

        <circle cx="139" cy="172" r="8" fill="#78350f" />
        <circle cx="139" cy="172" r="5" fill="#f59e0b" />
        <circle cx="139" cy="172" r="2.5" fill="#fcd34d" opacity="0.8" />

        {/* Progress bars */}
        <rect x="68" y="188" width="84" height="5" rx="2.5" fill="#2d1b69" />
        <rect x="68" y="188" width="64" height="5" rx="2.5" fill="#7c3aed" />

        <rect x="68" y="199" width="84" height="5" rx="2.5" fill="#2d1b69" />
        <rect x="68" y="199" width="48" height="5" rx="2.5" fill="#a78bfa" />

        <rect x="68" y="210" width="84" height="5" rx="2.5" fill="#2d1b69" />
        <rect x="68" y="210" width="76" height="5" rx="2.5" fill="#c084fc" />

        {/* Arms */}
        <rect x="8"   y="144" width="30" height="78" rx="15" fill="#0f0720" stroke="#7c3aed" strokeWidth="1.5" />
        <rect x="182" y="144" width="30" height="78" rx="15" fill="#0f0720" stroke="#7c3aed" strokeWidth="1.5" />

        {/* Hands */}
        <circle cx="23"  cy="227" r="15" fill="#0f0720" stroke="#7c3aed" strokeWidth="1.5" />
        <circle cx="197" cy="227" r="15" fill="#0f0720" stroke="#7c3aed" strokeWidth="1.5" />

        {/* Legs */}
        <rect x="64"  y="246" width="36" height="40" rx="13" fill="#0f0720" stroke="#7c3aed" strokeWidth="1.5" />
        <rect x="120" y="246" width="36" height="40" rx="13" fill="#0f0720" stroke="#7c3aed" strokeWidth="1.5" />

        {/* Feet */}
        <rect x="57"  y="278" width="46" height="12" rx="6" fill="#2d1b69" />
        <rect x="117" y="278" width="46" height="12" rx="6" fill="#2d1b69" />
      </svg>
    </div>
  );
}

// ── Icons ───────────────────────────────────────────────────────────────────

const EmailIcon = () => (
  <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
  </svg>
);

const WhatsAppIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="currentColor">
    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
  </svg>
);

const WebFormIcon = () => (
  <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
  </svg>
);

function Spinner() {
  return (
    <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}

// ── Input helper ─────────────────────────────────────────────────────────────

const inp = () =>
  `w-full bg-purple-950/40 border border-purple-800/50 rounded-xl px-4 py-3 text-white
   placeholder:text-purple-700 focus:outline-none transition-all text-sm
   focus:border-violet-500 focus:ring-1 focus:ring-violet-500/30`;

// ── Success Card ─────────────────────────────────────────────────────────────

function SuccessCard({ title, subtitle, ticketId, buttonLabel, onReset }) {
  return (
    <div className="text-center py-6 space-y-5">
      <div className="flex justify-center">
        <div className="relative">
          <div className="absolute inset-0 bg-violet-500/20 rounded-full animate-ping" />
          <div className="relative w-16 h-16 bg-gradient-to-br from-violet-500 to-purple-600 rounded-full flex items-center justify-center shadow-lg shadow-violet-500/30">
            <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
            </svg>
          </div>
        </div>
      </div>
      <div>
        <h3 className="text-xl font-bold text-white">{title}</h3>
        <p className="text-purple-400 text-sm mt-1">{subtitle}</p>
      </div>
      <div className="bg-purple-950/60 border border-purple-800/40 rounded-xl p-4 text-left">
        <p className="text-xs text-purple-600 mb-1.5">Ticket Reference</p>
        <p className="font-mono font-bold text-lg text-violet-400">{ticketId}</p>
        <p className="text-xs text-purple-600 mt-1.5">Save this ID to track your ticket status.</p>
      </div>
      <button
        onClick={onReset}
        className="bg-purple-800/60 hover:bg-purple-700/60 text-white px-6 py-2.5 rounded-xl font-semibold text-sm transition-all border border-purple-700/40"
      >
        {buttonLabel}
      </button>
    </div>
  );
}

// ── Email Form ────────────────────────────────────────────────────────────────

function EmailForm() {
  const [form, setForm] = useState({ name: '', email: '', subject: '', message: '' });
  const [st, setSt] = useState('idle');
  const [ticket, setTicket] = useState('');
  const [err, setErr] = useState('');
  const set = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setSt('submitting');
    setErr('');
    try {
      const res = await fetch('/api/send-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to send email');
      setTicket(data.ticket_id || genTicket('EMAIL'));
      setSt('success');
    } catch (ex) {
      setErr(ex.message);
      setSt('error');
    }
  };

  if (st === 'success') {
    return (
      <SuccessCard
        title="Email Sent Successfully!"
        subtitle="We'll respond to your email shortly."
        ticketId={ticket}
        buttonLabel="Send Another Email"
        onReset={() => { setSt('idle'); setForm({ name: '', email: '', subject: '', message: '' }); }}
      />
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-purple-400 mb-1.5">Full Name *</label>
          <input required value={form.name} onChange={set('name')} placeholder="Your name" className={inp()} />
        </div>
        <div>
          <label className="block text-xs font-medium text-purple-400 mb-1.5">Email Address *</label>
          <input required type="email" value={form.email} onChange={set('email')} placeholder="you@example.com" className={inp()} />
        </div>
      </div>
      <div>
        <label className="block text-xs font-medium text-purple-400 mb-1.5">Subject *</label>
        <input required value={form.subject} onChange={set('subject')} placeholder="Brief description" className={inp()} />
      </div>
      <div>
        <label className="block text-xs font-medium text-purple-400 mb-1.5">Message *</label>
        <textarea required rows={4} value={form.message} onChange={set('message')}
          placeholder="Describe your issue in detail..." className={`${inp()} resize-none`} />
      </div>
      {st === 'error' && (
        <p className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</p>
      )}
      <button type="submit" disabled={st === 'submitting'}
        className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-violet-600 to-purple-600
                   text-white py-3 rounded-xl font-semibold text-sm hover:from-violet-500 hover:to-purple-500
                   transition-all shadow-lg shadow-violet-500/25 disabled:opacity-50 disabled:cursor-not-allowed">
        {st === 'submitting' ? <><Spinner /> Sending...</> : 'Send Email →'}
      </button>
    </form>
  );
}

// ── WhatsApp Form ─────────────────────────────────────────────────────────────

function WhatsAppForm() {
  const [form, setForm] = useState({ name: '', phone: '', message: '' });
  const [st, setSt] = useState('idle');
  const [ticket, setTicket] = useState('');
  const [err, setErr] = useState('');
  const set = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setSt('submitting');
    setErr('');
    try {
      const res = await fetch('/api/send-whatsapp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to send message');
      setTicket(data.ticket_id || genTicket('WA'));
      setSt('success');
    } catch (ex) {
      setErr(ex.message);
      setSt('error');
    }
  };

  if (st === 'success') {
    return (
      <SuccessCard
        title="Message Sent on WhatsApp!"
        subtitle="Our agent will respond to you shortly."
        ticketId={ticket}
        buttonLabel="Send Another Message"
        onReset={() => { setSt('idle'); setForm({ name: '', phone: '', message: '' }); }}
      />
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-purple-400 mb-1.5">Full Name *</label>
          <input required value={form.name} onChange={set('name')} placeholder="Your name" className={inp()} />
        </div>
        <div>
          <label className="block text-xs font-medium text-purple-400 mb-1.5">WhatsApp Number *</label>
          <input required value={form.phone} onChange={set('phone')} placeholder="+92 300 1234567" className={inp()} />
        </div>
      </div>
      <div>
        <label className="block text-xs font-medium text-purple-400 mb-1.5">Message *</label>
        <textarea required rows={4} value={form.message} onChange={set('message')}
          placeholder="Type your message here..." className={`${inp()} resize-none`} />
      </div>
      {st === 'error' && (
        <p className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</p>
      )}
      <button type="submit" disabled={st === 'submitting'}
        className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-green-600 to-emerald-600
                   text-white py-3 rounded-xl font-semibold text-sm hover:from-green-500 hover:to-emerald-500
                   transition-all shadow-lg shadow-green-500/20 disabled:opacity-50 disabled:cursor-not-allowed">
        {st === 'submitting' ? <><Spinner /> Sending...</> : 'Send WhatsApp Message →'}
      </button>
      <p className="text-xs text-purple-700 text-center">Include country code · e.g. +92 Pakistan</p>
    </form>
  );
}

// ── Status Modal ──────────────────────────────────────────────────────────────

function StatusModal({ onClose }) {
  const [ticketId, setTicketId] = useState('');
  const [result, setResult] = useState(null);
  const [st, setSt] = useState('idle');
  const [err, setErr] = useState('');

  const check = async (e) => {
    e.preventDefault();
    if (!ticketId.trim()) return;
    setSt('loading');
    setErr('');
    setResult(null);
    try {
      const res = await fetch(`/support/ticket/${encodeURIComponent(ticketId.trim())}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Ticket not found');
      setResult(data);
      setSt('done');
    } catch (ex) {
      setErr(ex.message);
      setSt('error');
    }
  };

  const STATUS_COLORS = {
    open:        'text-violet-400 bg-violet-500/10 border-violet-500/30',
    in_progress: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
    resolved:    'text-green-400 bg-green-500/10 border-green-500/30',
    escalated:   'text-red-400 bg-red-500/10 border-red-500/30',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="bg-purple-950/95 border border-purple-800/50 rounded-2xl p-6 w-full max-w-md shadow-2xl shadow-violet-900/40">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-bold text-white">Check Ticket Status</h3>
          <button onClick={onClose} className="text-purple-500 hover:text-white transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <form onSubmit={check} className="space-y-3">
          <input value={ticketId} onChange={(e) => setTicketId(e.target.value)}
            placeholder="e.g. WEB-ABC123 or WA-XYZ456" className={inp()} />
          <button type="submit" disabled={st === 'loading'}
            className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-violet-600 to-purple-600
                       text-white py-3 rounded-xl font-semibold text-sm hover:from-violet-500 hover:to-purple-500
                       transition-all disabled:opacity-50">
            {st === 'loading' ? <><Spinner /> Checking...</> : 'Check Status'}
          </button>
        </form>
        {st === 'error' && (
          <p className="mt-3 text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</p>
        )}
        {result && (
          <div className="mt-4 space-y-3">
            <div className={`border rounded-xl px-4 py-3 ${STATUS_COLORS[result.status] || STATUS_COLORS.open}`}>
              <p className="text-xs font-medium opacity-70 mb-1">Status</p>
              <p className="font-bold capitalize">{(result.status || 'open').replace('_', ' ')}</p>
            </div>
            {result.subject && (
              <div className="bg-purple-900/30 border border-purple-800/30 rounded-xl px-4 py-3">
                <p className="text-xs text-purple-500 mb-1">Subject</p>
                <p className="text-white text-sm font-medium">{result.subject}</p>
              </div>
            )}
            {result.estimated_response_time && (
              <div className="bg-purple-900/30 border border-purple-800/30 rounded-xl px-4 py-3">
                <p className="text-xs text-purple-500 mb-1">Estimated Response</p>
                <p className="text-violet-400 text-sm font-medium">{result.estimated_response_time}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Web Form Modal ────────────────────────────────────────────────────────────

function WebFormModal({ onClose }) {
  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <button onClick={onClose}
        className="fixed top-4 right-4 z-[60] w-10 h-10 bg-purple-900 hover:bg-purple-800 border border-purple-700
                   rounded-full flex items-center justify-center text-purple-300 hover:text-white transition-all shadow-lg">
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
      <SupportForm apiEndpoint="/support/submit" />
    </div>
  );
}

// ── Channel Card ──────────────────────────────────────────────────────────────

function ChannelCard({ id, icon: Icon, title, description, isActive, onClick, accentColor }) {
  const colors = {
    violet: { border: 'border-violet-500', bg: 'bg-violet-500/10', icon: 'text-violet-400', ring: 'ring-violet-500/20' },
    green:  { border: 'border-green-500',  bg: 'bg-green-500/10',  icon: 'text-green-400',  ring: 'ring-green-500/20' },
    purple: { border: 'border-purple-500', bg: 'bg-purple-500/10', icon: 'text-purple-400', ring: 'ring-purple-500/20' },
  };
  const c = colors[accentColor] || colors.violet;

  return (
    <button onClick={onClick}
      className={`flex flex-col items-center gap-3 p-5 rounded-2xl border transition-all duration-200 w-full
        ${isActive
          ? `${c.border} ${c.bg} ring-2 ${c.ring} shadow-lg`
          : 'border-purple-900/50 bg-purple-950/30 hover:border-purple-700/60 hover:bg-purple-900/30'
        }`}>
      <div className={`${isActive ? c.icon : 'text-purple-500'} transition-colors`}>
        <Icon />
      </div>
      <div className="text-center">
        <p className={`font-semibold text-sm ${isActive ? 'text-white' : 'text-purple-300'}`}>{title}</p>
        <p className="text-xs text-purple-600 mt-1 leading-relaxed">{description}</p>
      </div>
    </button>
  );
}

// ── Main Landing Page ─────────────────────────────────────────────────────────

export default function LandingPage() {
  const [channel, setChannel] = useState(null);
  const [showStatus, setShowStatus] = useState(false);
  const [webformOpen, setWebformOpen] = useState(false);
  const channelRef = useRef(null);

  const scrollToChannels = () => {
    channelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const selectChannel = (id) => {
    if (id === 'webform') { setWebformOpen(true); return; }
    setChannel(channel === id ? null : id);
    setTimeout(() => channelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 100);
  };

  const channels = [
    { id: 'email',    icon: EmailIcon,    title: 'Email',    description: 'Send us an email for detailed support', accentColor: 'violet' },
    { id: 'whatsapp', icon: WhatsAppIcon, title: 'WhatsApp', description: 'Chat instantly on WhatsApp',            accentColor: 'green'  },
    { id: 'webform',  icon: WebFormIcon,  title: 'Web Form', description: 'Fill our form for structured support',  accentColor: 'purple' },
  ];

  return (
    <>
      <style>{`
        @keyframes floatUp   { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-12px)} }
        @keyframes fadeSlide { from{opacity:0;transform:translateY(18px)} to{opacity:1;transform:translateY(0)} }
        @keyframes glow      { 0%,100%{opacity:0.4} 50%{opacity:0.7} }
        .float-anim  { animation: floatUp 4.5s ease-in-out infinite; }
        .fade-slide  { animation: fadeSlide 0.4s cubic-bezier(.16,1,.3,1) both; }
        .glow-pulse  { animation: glow 3s ease-in-out infinite; }
      `}</style>

      <div className="min-h-screen" style={{ background: 'linear-gradient(150deg, #0d0718 0%, #100520 45%, #0a0315 100%)' }}>

        {/* ═══ NAVBAR ═══ */}
        <nav className="fixed top-0 left-0 right-0 z-40 border-b border-purple-900/30 backdrop-blur-xl"
          style={{ background: 'rgba(13, 7, 24, 0.88)' }}>
          <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-600 to-purple-700 flex items-center justify-center shadow-lg shadow-violet-500/30">
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <span className="font-bold text-white text-sm">NimbusFlow</span>
              <span className="font-bold text-violet-400 text-sm">AI</span>
            </div>

            {/* Nav links */}
            <div className="hidden md:flex items-center gap-7">
              {[
                { label: 'Home',         onClick: () => window.scrollTo({ top: 0, behavior: 'smooth' }) },
                { label: 'Get Help',     onClick: scrollToChannels },
                { label: 'Check Status', onClick: () => setShowStatus(true) },
                { label: 'Dashboard',    href: '/admin' },
              ].map((item) =>
                item.href ? (
                  <a key={item.label} href={item.href}
                    className="text-sm text-purple-400 hover:text-white transition-colors font-medium">
                    {item.label}
                  </a>
                ) : (
                  <button key={item.label} onClick={item.onClick}
                    className="text-sm text-purple-400 hover:text-white transition-colors font-medium">
                    {item.label}
                  </button>
                )
              )}
            </div>

            {/* CTA */}
            <button onClick={scrollToChannels}
              className="bg-gradient-to-r from-violet-600 to-purple-700 text-white px-4 py-2
                         rounded-xl text-sm font-semibold hover:from-violet-500 hover:to-purple-600
                         transition-all shadow-lg shadow-violet-500/25">
              Get Support
            </button>
          </div>
        </nav>

        {/* ═══ HERO ═══ */}
        <section className="pt-16 min-h-screen flex items-center relative overflow-hidden">
          {/* Background blobs */}
          <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-violet-700/8 rounded-full blur-3xl pointer-events-none glow-pulse" />
          <div className="absolute top-1/4 left-1/4 w-72 h-72 bg-purple-600/6 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute bottom-1/3 right-1/4 w-64 h-64 bg-fuchsia-700/5 rounded-full blur-3xl pointer-events-none" />

          <div className="max-w-6xl mx-auto px-8 py-20 w-full">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">

              {/* ── Left: Text ── */}
              <div className="space-y-7 text-center lg:text-left">
                {/* Status badge */}
                <div className="inline-flex items-center gap-2 bg-violet-500/10 border border-violet-500/25
                               rounded-full px-4 py-1.5 backdrop-blur-sm">
                  <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                  <span className="text-xs font-medium text-violet-300 tracking-wide">
                    AI-Powered · Global Support · 24/7 Active
                  </span>
                </div>

                {/* Headline */}
                <h1 className="text-5xl lg:text-[3.4rem] font-extrabold text-white leading-[1.1] tracking-tight">
                  Your 24/7
                  <br />
                  <span className="bg-gradient-to-r from-violet-400 via-purple-400 to-fuchsia-400 bg-clip-text text-transparent">
                    Customer Success
                  </span>
                  <br />
                  Partner
                </h1>

                {/* Subtitle */}
                <p className="text-purple-300/80 text-lg leading-relaxed max-w-md mx-auto lg:mx-0">
                  Get instant, intelligent support across email, WhatsApp, and web —
                  powered by AI that never sleeps.
                </p>

                {/* CTA Buttons */}
                <div className="flex flex-wrap gap-3 pt-1 justify-center lg:justify-start">
                  <button onClick={scrollToChannels}
                    className="flex items-center gap-2 bg-gradient-to-r from-violet-600 to-purple-700
                               text-white px-7 py-3.5 rounded-xl font-semibold text-sm
                               hover:from-violet-500 hover:to-purple-600 transition-all
                               shadow-xl shadow-violet-500/30">
                    Get Support Now
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                    </svg>
                  </button>
                  <button onClick={() => setShowStatus(true)}
                    className="flex items-center gap-2 border border-purple-700/60 text-purple-300
                               px-7 py-3.5 rounded-xl font-semibold text-sm
                               hover:border-purple-500 hover:text-white transition-all backdrop-blur-sm">
                    Check Ticket Status
                  </button>
                </div>

                {/* Stats */}
                <div className="flex gap-8 pt-3 border-t border-purple-900/60 justify-center lg:justify-start">
                  {[
                    { value: '< 5 min', label: 'Avg Response' },
                    { value: '24 / 7',  label: 'Availability' },
                    { value: '3',       label: 'Channels' },
                  ].map((s) => (
                    <div key={s.label}>
                      <p className="text-xl font-bold text-white">{s.value}</p>
                      <p className="text-xs text-purple-600 mt-0.5">{s.label}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* ── Right: Robot ── */}
              <div className="flex justify-center">
                <div className="float-anim">
                  <RobotIllustration />
                </div>
              </div>
            </div>
          </div>

          {/* Scroll indicator */}
          <button onClick={scrollToChannels}
            className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1
                       text-purple-700 hover:text-purple-500 transition-colors">
            <span className="text-xs font-medium">Scroll to get help</span>
            <svg className="w-5 h-5 animate-bounce" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </section>

        {/* ═══ CHANNEL SECTION ═══ */}
        <section ref={channelRef} className="py-24"
          style={{ background: 'rgba(124, 58, 237, 0.03)' }}>
          <div className="max-w-3xl mx-auto px-6">

            {/* Section header */}
            <div className="text-center mb-12">
              <div className="inline-flex items-center gap-2 bg-violet-500/10 border border-violet-500/20
                             rounded-full px-4 py-1.5 mb-4">
                <span className="text-xs font-medium text-violet-400">Choose Your Channel</span>
              </div>
              <h2 className="text-3xl font-bold text-white mb-3">Contact Our AI Assistant</h2>
              <p className="text-purple-400/70 text-sm max-w-md mx-auto">
                Reach us through your preferred channel. Our AI agent is available 24/7 to assist you.
              </p>
            </div>

            {/* Channel cards */}
            <div className="grid grid-cols-3 gap-4 mb-8">
              {channels.map((ch) => (
                <ChannelCard key={ch.id} {...ch}
                  isActive={channel === ch.id}
                  onClick={() => selectChannel(ch.id)} />
              ))}
            </div>

            {/* Inline form */}
            {channel && (
              <div key={channel}
                className="bg-purple-950/50 border border-purple-800/40 rounded-2xl p-7
                           backdrop-blur-sm shadow-xl shadow-violet-900/20 fade-slide">
                <div className="flex items-center justify-between mb-5">
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full animate-pulse ${
                      channel === 'email' ? 'bg-violet-400' : 'bg-green-400'
                    }`} />
                    <h3 className="font-semibold text-white text-sm">
                      {channel === 'email' ? 'Send us an Email' : 'Send a WhatsApp Message'}
                    </h3>
                  </div>
                  <button onClick={() => setChannel(null)}
                    className="text-purple-600 hover:text-purple-300 transition-colors">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                {channel === 'email'    && <EmailForm />}
                {channel === 'whatsapp' && <WhatsAppForm />}
              </div>
            )}
          </div>
        </section>

        {/* ═══ FOOTER ═══ */}
        <footer className="border-t border-purple-900/40 py-8">
          <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-violet-600 to-purple-700 flex items-center justify-center">
                <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <span className="text-xs text-purple-700">NimbusFlow AI · Customer Success Platform</span>
            </div>
            <div className="flex items-center gap-4">
              <a href="/admin" className="text-xs text-purple-700 hover:text-purple-400 transition-colors">Dashboard</a>
              <button onClick={() => setShowStatus(true)} className="text-xs text-purple-700 hover:text-purple-400 transition-colors">
                Check Status
              </button>
            </div>
          </div>
        </footer>
      </div>

      {/* ═══ MODALS ═══ */}
      {showStatus  && <StatusModal onClose={() => setShowStatus(false)} />}
      {webformOpen && <WebFormModal onClose={() => setWebformOpen(false)} />}
    </>
  );
}
