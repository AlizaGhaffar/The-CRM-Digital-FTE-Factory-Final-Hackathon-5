/**
 * frontend/components/EscalationsQueue.jsx
 *
 * NimbusFlow — Escalations Queue
 * Admin view of tickets awaiting human review.
 * Supports dark/light mode, filtering, expandable detail rows,
 * and quick-action buttons (Assign to Me, Respond as Human, Send Back to AI).
 *
 * API endpoints used:
 *   GET  /api/escalations                         — escalated ticket queue
 *   POST /support/ticket/{id}/assign              — assign ticket to current agent
 *   POST /support/ticket/{id}/respond-human       — mark as human responding
 *   POST /support/ticket/{id}/return-to-ai        — send back to AI
 *
 * Usage (Next.js):
 *   import EscalationsQueue from '@/components/EscalationsQueue';
 *   export default function EscalationsPage() {
 *     return <EscalationsQueue apiBase="" agentName="Alex" />;
 *   }
 *
 * Requirements: React 18+, Tailwind CSS
 */

import { useState, useEffect, useCallback, useRef } from 'react';

// ── Mock data ──────────────────────────────────────────────────────────────

const MOCK_ESCALATIONS = [
  {
    ticket_id:          'a1b2c3d4-5e6f-7890-bcde-f01234567890',
    customer_name:      'Alice Nguyen',
    customer_email:     'alice@corp.com',
    channel:            'email',
    priority:           'high',
    escalation_reason:  'billing_dispute',
    wait_since:         new Date(Date.now() - 52 * 60000).toISOString(),
    last_customer_msg:  'I was charged twice for my subscription this month and need an immediate refund. This is completely unacceptable.',
    ai_response:        'Thank you for reaching out. I understand your concern about the billing. Our billing team processes refunds within 5-7 business days…',
    why_escalated:      'Customer explicitly requested a human agent and used high-frustration language. Confidence score: 0.31.',
  },
  {
    ticket_id:          'b2c3d4e5-6f70-8901-cdef-012345678901',
    customer_name:      'Bob Martinez',
    customer_email:     'bob@startup.io',
    channel:            'whatsapp',
    priority:           'high',
    escalation_reason:  'technical_complexity',
    wait_since:         new Date(Date.now() - 18 * 60000).toISOString(),
    last_customer_msg:  "Our webhook is failing silently — no 4xx, no 5xx, just no payload delivery. We've checked firewall rules.",
    ai_response:        'Webhook delivery issues can be caused by several factors. Please ensure your endpoint returns a 200 status within 5 seconds…',
    why_escalated:      'Multi-step debugging required beyond AI capability. Three clarification loops without resolution.',
  },
  {
    ticket_id:          'c3d4e5f6-7081-9012-def0-123456789012',
    customer_name:      'Carol Li',
    customer_email:     'carol@tech.dev',
    channel:            'web_form',
    priority:           'medium',
    escalation_reason:  'policy_exception',
    wait_since:         new Date(Date.now() - 35 * 60000).toISOString(),
    last_customer_msg:  "We're a non-profit — can you waive the setup fee? We have a tight budget and really want to use NimbusFlow.",
    ai_response:        'We appreciate your interest in NimbusFlow. Our pricing plans are designed to accommodate various needs…',
    why_escalated:      'Request requires policy exception authority not granted to AI. Escalation triggered by keyword "non-profit waiver".',
  },
  {
    ticket_id:          'd4e5f607-8192-0123-ef01-234567890123',
    customer_name:      'Dave Kim',
    customer_email:     'dave@bigco.com',
    channel:            'email',
    priority:           'high',
    escalation_reason:  'legal_compliance',
    wait_since:         new Date(Date.now() - 67 * 60000).toISOString(),
    last_customer_msg:  'We need a data processing agreement signed before we can go live. Our legal team requires this for GDPR compliance.',
    ai_response:        'Data protection is important to us. I can point you to our Privacy Policy and Data Processing Addendum available on our website…',
    why_escalated:      'Legal document execution requires human authority. DPA signing is outside AI scope.',
  },
  {
    ticket_id:          'e5f60718-9203-1234-f012-345678901234',
    customer_name:      'Eve Johnson',
    customer_email:     'eve@design.co',
    channel:            'whatsapp',
    priority:           'medium',
    escalation_reason:  'sentiment_negative',
    wait_since:         new Date(Date.now() - 41 * 60000).toISOString(),
    last_customer_msg:  "Honestly at this point I'm considering cancelling. Every week there's a new bug. I'm just exhausted.",
    ai_response:        "I'm really sorry to hear you're feeling frustrated. Your experience matters to us and I'd like to help resolve this…",
    why_escalated:      'Sentiment score 0.11 — extreme dissatisfaction detected. Churn risk flagged. Human empathy required.',
  },
  {
    ticket_id:          'f6071829-0314-2345-0123-456789012345',
    customer_name:      'Frank Osei',
    customer_email:     'frank@media.io',
    channel:            'web_form',
    priority:           'low',
    escalation_reason:  'repeated_contact',
    wait_since:         new Date(Date.now() - 14 * 60000).toISOString(),
    last_customer_msg:  "This is the 4th time I'm asking about the CSV export bug. Is anyone actually reading these?",
    ai_response:        "Thank you for your patience, Frank. I've reviewed your previous tickets regarding the CSV export issue…",
    why_escalated:      'Same issue reported 4 times without resolution. Repeated-contact threshold (3) exceeded.',
  },
  {
    ticket_id:          '07182930-1425-3456-1234-567890123456',
    customer_name:      'Grace Patel',
    customer_email:     'grace@fintech.co',
    channel:            'email',
    priority:           'high',
    escalation_reason:  'account_security',
    wait_since:         new Date(Date.now() - 29 * 60000).toISOString(),
    last_customer_msg:  "I see login activity from an IP I don't recognise in Germany. I'm in Canada. Please help, I'm worried.",
    ai_response:        'Account security is our top priority. Please change your password immediately using the link below…',
    why_escalated:      'Potential account compromise requires immediate human investigation and manual session revocation.',
  },
  {
    ticket_id:          '18293041-2536-4567-2345-678901234567',
    customer_name:      'Hiro Tanaka',
    customer_email:     'hiro@saas.jp',
    channel:            'whatsapp',
    priority:           'medium',
    escalation_reason:  'technical_complexity',
    wait_since:         new Date(Date.now() - 9 * 60000).toISOString(),
    last_customer_msg:  'Our SSO setup with Okta is almost working but the SAML assertion keeps failing attribute mapping.',
    ai_response:        'SAML attribute mapping issues are commonly caused by mismatched attribute names. In Okta, navigate to the app settings…',
    why_escalated:      'Advanced SAML/SSO configuration exceeded AI knowledge boundary. Specialist required.',
  },
];

// ── Config ─────────────────────────────────────────────────────────────────

const PRIORITY_CFG = {
  high:   { label: 'High',   light: 'bg-red-100 text-red-700 ring-red-200',     dark: 'bg-red-900/40 text-red-300 ring-red-700',     dot: 'bg-red-500' },
  medium: { label: 'Medium', light: 'bg-amber-100 text-amber-700 ring-amber-200', dark: 'bg-amber-900/40 text-amber-300 ring-amber-700', dot: 'bg-amber-400' },
  low:    { label: 'Low',    light: 'bg-green-100 text-green-700 ring-green-200', dark: 'bg-green-900/40 text-green-300 ring-green-700', dot: 'bg-green-500' },
};

const REASON_CFG = {
  billing_dispute:      { label: 'Billing Dispute',     color: 'text-red-500',    bg: 'bg-red-50 dark:bg-red-900/20' },
  technical_complexity: { label: 'Technical Complexity', color: 'text-blue-500',   bg: 'bg-blue-50 dark:bg-blue-900/20' },
  policy_exception:     { label: 'Policy Exception',    color: 'text-purple-500', bg: 'bg-purple-50 dark:bg-purple-900/20' },
  legal_compliance:     { label: 'Legal / Compliance',  color: 'text-orange-500', bg: 'bg-orange-50 dark:bg-orange-900/20' },
  sentiment_negative:   { label: 'Negative Sentiment',  color: 'text-pink-500',   bg: 'bg-pink-50 dark:bg-pink-900/20' },
  repeated_contact:     { label: 'Repeated Contact',    color: 'text-amber-500',  bg: 'bg-amber-50 dark:bg-amber-900/20' },
  account_security:     { label: 'Account Security',    color: 'text-red-600',    bg: 'bg-red-50 dark:bg-red-900/20' },
};

const CHANNEL_COLOR = {
  email:    { light: 'text-blue-600 bg-blue-100',    dark: 'text-blue-400 bg-blue-900/40' },
  whatsapp: { light: 'text-green-600 bg-green-100',  dark: 'text-green-400 bg-green-900/40' },
  web_form: { light: 'text-purple-600 bg-purple-100', dark: 'text-purple-400 bg-purple-900/40' },
};

// ── Icons ──────────────────────────────────────────────────────────────────

function EmailIcon({ className }) {
  return <svg className={className} viewBox="0 0 20 20" fill="currentColor"><path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z"/><path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z"/></svg>;
}
function WhatsAppIcon({ className }) {
  return <svg className={className} viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.127.558 4.126 1.532 5.862L.072 23.928l6.243-1.636A11.935 11.935 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.818 9.818 0 01-5.009-1.374l-.36-.213-3.708.972.989-3.617-.233-.371A9.818 9.818 0 1112 21.818z"/></svg>;
}
function WebIcon({ className }) {
  return <svg className={className} viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M4.083 9h1.946c.089-1.546.383-2.97.837-4.118A6.004 6.004 0 004.083 9zM10 2a8 8 0 100 16A8 8 0 0010 2zm0 2c-.076 0-.232.032-.465.262-.238.234-.497.623-.737 1.182-.389.907-.673 2.142-.766 3.556h3.936c-.093-1.414-.377-2.649-.766-3.556-.24-.56-.5-.948-.737-1.182C10.232 4.032 10.076 4 10 4zm3.971 5c-.089-1.546-.383-2.97-.837-4.118A6.004 6.004 0 0115.917 9h-1.946zm-2.003 2H8.032c.093 1.414.377 2.649.766 3.556.24.56.5.948.737 1.182.233.23.389.262.465.262.076 0 .232-.032.465-.262.238-.234.498-.623.737-1.182.389-.907.673-2.142.766-3.556zm1.166 4.118c.454-1.147.748-2.572.837-4.118h1.946a6.004 6.004 0 01-2.783 4.118zm-6.268 0C6.412 13.97 6.118 12.546 6.03 11H4.083a6.004 6.004 0 002.783 4.118z" clipRule="evenodd"/></svg>;
}
function ChevronIcon({ className, open }) {
  return (
    <svg className={`${className} transition-transform duration-200 ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  );
}
function ClockIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>;
}
function UserIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>;
}
function MoonIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>;
}
function SunIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>;
}
function BotIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17H3a2 2 0 01-2-2V5a2 2 0 012-2h16a2 2 0 012 2v10a2 2 0 01-2 2h-2"/></svg>;
}
function AlertIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>;
}

const CHANNEL_ICON = { email: EmailIcon, whatsapp: WhatsAppIcon, web_form: WebIcon };

// ── Helpers ─────────────────────────────────────────────────────────────────

function waitMinutes(iso) {
  return Math.floor((Date.now() - new Date(iso)) / 60000);
}

function formatWait(iso) {
  const mins = waitMinutes(iso);
  if (mins < 60)  return `${mins}m`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m`;
}

function truncateId(id) {
  return id ? id.slice(0, 8) + '…' : '—';
}

// ── Priority badge ──────────────────────────────────────────────────────────

function PriorityBadge({ priority, dark }) {
  const cfg  = PRIORITY_CFG[priority] || PRIORITY_CFG.medium;
  const mode = dark ? 'dark' : 'light';
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${cfg[mode]}`}>
      <span className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

// ── Wait time badge (red if > 30 min) ──────────────────────────────────────

function WaitBadge({ iso, dark }) {
  const mins    = waitMinutes(iso);
  const urgent  = mins > 30;
  return (
    <span className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold ${
      urgent
        ? (dark ? 'bg-red-900/50 text-red-300 ring-1 ring-red-700' : 'bg-red-100 text-red-700 ring-1 ring-red-200')
        : (dark ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-600')
    }`}>
      <ClockIcon className={`h-3 w-3 ${urgent ? 'animate-pulse' : ''}`} />
      {formatWait(iso)}
    </span>
  );
}

// ── Expanded detail panel ───────────────────────────────────────────────────

function DetailPanel({ ticket, dark, onAction, actionLoading }) {
  const muted = dark ? 'text-gray-400' : 'text-gray-500';
  const text  = dark ? 'text-gray-100' : 'text-gray-900';
  const bg    = dark ? 'bg-gray-700/40' : 'bg-gray-50';
  const border = dark ? 'border-gray-600' : 'border-gray-200';

  return (
    <div className={`px-4 pb-4 pt-2 ${dark ? 'bg-gray-800/50' : 'bg-gray-50/80'}`}>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">

        {/* Last customer message */}
        <div className={`rounded-xl border p-3 space-y-1.5 ${dark ? 'border-gray-600 bg-gray-800' : 'border-gray-200 bg-white'}`}>
          <p className={`text-xs font-semibold uppercase tracking-wide ${muted}`}>
            Last Customer Message
          </p>
          <div className={`flex items-start gap-2`}>
            <UserIcon className={`h-3.5 w-3.5 mt-0.5 flex-shrink-0 ${dark ? 'text-blue-400' : 'text-blue-600'}`} />
            <p className={`text-xs leading-relaxed ${text}`}>
              "{ticket.last_customer_msg}"
            </p>
          </div>
        </div>

        {/* AI's attempted response */}
        <div className={`rounded-xl border p-3 space-y-1.5 ${dark ? 'border-gray-600 bg-gray-800' : 'border-gray-200 bg-white'}`}>
          <p className={`text-xs font-semibold uppercase tracking-wide ${muted}`}>
            AI's Attempted Response
          </p>
          <div className="flex items-start gap-2">
            <BotIcon className={`h-3.5 w-3.5 mt-0.5 flex-shrink-0 ${dark ? 'text-purple-400' : 'text-purple-600'}`} />
            <p className={`text-xs leading-relaxed ${dark ? 'text-gray-300' : 'text-gray-600'}`}>
              "{ticket.ai_response}"
            </p>
          </div>
        </div>

        {/* Why AI escalated */}
        <div className={`rounded-xl border p-3 space-y-1.5 ${dark ? 'border-amber-700/50 bg-amber-900/20' : 'border-amber-200 bg-amber-50'}`}>
          <p className={`text-xs font-semibold uppercase tracking-wide ${dark ? 'text-amber-400' : 'text-amber-600'}`}>
            Why AI Escalated
          </p>
          <div className="flex items-start gap-2">
            <AlertIcon className={`h-3.5 w-3.5 mt-0.5 flex-shrink-0 ${dark ? 'text-amber-400' : 'text-amber-500'}`} />
            <p className={`text-xs leading-relaxed ${dark ? 'text-amber-200' : 'text-amber-800'}`}>
              {ticket.why_escalated}
            </p>
          </div>
        </div>
      </div>

      {/* Quick actions */}
      <div className="flex flex-wrap items-center gap-2 mt-3">
        <span className={`text-xs font-semibold uppercase tracking-wide ${muted} mr-1`}>Quick Actions:</span>

        <button
          onClick={() => onAction(ticket.ticket_id, 'assign')}
          disabled={!!actionLoading}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold border transition-colors disabled:opacity-50 ${
            dark
              ? 'border-blue-600 bg-blue-900/30 text-blue-300 hover:bg-blue-800/50'
              : 'border-blue-300 bg-blue-50 text-blue-700 hover:bg-blue-100'
          }`}
        >
          <UserIcon className="h-3.5 w-3.5" />
          {actionLoading === 'assign' ? 'Assigning…' : 'Assign to Me'}
        </button>

        <button
          onClick={() => onAction(ticket.ticket_id, 'respond-human')}
          disabled={!!actionLoading}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold border transition-colors disabled:opacity-50 ${
            dark
              ? 'border-green-600 bg-green-900/30 text-green-300 hover:bg-green-800/50'
              : 'border-green-300 bg-green-50 text-green-700 hover:bg-green-100'
          }`}
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/>
          </svg>
          {actionLoading === 'respond-human' ? 'Opening…' : 'Respond as Human'}
        </button>

        <button
          onClick={() => onAction(ticket.ticket_id, 'return-to-ai')}
          disabled={!!actionLoading}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold border transition-colors disabled:opacity-50 ${
            dark
              ? 'border-purple-600 bg-purple-900/30 text-purple-300 hover:bg-purple-800/50'
              : 'border-purple-300 bg-purple-50 text-purple-700 hover:bg-purple-100'
          }`}
        >
          <BotIcon className="h-3.5 w-3.5" />
          {actionLoading === 'return-to-ai' ? 'Returning…' : 'Send Back to AI'}
        </button>
      </div>
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

export default function EscalationsQueue({
  apiBase    = '',
  agentName  = 'Admin',
  refreshInterval = 30000,
}) {
  const [dark,        setDark]        = useState(false);
  const [tickets,     setTickets]     = useState(MOCK_ESCALATIONS);
  const [expanded,    setExpanded]    = useState(null);       // ticket_id
  const [actionLoading, setActionLoading] = useState({});     // { ticket_id: 'assign' | 'respond-human' | 'return-to-ai' }
  const [toast,       setToast]       = useState(null);

  // Filters
  const [filterChannel,  setFilterChannel]  = useState('all');
  const [filterPriority, setFilterPriority] = useState('all');
  const [filterReason,   setFilterReason]   = useState('all');
  const [filterWait,     setFilterWait]     = useState('all'); // 'all' | 'over30' | 'under30'

  const intervalRef = useRef(null);

  // ── Fetch ──────────────────────────────────────────────────────────────

  const fetchEscalations = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/api/escalations`);
      if (res.ok) setTickets(await res.json());
    } catch {
      // keep mock data
    }
  }, [apiBase]);

  useEffect(() => {
    fetchEscalations();
    intervalRef.current = setInterval(fetchEscalations, refreshInterval);
    return () => clearInterval(intervalRef.current);
  }, [fetchEscalations, refreshInterval]);

  // ── Actions ────────────────────────────────────────────────────────────

  const handleAction = async (ticketId, action) => {
    setActionLoading(prev => ({ ...prev, [ticketId]: action }));
    const messages = {
      'assign':         `Ticket assigned to ${agentName}.`,
      'respond-human':  'Responding as human agent.',
      'return-to-ai':   'Ticket returned to AI queue.',
    };
    try {
      await fetch(`${apiBase}/support/ticket/${ticketId}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent: agentName }),
      });
      if (action !== 'respond-human') {
        setTickets(prev => prev.filter(t => t.ticket_id !== ticketId));
        setExpanded(null);
      }
      showToast(messages[action], 'success');
    } catch {
      showToast('Action failed. Please try again.', 'error');
    } finally {
      setActionLoading(prev => { const n = { ...prev }; delete n[ticketId]; return n; });
    }
  };

  const handleTakeOver = (ticketId) => {
    handleAction(ticketId, 'assign');
  };

  const showToast = (message, type) => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  };

  // ── Filter logic ───────────────────────────────────────────────────────

  const filtered = tickets.filter(t => {
    if (filterChannel  !== 'all' && t.channel            !== filterChannel)  return false;
    if (filterPriority !== 'all' && t.priority           !== filterPriority) return false;
    if (filterReason   !== 'all' && t.escalation_reason  !== filterReason)   return false;
    if (filterWait === 'over30'  && waitMinutes(t.wait_since) <= 30)         return false;
    if (filterWait === 'under30' && waitMinutes(t.wait_since) > 30)          return false;
    return true;
  });

  // ── Theme ──────────────────────────────────────────────────────────────

  const bg      = dark ? 'bg-gray-900'  : 'bg-gray-50';
  const card    = dark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-100 shadow-sm';
  const text    = dark ? 'text-gray-100' : 'text-gray-900';
  const muted   = dark ? 'text-gray-400' : 'text-gray-500';
  const divider = dark ? 'border-gray-700' : 'border-gray-100';
  const hover   = dark ? 'hover:bg-gray-750' : 'hover:bg-gray-50/80';
  const inputCls = `rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 ${
    dark ? 'bg-gray-700 border-gray-600 text-gray-200' : 'bg-white border-gray-200 text-gray-700'
  }`;

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <>
      <style>{`
        @keyframes fadeIn  { from { opacity:0; transform:translateY(6px) } to { opacity:1; transform:translateY(0) } }
        @keyframes slideDown { from { opacity:0; max-height:0 } to { opacity:1; max-height:600px } }
        @keyframes toastIn { from { opacity:0; transform:translateY(16px) } to { opacity:1; transform:translateY(0) } }
        .fade-in    { animation: fadeIn    0.3s ease both }
        .slide-down { animation: slideDown 0.25s ease both }
        .toast-in   { animation: toastIn   0.3s ease both }
      `}</style>

      <div className={`min-h-screen ${bg} transition-colors duration-300`}>
        <div className="mx-auto max-w-7xl px-4 py-6 space-y-5">

          {/* ── Header ──────────────────────────────────────────────── */}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${dark ? 'bg-red-900/40' : 'bg-red-100'}`}>
                  <AlertIcon className={`h-5 w-5 ${dark ? 'text-red-400' : 'text-red-600'}`} />
                </div>
                <div>
                  <h1 className={`text-xl font-bold ${text}`}>
                    {tickets.length} Ticket{tickets.length !== 1 ? 's' : ''} Awaiting Human Review
                  </h1>
                  <p className={`text-xs ${muted} mt-0.5`}>
                    {filtered.length !== tickets.length
                      ? `Showing ${filtered.length} of ${tickets.length} after filters`
                      : 'All escalated tickets requiring agent attention'}
                  </p>
                </div>
              </div>
            </div>

            <button
              onClick={() => setDark(d => !d)}
              className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                dark
                  ? 'border-gray-600 bg-gray-700 text-gray-300 hover:bg-gray-600'
                  : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50 shadow-sm'
              }`}
            >
              {dark ? <SunIcon className="h-4 w-4" /> : <MoonIcon className="h-4 w-4" />}
              {dark ? 'Light' : 'Dark'}
            </button>
          </div>

          {/* ── Filter bar ──────────────────────────────────────────── */}
          <div className={`rounded-2xl border p-4 ${card}`}>
            <div className="flex flex-wrap items-center gap-3">
              <span className={`text-xs font-semibold uppercase tracking-wide ${muted} whitespace-nowrap`}>
                Filter by:
              </span>

              {/* Channel */}
              <select value={filterChannel} onChange={e => setFilterChannel(e.target.value)} className={inputCls}>
                <option value="all">All Channels</option>
                <option value="email">Email</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="web_form">Web Form</option>
              </select>

              {/* Priority */}
              <select value={filterPriority} onChange={e => setFilterPriority(e.target.value)} className={inputCls}>
                <option value="all">All Priorities</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>

              {/* Escalation reason */}
              <select value={filterReason} onChange={e => setFilterReason(e.target.value)} className={inputCls}>
                <option value="all">All Reasons</option>
                {Object.entries(REASON_CFG).map(([key, cfg]) => (
                  <option key={key} value={key}>{cfg.label}</option>
                ))}
              </select>

              {/* Wait time */}
              <select value={filterWait} onChange={e => setFilterWait(e.target.value)} className={inputCls}>
                <option value="all">Any Wait Time</option>
                <option value="over30">Over 30 min</option>
                <option value="under30">Under 30 min</option>
              </select>

              {/* Clear filters */}
              {(filterChannel !== 'all' || filterPriority !== 'all' || filterReason !== 'all' || filterWait !== 'all') && (
                <button
                  onClick={() => { setFilterChannel('all'); setFilterPriority('all'); setFilterReason('all'); setFilterWait('all'); }}
                  className={`text-xs font-medium underline underline-offset-2 ${dark ? 'text-gray-400 hover:text-gray-200' : 'text-gray-500 hover:text-gray-700'}`}
                >
                  Clear all
                </button>
              )}
            </div>
          </div>

          {/* ── Ticket list ─────────────────────────────────────────── */}
          <div className={`rounded-2xl border overflow-hidden ${card}`}>

            {/* Table header */}
            <div className={`hidden md:grid grid-cols-[1fr_1.4fr_0.9fr_1.3fr_0.7fr_0.7fr_0.8fr] gap-0 px-4 py-3 border-b ${divider}`}>
              {['Ticket ID', 'Customer', 'Channel', 'Escalation Reason', 'Wait Time', 'Priority', 'Action'].map(h => (
                <span key={h} className={`text-xs font-semibold uppercase tracking-wide ${muted}`}>{h}</span>
              ))}
            </div>

            {/* Rows */}
            {filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3">
                <div className={`flex h-12 w-12 items-center justify-center rounded-full ${dark ? 'bg-gray-700' : 'bg-gray-100'}`}>
                  <svg className={`h-6 w-6 ${muted}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                  </svg>
                </div>
                <p className={`text-sm font-medium ${text}`}>No tickets match your filters</p>
                <p className={`text-xs ${muted}`}>Try adjusting or clearing your filters</p>
              </div>
            ) : (
              <div className="divide-y divide-transparent">
                {filtered.map((ticket, i) => {
                  const ChIcon   = CHANNEL_ICON[ticket.channel] || WebIcon;
                  const chColor  = CHANNEL_COLOR[ticket.channel] || CHANNEL_COLOR.web_form;
                  const reasonCfg = REASON_CFG[ticket.escalation_reason];
                  const isOpen   = expanded === ticket.ticket_id;
                  const mode     = dark ? 'dark' : 'light';
                  const loading  = actionLoading[ticket.ticket_id];

                  return (
                    <div key={ticket.ticket_id} className={`border-b ${divider} fade-in`} style={{ animationDelay: `${i * 30}ms` }}>

                      {/* Main row */}
                      <div
                        className={`grid grid-cols-1 md:grid-cols-[1fr_1.4fr_0.9fr_1.3fr_0.7fr_0.7fr_0.8fr] gap-3 md:gap-0 px-4 py-3.5 cursor-pointer transition-colors ${hover}`}
                        onClick={() => setExpanded(isOpen ? null : ticket.ticket_id)}
                      >
                        {/* Ticket ID */}
                        <div className="flex items-center gap-2">
                          <ChevronIcon className={`h-3.5 w-3.5 flex-shrink-0 ${muted}`} open={isOpen} />
                          <span className={`font-mono text-xs ${dark ? 'text-gray-300' : 'text-gray-600'}`}>
                            {truncateId(ticket.ticket_id)}
                          </span>
                        </div>

                        {/* Customer */}
                        <div className="flex flex-col min-w-0">
                          <span className={`text-xs font-semibold ${text} truncate`}>{ticket.customer_name}</span>
                          <span className={`text-xs ${muted} truncate`}>{ticket.customer_email}</span>
                        </div>

                        {/* Channel */}
                        <div className="flex items-center">
                          <span className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium ${chColor[mode]}`}>
                            <ChIcon className="h-3 w-3" />
                            {ticket.channel?.replace('_', ' ')}
                          </span>
                        </div>

                        {/* Escalation reason */}
                        <div className="flex items-center">
                          {reasonCfg ? (
                            <span className={`text-xs font-semibold ${reasonCfg.color}`}>
                              {reasonCfg.label}
                            </span>
                          ) : (
                            <span className={`text-xs ${muted}`}>{ticket.escalation_reason}</span>
                          )}
                        </div>

                        {/* Wait time */}
                        <div className="flex items-center">
                          <WaitBadge iso={ticket.wait_since} dark={dark} />
                        </div>

                        {/* Priority */}
                        <div className="flex items-center">
                          <PriorityBadge priority={ticket.priority} dark={dark} />
                        </div>

                        {/* Take Over action */}
                        <div className="flex items-center" onClick={e => e.stopPropagation()}>
                          <button
                            onClick={() => handleTakeOver(ticket.ticket_id)}
                            disabled={!!loading}
                            className={`rounded-lg px-3 py-1.5 text-xs font-semibold border transition-colors disabled:opacity-50 ${
                              dark
                                ? 'border-blue-600 bg-blue-900/30 text-blue-300 hover:bg-blue-800/50'
                                : 'border-blue-300 bg-blue-50 text-blue-700 hover:bg-blue-100'
                            }`}
                          >
                            {loading === 'assign' ? '…' : 'Take Over'}
                          </button>
                        </div>
                      </div>

                      {/* Expanded detail panel */}
                      {isOpen && (
                        <div className="slide-down overflow-hidden">
                          <DetailPanel
                            ticket={ticket}
                            dark={dark}
                            onAction={handleAction}
                            actionLoading={loading}
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Footer summary */}
            <div className={`px-6 py-3 border-t ${divider} flex items-center justify-between`}>
              <span className={`text-xs ${muted}`}>
                {filtered.filter(t => waitMinutes(t.wait_since) > 30).length} ticket(s) waiting over 30 minutes
              </span>
              <span className={`text-xs ${muted}`}>
                {filtered.filter(t => t.priority === 'high').length} high-priority
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Toast notification ─────────────────────────────────────── */}
      {toast && (
        <div className={`fixed bottom-6 right-6 z-50 toast-in flex items-center gap-2.5 rounded-xl px-4 py-3 text-sm font-medium shadow-lg ${
          toast.type === 'success'
            ? (dark ? 'bg-green-800 text-green-100' : 'bg-green-600 text-white')
            : (dark ? 'bg-red-800 text-red-100'     : 'bg-red-600 text-white')
        }`}>
          {toast.type === 'success'
            ? <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/></svg>
            : <AlertIcon className="h-4 w-4" />}
          {toast.message}
        </div>
      )}
    </>
  );
}
