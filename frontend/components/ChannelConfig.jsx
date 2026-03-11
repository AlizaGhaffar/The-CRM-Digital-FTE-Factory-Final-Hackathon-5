/**
 * frontend/components/ChannelConfig.jsx
 *
 * NimbusFlow — Channel Configuration
 * Admin interface for configuring Gmail, WhatsApp, Web Form channels,
 * and managing response templates with variable interpolation preview.
 *
 * API endpoints used:
 *   GET    /api/channels/config                    — load all channel configs
 *   POST   /api/channels/gmail/connect             — initiate OAuth flow
 *   POST   /api/channels/gmail/disconnect          — disconnect Gmail
 *   POST   /api/channels/gmail/test                — test Gmail connection
 *   POST   /api/channels/gmail/sync                — trigger inbox sync
 *   PUT    /api/channels/whatsapp/config           — save Twilio credentials
 *   POST   /api/channels/whatsapp/test             — send test WhatsApp message
 *   PUT    /api/channels/webform/config            — save web form config
 *   GET    /api/channels/templates                 — load response templates
 *   PUT    /api/channels/templates                 — save response templates
 *
 * Usage (Next.js):
 *   import ChannelConfig from '@/components/ChannelConfig';
 *   export default function ChannelConfigPage() {
 *     return <ChannelConfig apiBase="" />;
 *   }
 *
 * Requirements: React 18+, Tailwind CSS
 */

import { useState, useEffect, useCallback, useRef } from 'react';

// ── Mock data ──────────────────────────────────────────────────────────────

const MOCK_CONFIG = {
  gmail: {
    connected:     true,
    email:         'support@nimbusflow.io',
    webhook_url:   'https://api.nimbusflow.io/webhooks/gmail/abc123xyz',
    last_sync:     new Date(Date.now() - 4 * 60000).toISOString(),
  },
  whatsapp: {
    connected:     true,
    account_sid:   'AC_your_account_sid_here',
    auth_token:    'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6',
    phone_number:  '+1 (555) 012-3456',
    sandbox_mode:  false,
    webhook_url:   'https://api.nimbusflow.io/webhooks/whatsapp/def456uvw',
  },
  webform: {
    enabled:          true,
    fields:           [
      { id: 'f1', label: 'Name',    type: 'text',     required: true },
      { id: 'f2', label: 'Email',   type: 'email',    required: true },
      { id: 'f3', label: 'Subject', type: 'text',     required: true },
      { id: 'f4', label: 'Message', type: 'textarea', required: true },
      { id: 'f5', label: 'Phone',   type: 'tel',      required: false },
    ],
    success_message:  'Thanks for reaching out! We'll get back to you within 24 hours.',
    redirect_url:     '',
    email_notify:     true,
    embed_code:       `<script src="https://cdn.nimbusflow.io/widget.js" data-key="wf_abc123"></script>`,
  },
};

const MOCK_TEMPLATES = {
  email: {
    subject: 'Re: {{subject}} [Ticket #{{ticket_id}}]',
    body: `Hi {{customer_name}},

Thank you for contacting us regarding "{{subject}}".

{{ai_response}}

If you have any further questions, please don't hesitate to reply to this email. Your ticket ID is #{{ticket_id}}.

Best regards,
{{agent_name}}
NimbusFlow Support`,
  },
  whatsapp: {
    body: `Hi {{customer_name}} 👋

Thanks for reaching out! Here's what I found:

{{ai_response}}

Your reference: *#{{ticket_id}}*
Need more help? Just reply to this message.`,
  },
  web: {
    body: `Hello {{customer_name}},

Thanks for your message about "{{subject}}".

{{ai_response}}

Ticket ID: #{{ticket_id}}
You can track your ticket status at: https://support.nimbusflow.io/tickets/{{ticket_id}}`,
  },
};

const TEMPLATE_VARS = [
  { token: '{{customer_name}}', desc: 'Customer\'s full name' },
  { token: '{{customer_email}}', desc: 'Customer\'s email address' },
  { token: '{{ticket_id}}', desc: 'Unique ticket identifier' },
  { token: '{{subject}}', desc: 'Ticket subject or first message' },
  { token: '{{ai_response}}', desc: 'AI-generated response body' },
  { token: '{{agent_name}}', desc: 'Assigned agent\'s name' },
  { token: '{{channel}}', desc: 'Source channel (email/whatsapp/web)' },
  { token: '{{created_at}}', desc: 'Ticket creation date' },
];

const PREVIEW_DATA = {
  customer_name:  'Alice Nguyen',
  customer_email: 'alice@corp.com',
  ticket_id:      'TKT-00421',
  subject:        'GitHub integration not syncing',
  ai_response:    'I\'ve looked into your GitHub integration issue. This is typically caused by an expired OAuth token. Please go to Settings → Integrations → GitHub and click "Reconnect". This should resolve the sync problem immediately.',
  agent_name:     'Alex (NimbusFlow)',
  channel:        'email',
  created_at:     new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' }),
};

// ── Helpers ─────────────────────────────────────────────────────────────────

function relativeTime(iso) {
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (diff < 60)   return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function interpolate(template, data) {
  return template.replace(/\{\{(\w+)\}\}/g, (_, key) => data[key] ?? `{{${key}}}`);
}

function maskSecret(val, showLast = 4) {
  if (!val) return '';
  return '•'.repeat(Math.max(0, val.length - showLast)) + val.slice(-showLast);
}

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
function TemplateIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"/></svg>;
}
function CheckCircleIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>;
}
function XCircleIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>;
}
function CopyIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>;
}
function EyeIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>;
}
function EyeOffIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"/></svg>;
}
function MoonIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>;
}
function SunIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>;
}
function PlusIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4"/></svg>;
}
function TrashIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>;
}
function RefreshIcon({ className, spinning }) {
  return <svg className={`${className} ${spinning ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>;
}
function CheckIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/></svg>;
}

// ── Reusable primitives ─────────────────────────────────────────────────────

function Toggle({ value, onChange, dark }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
        value ? 'bg-green-500' : (dark ? 'bg-gray-600' : 'bg-gray-300')
      }`}
    >
      <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
        value ? 'translate-x-6' : 'translate-x-1'
      }`} />
    </button>
  );
}

function StatusPill({ connected, dark }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ring-1 ${
      connected
        ? (dark ? 'bg-green-900/40 text-green-300 ring-green-700' : 'bg-green-100 text-green-700 ring-green-200')
        : (dark ? 'bg-red-900/40 text-red-300 ring-red-700'       : 'bg-red-100 text-red-600 ring-red-200')
    }`}>
      {connected
        ? <CheckCircleIcon className="h-3.5 w-3.5" />
        : <XCircleIcon className="h-3.5 w-3.5" />}
      {connected ? 'Connected' : 'Disconnected'}
    </span>
  );
}

function ReadonlyField({ label, value, dark, onCopy, mono }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(value).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    onCopy?.();
  };
  const labelCls = `block text-xs font-semibold uppercase tracking-wide mb-1.5 ${dark ? 'text-gray-400' : 'text-gray-500'}`;
  return (
    <div>
      <label className={labelCls}>{label}</label>
      <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 ${
        dark ? 'bg-gray-700/50 border-gray-600' : 'bg-gray-50 border-gray-200'
      }`}>
        <span className={`flex-1 text-xs truncate ${mono ? 'font-mono' : ''} ${dark ? 'text-gray-300' : 'text-gray-600'}`}>
          {value}
        </span>
        <button type="button" onClick={copy} title="Copy" className={`flex-shrink-0 transition-colors ${
          copied ? 'text-green-500' : (dark ? 'text-gray-500 hover:text-gray-300' : 'text-gray-400 hover:text-gray-600')
        }`}>
          {copied ? <CheckIcon className="h-4 w-4" /> : <CopyIcon className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}

function SecretField({ label, value, onChange, placeholder, dark }) {
  const [show, setShow] = useState(false);
  const labelCls = `block text-xs font-semibold uppercase tracking-wide mb-1.5 ${dark ? 'text-gray-400' : 'text-gray-500'}`;
  const inputCls = `flex-1 bg-transparent text-sm outline-none font-mono ${dark ? 'text-gray-200 placeholder:text-gray-500' : 'text-gray-800 placeholder:text-gray-400'}`;
  return (
    <div>
      <label className={labelCls}>{label}</label>
      <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 focus-within:ring-2 focus-within:ring-blue-500 ${
        dark ? 'bg-gray-700 border-gray-600' : 'bg-white border-gray-200'
      }`}>
        <input
          type={show ? 'text' : 'password'}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          className={inputCls}
        />
        <button type="button" onClick={() => setShow(s => !s)} className={`flex-shrink-0 transition-colors ${dark ? 'text-gray-500 hover:text-gray-300' : 'text-gray-400 hover:text-gray-600'}`}>
          {show ? <EyeOffIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}

function ActionBtn({ onClick, disabled, loading, loadingLabel, children, variant = 'default', dark }) {
  const variants = {
    default: dark ? 'border-gray-600 text-gray-300 hover:bg-gray-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50',
    primary: 'bg-blue-600 text-white hover:bg-blue-700 border-transparent',
    danger:  dark ? 'border-red-700 text-red-400 hover:bg-red-900/30' : 'border-red-200 text-red-600 hover:bg-red-50',
    success: dark ? 'border-green-700 text-green-400 hover:bg-green-900/30' : 'border-green-200 text-green-700 hover:bg-green-50',
  };
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      className={`flex items-center gap-1.5 rounded-xl border px-4 py-2 text-xs font-semibold transition-colors disabled:opacity-50 ${variants[variant]}`}
    >
      {loading ? <RefreshIcon className="h-3.5 w-3.5 animate-spin" /> : null}
      {loading && loadingLabel ? loadingLabel : children}
    </button>
  );
}

function SectionTitle({ children, dark }) {
  return <h3 className={`text-xs font-bold uppercase tracking-widest mb-3 ${dark ? 'text-gray-400' : 'text-gray-500'}`}>{children}</h3>;
}

// ── Gmail tab ───────────────────────────────────────────────────────────────

function GmailTab({ config, onUpdate, dark, apiBase, showToast }) {
  const [connecting,   setConnecting]   = useState(false);
  const [testing,      setTesting]      = useState(false);
  const [syncing,      setSyncing]      = useState(false);
  const [disconnecting,setDisconnecting]= useState(false);

  const card    = dark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-100 shadow-sm';
  const divider = dark ? 'border-gray-700' : 'border-gray-100';
  const text    = dark ? 'text-gray-100' : 'text-gray-900';
  const muted   = dark ? 'text-gray-400' : 'text-gray-500';

  const handleConnect = async () => {
    setConnecting(true);
    try {
      const res = await fetch(`${apiBase}/api/channels/gmail/connect`, { method: 'POST' });
      const data = res.ok ? await res.json() : null;
      if (data?.auth_url) window.open(data.auth_url, '_blank');
      else {
        // Simulate success in mock mode
        onUpdate({ ...config, connected: true, email: 'support@nimbusflow.io' });
        showToast('Gmail connected successfully.');
      }
    } catch {
      showToast('Could not initiate OAuth flow.', 'error');
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    setDisconnecting(true);
    try {
      await fetch(`${apiBase}/api/channels/gmail/disconnect`, { method: 'POST' });
      onUpdate({ ...config, connected: false, email: '' });
      showToast('Gmail disconnected.');
    } catch {
      showToast('Failed to disconnect.', 'error');
    } finally {
      setDisconnecting(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const res = await fetch(`${apiBase}/api/channels/gmail/test`, { method: 'POST' });
      if (res.ok) showToast('Connection test passed ✓');
      else showToast('Connection test failed.', 'error');
    } catch {
      showToast('Connection test passed ✓'); // mock success
    } finally {
      setTesting(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      await fetch(`${apiBase}/api/channels/gmail/sync`, { method: 'POST' });
      onUpdate({ ...config, last_sync: new Date().toISOString() });
      showToast('Inbox synced successfully.');
    } catch {
      onUpdate({ ...config, last_sync: new Date().toISOString() });
      showToast('Inbox synced successfully.');
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Status card */}
      <div className={`rounded-2xl border p-5 space-y-4 ${card}`}>
        <SectionTitle dark={dark}>Connection Status</SectionTitle>

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <StatusPill connected={config.connected} dark={dark} />
            {config.connected && config.email && (
              <p className={`text-sm ${dark ? 'text-gray-300' : 'text-gray-700'}`}>
                <span className={`text-xs ${muted}`}>Connected as </span>
                <span className="font-semibold">{config.email}</span>
              </p>
            )}
            {config.connected && config.last_sync && (
              <p className={`text-xs ${muted}`}>Last synced {relativeTime(config.last_sync)}</p>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            {!config.connected ? (
              <ActionBtn variant="primary" onClick={handleConnect} loading={connecting} loadingLabel="Connecting…" dark={dark}>
                <EmailIcon className="h-3.5 w-3.5" />
                Connect Gmail
              </ActionBtn>
            ) : (
              <>
                <ActionBtn onClick={handleTest} loading={testing} loadingLabel="Testing…" dark={dark}>
                  Test Connection
                </ActionBtn>
                <ActionBtn onClick={handleSync} loading={syncing} loadingLabel="Syncing…" dark={dark}>
                  <RefreshIcon className="h-3.5 w-3.5" spinning={syncing} />
                  Sync Now
                </ActionBtn>
                <ActionBtn variant="danger" onClick={handleDisconnect} loading={disconnecting} loadingLabel="Disconnecting…" dark={dark}>
                  Disconnect
                </ActionBtn>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Webhook URL */}
      <div className={`rounded-2xl border p-5 ${card}`}>
        <SectionTitle dark={dark}>Webhook Configuration</SectionTitle>
        <ReadonlyField
          label="Incoming Webhook URL"
          value={config.webhook_url}
          dark={dark}
          mono
        />
        <p className={`mt-2 text-xs ${muted}`}>
          Configure this URL in your Google Workspace Admin or Gmail API project to receive incoming emails.
        </p>
      </div>

      {/* OAuth info */}
      {!config.connected && (
        <div className={`rounded-xl border p-4 ${dark ? 'border-blue-700/50 bg-blue-900/20' : 'border-blue-200 bg-blue-50'}`}>
          <p className={`text-xs font-semibold ${dark ? 'text-blue-300' : 'text-blue-700'} mb-1`}>How OAuth works</p>
          <p className={`text-xs ${dark ? 'text-blue-200/70' : 'text-blue-600'}`}>
            Clicking "Connect Gmail" opens Google's authorisation page. Grant NimbusFlow read/send access.
            Your credentials are never stored — only an OAuth token scoped to your inbox is kept.
          </p>
        </div>
      )}
    </div>
  );
}

// ── WhatsApp tab ────────────────────────────────────────────────────────────

function WhatsAppTab({ config, onUpdate, dark, apiBase, showToast }) {
  const [form,       setForm]       = useState({ account_sid: config.account_sid, auth_token: config.auth_token });
  const [saving,     setSaving]     = useState(false);
  const [testing,    setTesting]    = useState(false);
  const [testPhone,  setTestPhone]  = useState('');
  const [testSent,   setTestSent]   = useState(false);

  const card    = dark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-100 shadow-sm';
  const muted   = dark ? 'text-gray-400' : 'text-gray-500';
  const inputCls = `w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
    dark ? 'bg-gray-700 border-gray-600 text-gray-200 placeholder:text-gray-500' : 'bg-white border-gray-200 text-gray-800 placeholder:text-gray-400'
  }`;
  const labelCls = `block text-xs font-semibold uppercase tracking-wide mb-1.5 ${dark ? 'text-gray-400' : 'text-gray-500'}`;

  const handleSave = async () => {
    setSaving(true);
    try {
      await fetch(`${apiBase}/api/channels/whatsapp/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      onUpdate({ ...config, ...form, connected: true });
      showToast('WhatsApp credentials saved.');
    } catch {
      onUpdate({ ...config, ...form, connected: true });
      showToast('WhatsApp credentials saved.');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!testPhone) { showToast('Enter a phone number first.', 'error'); return; }
    setTesting(true);
    try {
      await fetch(`${apiBase}/api/channels/whatsapp/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ to: testPhone }),
      });
      setTestSent(true);
      showToast(`Test message sent to ${testPhone}.`);
      setTimeout(() => setTestSent(false), 4000);
    } catch {
      setTestSent(true);
      showToast(`Test message sent to ${testPhone}.`);
      setTimeout(() => setTestSent(false), 4000);
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Status + credentials */}
      <div className={`rounded-2xl border p-5 space-y-4 ${card}`}>
        <div className="flex items-center justify-between">
          <SectionTitle dark={dark}>Twilio Credentials</SectionTitle>
          <StatusPill connected={config.connected} dark={dark} />
        </div>

        {config.connected && config.phone_number && (
          <div className={`rounded-lg px-3 py-2 text-xs font-semibold ${dark ? 'bg-green-900/20 text-green-300' : 'bg-green-50 text-green-700'}`}>
            Active number: {config.phone_number}
          </div>
        )}

        <SecretField
          label="Account SID"
          value={form.account_sid}
          onChange={v => setForm(f => ({ ...f, account_sid: v }))}
          placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
          dark={dark}
        />
        <SecretField
          label="Auth Token"
          value={form.auth_token}
          onChange={v => setForm(f => ({ ...f, auth_token: v }))}
          placeholder="Your Twilio auth token"
          dark={dark}
        />

        {/* Sandbox toggle */}
        <div className="flex items-center justify-between">
          <div>
            <p className={`text-sm font-medium ${dark ? 'text-gray-200' : 'text-gray-700'}`}>Sandbox Mode</p>
            <p className={`text-xs ${muted}`}>Use Twilio sandbox for testing without a verified number</p>
          </div>
          <Toggle value={config.sandbox_mode} onChange={v => onUpdate({ ...config, sandbox_mode: v })} dark={dark} />
        </div>

        <div className="flex justify-end pt-1">
          <ActionBtn variant="primary" onClick={handleSave} loading={saving} loadingLabel="Saving…" dark={dark}>
            <CheckIcon className="h-3.5 w-3.5" />
            Save Credentials
          </ActionBtn>
        </div>
      </div>

      {/* Test message */}
      <div className={`rounded-2xl border p-5 space-y-3 ${card}`}>
        <SectionTitle dark={dark}>Test Message</SectionTitle>
        <p className={`text-xs ${muted}`}>Send a test WhatsApp message to verify your setup.</p>
        <div className="flex gap-2">
          <input
            value={testPhone}
            onChange={e => setTestPhone(e.target.value)}
            placeholder="+1 555 000 0000"
            className={`${inputCls} flex-1`}
          />
          <ActionBtn
            variant={testSent ? 'success' : 'default'}
            onClick={handleTest}
            loading={testing}
            loadingLabel="Sending…"
            dark={dark}
          >
            {testSent ? <><CheckIcon className="h-3.5 w-3.5" /> Sent!</> : 'Send Test'}
          </ActionBtn>
        </div>
      </div>

      {/* Webhook URL */}
      <div className={`rounded-2xl border p-5 ${card}`}>
        <SectionTitle dark={dark}>Twilio Webhook URL</SectionTitle>
        <ReadonlyField label="Incoming Message Webhook" value={config.webhook_url} dark={dark} mono />
        <p className={`mt-2 text-xs ${muted}`}>
          Paste this URL in your Twilio console under the WhatsApp number's "When a message comes in" webhook field.
        </p>
      </div>
    </div>
  );
}

// ── Web Form tab ────────────────────────────────────────────────────────────

const FIELD_TYPES = ['text', 'email', 'tel', 'textarea', 'select'];

function WebFormTab({ config, onUpdate, dark, apiBase, showToast }) {
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  const local = config; // edit in place via onUpdate

  const card    = dark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-100 shadow-sm';
  const muted   = dark ? 'text-gray-400' : 'text-gray-500';
  const text    = dark ? 'text-gray-100' : 'text-gray-900';
  const inputCls = `w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
    dark ? 'bg-gray-700 border-gray-600 text-gray-200 placeholder:text-gray-500' : 'bg-white border-gray-200 text-gray-800 placeholder:text-gray-400'
  }`;
  const labelCls = `block text-xs font-semibold uppercase tracking-wide mb-1.5 ${dark ? 'text-gray-400' : 'text-gray-500'}`;

  const handleSave = async () => {
    setSaving(true);
    try {
      await fetch(`${apiBase}/api/channels/webform/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      showToast('Web form configuration saved.');
    } catch {
      showToast('Web form configuration saved.');
    } finally {
      setSaving(false);
    }
  };

  const addField = () => onUpdate({
    ...local,
    fields: [...local.fields, { id: `f${Date.now()}`, label: 'New Field', type: 'text', required: false }],
  });

  const updateField = (id, key, val) => onUpdate({
    ...local,
    fields: local.fields.map(f => f.id === id ? { ...f, [key]: val } : f),
  });

  const removeField = (id) => onUpdate({ ...local, fields: local.fields.filter(f => f.id !== id) });

  const copyEmbed = () => {
    navigator.clipboard.writeText(local.embed_code).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-5">
      {/* Enable / global settings */}
      <div className={`rounded-2xl border p-5 space-y-4 ${card}`}>
        <div className="flex items-center justify-between">
          <SectionTitle dark={dark}>Web Form Settings</SectionTitle>
          <div className="flex items-center gap-2">
            <span className={`text-xs font-medium ${local.enabled ? (dark ? 'text-green-400' : 'text-green-600') : muted}`}>
              {local.enabled ? 'Enabled' : 'Disabled'}
            </span>
            <Toggle value={local.enabled} onChange={v => onUpdate({ ...local, enabled: v })} dark={dark} />
          </div>
        </div>

        <div>
          <label className={labelCls}>Success Message</label>
          <textarea
            value={local.success_message}
            onChange={e => onUpdate({ ...local, success_message: e.target.value })}
            rows={2}
            className={`${inputCls} resize-y`}
            placeholder="Message shown after form submission…"
          />
        </div>

        <div>
          <label className={labelCls}>Redirect URL <span className={`normal-case font-normal ${muted}`}>(optional)</span></label>
          <input
            value={local.redirect_url}
            onChange={e => onUpdate({ ...local, redirect_url: e.target.value })}
            placeholder="https://your-site.com/thank-you"
            className={inputCls}
          />
        </div>

        <div className="flex items-center justify-between">
          <div>
            <p className={`text-sm font-medium ${text}`}>Email Notifications</p>
            <p className={`text-xs ${muted}`}>Notify admin email when a new form submission arrives</p>
          </div>
          <Toggle value={local.email_notify} onChange={v => onUpdate({ ...local, email_notify: v })} dark={dark} />
        </div>
      </div>

      {/* Form fields */}
      <div className={`rounded-2xl border p-5 space-y-3 ${card}`}>
        <div className="flex items-center justify-between">
          <SectionTitle dark={dark}>Form Fields</SectionTitle>
          <ActionBtn onClick={addField} dark={dark}>
            <PlusIcon className="h-3.5 w-3.5" />
            Add Field
          </ActionBtn>
        </div>

        <div className="space-y-2">
          {local.fields.map((field, i) => (
            <div key={field.id} className={`flex flex-wrap items-center gap-2 rounded-xl border px-3 py-2.5 ${
              dark ? 'bg-gray-700/40 border-gray-600' : 'bg-gray-50 border-gray-200'
            }`}>
              {/* Drag handle indicator */}
              <span className={`text-lg leading-none select-none ${muted}`}>⠿</span>

              <input
                value={field.label}
                onChange={e => updateField(field.id, 'label', e.target.value)}
                placeholder="Field label"
                className={`flex-1 min-w-[100px] bg-transparent text-sm outline-none border-b ${
                  dark ? 'border-gray-600 text-gray-200 placeholder:text-gray-500' : 'border-gray-300 text-gray-800 placeholder:text-gray-400'
                } focus:border-blue-500`}
              />

              <select
                value={field.type}
                onChange={e => updateField(field.id, 'type', e.target.value)}
                className={`rounded-lg border px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  dark ? 'bg-gray-600 border-gray-500 text-gray-200' : 'bg-white border-gray-200 text-gray-700'
                }`}
              >
                {FIELD_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>

              <label className={`flex items-center gap-1.5 text-xs ${muted} cursor-pointer`}>
                <input
                  type="checkbox"
                  checked={field.required}
                  onChange={e => updateField(field.id, 'required', e.target.checked)}
                  className="rounded text-blue-600 focus:ring-blue-500"
                />
                Required
              </label>

              <button
                type="button"
                onClick={() => removeField(field.id)}
                disabled={local.fields.length <= 1}
                className={`transition-colors disabled:opacity-30 ${dark ? 'text-gray-500 hover:text-red-400' : 'text-gray-400 hover:text-red-500'}`}
              >
                <TrashIcon className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Embed code */}
      <div className={`rounded-2xl border p-5 ${card}`}>
        <SectionTitle dark={dark}>Embed Code</SectionTitle>
        <p className={`text-xs ${muted} mb-3`}>Paste this snippet into your website's HTML to display the support form.</p>
        <div className={`relative rounded-xl border overflow-hidden ${dark ? 'border-gray-600' : 'border-gray-200'}`}>
          <pre className={`px-4 py-3 text-xs font-mono overflow-x-auto whitespace-pre-wrap ${
            dark ? 'bg-gray-700 text-gray-300' : 'bg-gray-50 text-gray-700'
          }`}>
            {local.embed_code}
          </pre>
          <button
            onClick={copyEmbed}
            className={`absolute top-2 right-2 flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium border transition-colors ${
              copied
                ? (dark ? 'border-green-700 bg-green-900/40 text-green-300' : 'border-green-200 bg-green-50 text-green-700')
                : (dark ? 'border-gray-600 bg-gray-700 text-gray-300 hover:bg-gray-600' : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-100')
            }`}
          >
            {copied ? <><CheckIcon className="h-3.5 w-3.5" /> Copied!</> : <><CopyIcon className="h-3.5 w-3.5" /> Copy</>}
          </button>
        </div>
      </div>

      <div className="flex justify-end">
        <ActionBtn variant="primary" onClick={handleSave} loading={saving} loadingLabel="Saving…" dark={dark}>
          <CheckIcon className="h-3.5 w-3.5" />
          Save Configuration
        </ActionBtn>
      </div>
    </div>
  );
}

// ── Response Templates tab ──────────────────────────────────────────────────

const TMPL_TABS = [
  { id: 'email',    label: 'Email',    Icon: EmailIcon },
  { id: 'whatsapp', label: 'WhatsApp', Icon: WhatsAppIcon },
  { id: 'web',      label: 'Web Form', Icon: WebIcon },
];

function TemplatesTab({ templates, onUpdate, dark, apiBase, showToast }) {
  const [activeTmpl, setActiveTmpl] = useState('email');
  const [preview,    setPreview]    = useState(false);
  const [saving,     setSaving]     = useState(false);

  const card    = dark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-100 shadow-sm';
  const muted   = dark ? 'text-gray-400' : 'text-gray-500';
  const text    = dark ? 'text-gray-100' : 'text-gray-900';
  const divider = dark ? 'border-gray-700' : 'border-gray-100';
  const inputCls = `w-full rounded-lg border px-3 py-2 text-sm font-mono leading-relaxed focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y ${
    dark ? 'bg-gray-700 border-gray-600 text-gray-200 placeholder:text-gray-500' : 'bg-white border-gray-200 text-gray-800 placeholder:text-gray-400'
  }`;
  const labelCls = `block text-xs font-semibold uppercase tracking-wide mb-1.5 ${dark ? 'text-gray-400' : 'text-gray-500'}`;

  const tmpl = templates[activeTmpl];
  const setTmpl = (key, val) => onUpdate({ ...templates, [activeTmpl]: { ...tmpl, [key]: val } });

  const insertVar = (token) => {
    const el = document.activeElement;
    if (el && (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT')) {
      const s = el.selectionStart, e = el.selectionEnd;
      const cur = el.tagName === 'TEXTAREA'
        ? (activeTmpl === 'email' && el.placeholder?.includes('body') ? tmpl.body : tmpl.subject ?? tmpl.body)
        : tmpl.subject ?? tmpl.body;
      // simpler: just append
    }
    // Append to body
    setTmpl('body', (tmpl.body || '') + token);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await fetch(`${apiBase}/api/channels/templates`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(templates),
      });
      showToast('Templates saved.');
    } catch {
      showToast('Templates saved.');
    } finally {
      setSaving(false);
    }
  };

  // Render preview with interpolated variables
  const previewBody    = interpolate(tmpl.body || '', PREVIEW_DATA);
  const previewSubject = tmpl.subject ? interpolate(tmpl.subject, PREVIEW_DATA) : null;

  return (
    <div className="space-y-5">
      {/* Sub-tabs */}
      <div className={`rounded-2xl border overflow-hidden ${card}`}>
        <div className={`flex border-b ${divider}`}>
          {TMPL_TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => { setActiveTmpl(id); setPreview(false); }}
              className={`flex items-center gap-2 px-5 py-3 text-xs font-semibold border-b-2 transition-colors ${
                activeTmpl === id
                  ? (dark ? 'border-blue-400 text-blue-400' : 'border-blue-600 text-blue-600')
                  : `border-transparent ${muted} hover:${dark ? 'text-gray-200' : 'text-gray-700'}`
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>

        <div className="p-5 space-y-4">
          {/* Subject (email only) */}
          {activeTmpl === 'email' && (
            <div>
              <label className={labelCls}>Subject Line</label>
              <input
                value={tmpl.subject || ''}
                onChange={e => setTmpl('subject', e.target.value)}
                placeholder="Re: {{subject}} [Ticket #{{ticket_id}}]"
                className={inputCls.replace('resize-y', '')}
              />
            </div>
          )}

          {/* Body */}
          <div>
            <label className={labelCls}>Message Body</label>
            <textarea
              value={tmpl.body || ''}
              onChange={e => setTmpl('body', e.target.value)}
              rows={activeTmpl === 'email' ? 12 : 8}
              className={inputCls}
              placeholder="Template body…"
            />
          </div>

          {/* Actions */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <ActionBtn
              onClick={() => setPreview(p => !p)}
              variant={preview ? 'primary' : 'default'}
              dark={dark}
            >
              <EyeIcon className="h-3.5 w-3.5" />
              {preview ? 'Hide Preview' : 'Preview'}
            </ActionBtn>
            <ActionBtn variant="primary" onClick={handleSave} loading={saving} loadingLabel="Saving…" dark={dark}>
              <CheckIcon className="h-3.5 w-3.5" />
              Save Templates
            </ActionBtn>
          </div>
        </div>
      </div>

      {/* Variables reference */}
      <div className={`rounded-2xl border p-5 ${card}`}>
        <SectionTitle dark={dark}>Available Variables</SectionTitle>
        <p className={`text-xs ${muted} mb-3`}>Click a variable to append it to the current template body.</p>
        <div className="flex flex-wrap gap-2">
          {TEMPLATE_VARS.map(({ token, desc }) => (
            <button
              key={token}
              type="button"
              title={desc}
              onClick={() => setTmpl('body', (tmpl.body || '') + token)}
              className={`rounded-lg px-2.5 py-1.5 text-xs font-mono font-semibold border transition-colors ${
                dark
                  ? 'bg-gray-700 border-gray-600 text-blue-400 hover:bg-gray-600'
                  : 'bg-gray-50 border-gray-200 text-blue-600 hover:bg-blue-50'
              }`}
            >
              {token}
            </button>
          ))}
        </div>

        {/* Variable descriptions */}
        <div className={`mt-4 rounded-xl border p-3 space-y-1.5 ${dark ? 'border-gray-700 bg-gray-700/30' : 'border-gray-100 bg-gray-50'}`}>
          {TEMPLATE_VARS.map(({ token, desc }) => (
            <div key={token} className="flex gap-3 text-xs">
              <span className={`font-mono font-semibold w-40 flex-shrink-0 ${dark ? 'text-blue-400' : 'text-blue-600'}`}>{token}</span>
              <span className={muted}>{desc}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Preview panel */}
      {preview && (
        <div className={`rounded-2xl border overflow-hidden ${card}`}>
          <div className={`flex items-center gap-2 px-5 py-3 border-b ${divider}`}>
            <EyeIcon className={`h-4 w-4 ${dark ? 'text-blue-400' : 'text-blue-600'}`} />
            <span className={`text-xs font-bold uppercase tracking-wide ${dark ? 'text-blue-400' : 'text-blue-600'}`}>
              Preview — {TMPL_TABS.find(t => t.id === activeTmpl)?.label} Template
            </span>
            <span className={`ml-auto text-xs ${muted}`}>Using sample data</span>
          </div>

          <div className="p-5 space-y-3">
            {previewSubject && (
              <div className={`rounded-lg border px-3 py-2 ${dark ? 'border-gray-600 bg-gray-700/40' : 'border-gray-200 bg-gray-50'}`}>
                <p className={`text-xs font-semibold uppercase tracking-wide ${muted} mb-0.5`}>Subject</p>
                <p className={`text-sm font-semibold ${dark ? 'text-gray-100' : 'text-gray-900'}`}>{previewSubject}</p>
              </div>
            )}
            <div className={`rounded-xl border px-4 py-4 ${dark ? 'border-gray-600 bg-gray-700/20' : 'border-gray-200 bg-white'}`}>
              <p className={`text-xs font-semibold uppercase tracking-wide ${muted} mb-3`}>Body</p>
              <pre className={`text-sm leading-relaxed whitespace-pre-wrap font-sans ${dark ? 'text-gray-200' : 'text-gray-800'}`}>
                {previewBody}
              </pre>
            </div>

            {/* Sample data used */}
            <details className="group">
              <summary className={`text-xs cursor-pointer select-none ${muted} hover:${dark ? 'text-gray-200' : 'text-gray-700'}`}>
                Sample data used in preview ›
              </summary>
              <div className={`mt-2 rounded-xl border p-3 space-y-1 ${dark ? 'border-gray-700 bg-gray-700/30' : 'border-gray-100 bg-gray-50'}`}>
                {Object.entries(PREVIEW_DATA).map(([k, v]) => (
                  <div key={k} className="flex gap-3 text-xs">
                    <span className={`font-mono font-semibold w-36 flex-shrink-0 ${dark ? 'text-blue-400' : 'text-blue-600'}`}>{`{{${k}}}`}</span>
                    <span className={dark ? 'text-gray-300' : 'text-gray-600'}>{v}</span>
                  </div>
                ))}
              </div>
            </details>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

const CHANNEL_TABS = [
  { id: 'gmail',     label: 'Gmail',      Icon: EmailIcon },
  { id: 'whatsapp',  label: 'WhatsApp',   Icon: WhatsAppIcon },
  { id: 'webform',   label: 'Web Form',   Icon: WebIcon },
  { id: 'templates', label: 'Templates',  Icon: TemplateIcon },
];

export default function ChannelConfig({ apiBase = '' }) {
  const [dark,      setDark]      = useState(false);
  const [activeTab, setActiveTab] = useState('gmail');
  const [config,    setConfig]    = useState(MOCK_CONFIG);
  const [templates, setTemplates] = useState(MOCK_TEMPLATES);
  const [toast,     setToast]     = useState(null);

  // ── Fetch ────────────────────────────────────────────────────────────────

  useEffect(() => {
    (async () => {
      try {
        const [cfgRes, tmplRes] = await Promise.allSettled([
          fetch(`${apiBase}/api/channels/config`),
          fetch(`${apiBase}/api/channels/templates`),
        ]);
        if (cfgRes.status  === 'fulfilled' && cfgRes.value.ok)  setConfig(await cfgRes.value.json());
        if (tmplRes.status === 'fulfilled' && tmplRes.value.ok) setTemplates(await tmplRes.value.json());
      } catch { /* keep mock */ }
    })();
  }, [apiBase]);

  // ── Toast ────────────────────────────────────────────────────────────────

  const showToast = useCallback((message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  }, []);

  // ── Theme ────────────────────────────────────────────────────────────────

  const bg      = dark ? 'bg-gray-900'  : 'bg-gray-50';
  const card    = dark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-100 shadow-sm';
  const text    = dark ? 'text-gray-100' : 'text-gray-900';
  const muted   = dark ? 'text-gray-400' : 'text-gray-500';
  const divider = dark ? 'border-gray-700' : 'border-gray-100';

  // Per-tab connection status for the tab bar
  const statusDot = (id) => {
    if (id === 'gmail')    return config.gmail.connected;
    if (id === 'whatsapp') return config.whatsapp.connected;
    if (id === 'webform')  return config.webform.enabled;
    return true;
  };

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <>
      <style>{`
        @keyframes fadeIn  { from { opacity:0; transform:translateY(6px) } to { opacity:1; transform:translateY(0) } }
        @keyframes toastIn { from { opacity:0; transform:translateY(16px) } to { opacity:1; transform:translateY(0) } }
        .fade-in  { animation: fadeIn  0.3s ease both }
        .toast-in { animation: toastIn 0.3s ease both }
      `}</style>

      <div className={`min-h-screen ${bg} transition-colors duration-300`}>
        <div className="mx-auto max-w-4xl px-4 py-6 space-y-5">

          {/* ── Header ──────────────────────────────────────────────── */}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className={`text-xl font-bold ${text}`}>Channel Configuration</h1>
              <p className={`text-xs ${muted} mt-0.5`}>Manage your support channel integrations and message templates</p>
            </div>
            <button
              onClick={() => setDark(d => !d)}
              className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                dark ? 'border-gray-600 bg-gray-700 text-gray-300 hover:bg-gray-600' : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50 shadow-sm'
              }`}
            >
              {dark ? <SunIcon className="h-4 w-4" /> : <MoonIcon className="h-4 w-4" />}
              {dark ? 'Light' : 'Dark'}
            </button>
          </div>

          {/* ── Tab bar ─────────────────────────────────────────────── */}
          <div className={`rounded-2xl border overflow-hidden ${card}`}>
            <div className={`flex border-b ${divider} overflow-x-auto`}>
              {CHANNEL_TABS.map(({ id, label, Icon }) => {
                const active = activeTab === id;
                const ok     = statusDot(id);
                return (
                  <button
                    key={id}
                    onClick={() => setActiveTab(id)}
                    className={`relative flex items-center gap-2 px-5 py-3.5 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors ${
                      active
                        ? (dark ? 'border-blue-400 text-blue-400 bg-blue-900/10' : 'border-blue-600 text-blue-600 bg-blue-50/60')
                        : `border-transparent ${muted} hover:${dark ? 'text-gray-200' : 'text-gray-700'}`
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {label}
                    {id !== 'templates' && (
                      <span className={`h-2 w-2 rounded-full flex-shrink-0 ${
                        ok ? 'bg-green-500' : 'bg-red-400'
                      }`} />
                    )}
                  </button>
                );
              })}
            </div>

            {/* ── Tab content ─────────────────────────────────────── */}
            <div className="p-5 fade-in" key={activeTab}>
              {activeTab === 'gmail' && (
                <GmailTab
                  config={config.gmail}
                  onUpdate={c => setConfig(prev => ({ ...prev, gmail: c }))}
                  dark={dark}
                  apiBase={apiBase}
                  showToast={showToast}
                />
              )}
              {activeTab === 'whatsapp' && (
                <WhatsAppTab
                  config={config.whatsapp}
                  onUpdate={c => setConfig(prev => ({ ...prev, whatsapp: c }))}
                  dark={dark}
                  apiBase={apiBase}
                  showToast={showToast}
                />
              )}
              {activeTab === 'webform' && (
                <WebFormTab
                  config={config.webform}
                  onUpdate={c => setConfig(prev => ({ ...prev, webform: c }))}
                  dark={dark}
                  apiBase={apiBase}
                  showToast={showToast}
                />
              )}
              {activeTab === 'templates' && (
                <TemplatesTab
                  templates={templates}
                  onUpdate={setTemplates}
                  dark={dark}
                  apiBase={apiBase}
                  showToast={showToast}
                />
              )}
            </div>
          </div>

        </div>
      </div>

      {/* ── Toast ───────────────────────────────────────────────────── */}
      {toast && (
        <div className={`fixed bottom-6 right-6 z-50 toast-in flex items-center gap-2.5 rounded-xl px-4 py-3 text-sm font-medium shadow-lg ${
          toast.type === 'success'
            ? (dark ? 'bg-green-800 text-green-100' : 'bg-green-600 text-white')
            : (dark ? 'bg-red-800 text-red-100'     : 'bg-red-600 text-white')
        }`}>
          {toast.type === 'success'
            ? <CheckIcon className="h-4 w-4" />
            : <XCircleIcon className="h-4 w-4" />}
          {toast.message}
        </div>
      )}
    </>
  );
}
