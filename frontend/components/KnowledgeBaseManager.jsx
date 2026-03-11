/**
 * frontend/components/KnowledgeBaseManager.jsx
 *
 * NimbusFlow — Knowledge Base Manager
 * Admin interface for creating, editing, and managing KB articles.
 * Supports dark/light mode, rich-text editing, category filtering,
 * search, preview mode, and tag management.
 *
 * API endpoints used:
 *   GET    /api/kb/articles              — list articles
 *   POST   /api/kb/articles              — create article
 *   PUT    /api/kb/articles/{id}         — update article
 *   DELETE /api/kb/articles/{id}         — delete article
 *   GET    /api/kb/articles/{id}/preview — preview rendered article
 *
 * Usage (Next.js):
 *   import KnowledgeBaseManager from '@/components/KnowledgeBaseManager';
 *   export default function KBPage() {
 *     return <KnowledgeBaseManager apiBase="" />;
 *   }
 *
 * Requirements: React 18+, Tailwind CSS
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';

// ── Mock data ──────────────────────────────────────────────────────────────

const MOCK_ARTICLES = [
  {
    id: 'art-001',
    title: 'Getting Started with NimbusFlow',
    category: 'onboarding',
    status: 'active',
    tags: ['setup', 'quickstart', 'beginner'],
    view_count: 4821,
    updated_at: new Date(Date.now() - 2 * 24 * 60 * 60000).toISOString(),
    content: `# Getting Started with NimbusFlow\n\nWelcome to NimbusFlow! This guide will help you set up your account and send your first automated response within minutes.\n\n## Step 1: Create Your Account\n\nNavigate to [app.nimbusflow.io](https://app.nimbusflow.io) and click **Sign Up**. You can register with your Google account or a business email.\n\n## Step 2: Connect Your Channels\n\nGo to **Settings → Channels** and connect the support channels you use:\n- **Email** — Connect via SMTP/IMAP or use our hosted address\n- **WhatsApp** — Link your WhatsApp Business account\n- **Web Form** — Embed our snippet on your website\n\n## Step 3: Configure Your AI\n\nUpload your knowledge base articles and the AI will start learning from them immediately.\n\n## Need Help?\n\nContact our support team at support@nimbusflow.io or start a chat below.`,
  },
  {
    id: 'art-002',
    title: 'How to Reset Your Password',
    category: 'account',
    status: 'active',
    tags: ['password', 'login', 'security'],
    view_count: 3102,
    updated_at: new Date(Date.now() - 5 * 24 * 60 * 60000).toISOString(),
    content: `# How to Reset Your Password\n\nIf you've forgotten your password or want to change it for security reasons, follow these steps.\n\n## From the Login Page\n\n1. Go to [app.nimbusflow.io/login](https://app.nimbusflow.io/login)\n2. Click **Forgot password?** below the sign-in button\n3. Enter your account email address\n4. Check your inbox for a reset link (valid for 30 minutes)\n5. Click the link and enter your new password\n\n## From Account Settings\n\n1. Click your avatar in the top-right corner\n2. Go to **Settings → Security**\n3. Click **Change Password**\n4. Enter your current password, then your new one\n\n## Password Requirements\n\n- Minimum 12 characters\n- At least one uppercase letter, one number, one symbol\n\n> **Tip:** Use a password manager for maximum security.`,
  },
  {
    id: 'art-003',
    title: 'Understanding AI Escalation Triggers',
    category: 'ai-behaviour',
    status: 'active',
    tags: ['escalation', 'ai', 'automation'],
    view_count: 2874,
    updated_at: new Date(Date.now() - 8 * 24 * 60 * 60000).toISOString(),
    content: `# Understanding AI Escalation Triggers\n\nNimbusFlow's AI will automatically escalate a conversation to a human agent when it detects certain conditions.\n\n## Automatic Triggers\n\n| Trigger | Threshold |\n|---|---|\n| Negative sentiment | Score < 0.25 |\n| Repeated contact | 3+ contacts on same issue |\n| Low confidence | < 0.40 confidence score |\n| Legal / compliance keywords | Any match |\n| Explicit human request | Any match |\n\n## Customising Thresholds\n\nGo to **Settings → AI Configuration → Escalation Rules** to adjust thresholds for your team.\n\n## Manual Escalation\n\nAgents can also manually escalate from the ticket view at any time by clicking **Escalate to Human**.`,
  },
  {
    id: 'art-004',
    title: 'Billing & Subscription FAQ',
    category: 'billing',
    status: 'active',
    tags: ['billing', 'subscription', 'payment', 'invoice'],
    view_count: 2215,
    updated_at: new Date(Date.now() - 12 * 24 * 60 * 60000).toISOString(),
    content: `# Billing & Subscription FAQ\n\n## When am I charged?\n\nYou are charged on the same day each month as your original sign-up date.\n\n## What payment methods are accepted?\n\nWe accept Visa, Mastercard, American Express, and bank transfers for annual plans.\n\n## How do I get an invoice?\n\nInvoices are emailed automatically after each payment. You can also download them from **Settings → Billing → Invoices**.\n\n## Can I change my plan?\n\nYes. Upgrades take effect immediately; downgrades take effect at the next billing cycle.\n\n## What happens if payment fails?\n\nWe retry failed payments 3 times over 7 days. After that, your account is suspended (data is retained for 30 days).`,
  },
  {
    id: 'art-005',
    title: 'Setting Up SSO with Okta',
    category: 'integrations',
    status: 'active',
    tags: ['sso', 'okta', 'saml', 'security'],
    view_count: 1563,
    updated_at: new Date(Date.now() - 18 * 24 * 60 * 60000).toISOString(),
    content: `# Setting Up SSO with Okta\n\nThis guide walks you through configuring SAML 2.0 Single Sign-On between NimbusFlow and Okta.\n\n## Prerequisites\n\n- Okta admin access\n- NimbusFlow Enterprise plan\n\n## Steps\n\n1. In Okta, create a new SAML 2.0 application\n2. Set the **Single Sign-On URL** to: \`https://app.nimbusflow.io/auth/saml/callback\`\n3. Set the **Audience URI** to: \`https://app.nimbusflow.io\`\n4. Configure attribute statements:\n   - \`email\` → \`user.email\`\n   - \`firstName\` → \`user.firstName\`\n   - \`lastName\` → \`user.lastName\`\n5. Download the Okta IdP metadata XML\n6. In NimbusFlow, go to **Settings → SSO** and upload the metadata file\n7. Test the connection and enable SSO\n\n## Troubleshooting\n\nIf the SAML assertion fails, double-check that attribute names match exactly (case-sensitive).`,
  },
  {
    id: 'art-006',
    title: 'WhatsApp Channel Setup Guide',
    category: 'integrations',
    status: 'draft',
    tags: ['whatsapp', 'channel', 'setup'],
    view_count: 0,
    updated_at: new Date(Date.now() - 1 * 24 * 60 * 60000).toISOString(),
    content: `# WhatsApp Channel Setup Guide\n\nConnect your WhatsApp Business account to NimbusFlow to handle customer messages automatically.\n\n## Requirements\n\n- A verified WhatsApp Business account\n- A dedicated phone number (cannot be in use on WhatsApp personally)\n\n## Setup Steps\n\n1. Go to **Settings → Channels → WhatsApp**\n2. Click **Connect WhatsApp Business**\n3. Follow the Facebook Business Manager flow to authorise NimbusFlow\n4. Select the phone number you want to use\n5. Configure your welcome message and opt-out keywords\n\n> **Note:** This article is still being reviewed.`,
  },
  {
    id: 'art-007',
    title: 'Exporting Data and Reports',
    category: 'reporting',
    status: 'active',
    tags: ['export', 'csv', 'reports', 'data'],
    view_count: 978,
    updated_at: new Date(Date.now() - 30 * 24 * 60 * 60000).toISOString(),
    content: `# Exporting Data and Reports\n\nYou can export ticket data, conversation logs, and performance metrics from NimbusFlow at any time.\n\n## Export Tickets\n\n1. Go to **Tickets → All Tickets**\n2. Apply any filters you need\n3. Click **Export → CSV** or **Export → Excel**\n\n## Export Reports\n\nGo to **Reports** and click the download icon on any chart or table.\n\n## Scheduled Exports\n\nEnterprise plans can set up automated email delivery of reports. Go to **Settings → Reports → Scheduled Exports**.\n\n## Data Retention\n\nAll data is retained for 2 years by default. Contact us to extend or reduce retention.`,
  },
  {
    id: 'art-008',
    title: 'GDPR Data Processing Agreement',
    category: 'legal',
    status: 'draft',
    tags: ['gdpr', 'legal', 'dpa', 'compliance'],
    view_count: 0,
    updated_at: new Date(Date.now() - 3 * 24 * 60 * 60000).toISOString(),
    content: `# GDPR Data Processing Agreement\n\nThis article will explain how to request and execute our Data Processing Agreement (DPA) for GDPR compliance.\n\n## Who Needs a DPA?\n\nAny customer based in the EU/EEA, or processing data of EU residents, is required to have a DPA in place.\n\n## How to Request\n\nEmail legal@nimbusflow.io with your company name and registered address. We will send the DPA within 2 business days.\n\n> **Draft — pending legal review before publishing.**`,
  },
];

const CATEGORIES = [
  { value: 'onboarding',    label: 'Onboarding' },
  { value: 'account',       label: 'Account' },
  { value: 'billing',       label: 'Billing' },
  { value: 'ai-behaviour',  label: 'AI Behaviour' },
  { value: 'integrations',  label: 'Integrations' },
  { value: 'reporting',     label: 'Reporting' },
  { value: 'legal',         label: 'Legal' },
];

const CATEGORY_CFG = {
  onboarding:   { light: 'bg-blue-100 text-blue-700',    dark: 'bg-blue-900/40 text-blue-300' },
  account:      { light: 'bg-purple-100 text-purple-700', dark: 'bg-purple-900/40 text-purple-300' },
  billing:      { light: 'bg-amber-100 text-amber-700',   dark: 'bg-amber-900/40 text-amber-300' },
  'ai-behaviour':{ light: 'bg-indigo-100 text-indigo-700', dark: 'bg-indigo-900/40 text-indigo-300' },
  integrations: { light: 'bg-green-100 text-green-700',  dark: 'bg-green-900/40 text-green-300' },
  reporting:    { light: 'bg-orange-100 text-orange-700', dark: 'bg-orange-900/40 text-orange-300' },
  legal:        { light: 'bg-red-100 text-red-700',       dark: 'bg-red-900/40 text-red-300' },
};

// ── Helpers ─────────────────────────────────────────────────────────────────

function relativeDate(iso) {
  const diff = Math.floor((Date.now() - new Date(iso)) / 86400000);
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  if (diff < 30)  return `${diff}d ago`;
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

function highlight(text, query) {
  if (!query) return text;
  const re = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  return text.replace(re, '<mark class="bg-yellow-200 dark:bg-yellow-700 rounded px-0.5">$1</mark>');
}

// ── Lightweight markdown renderer ───────────────────────────────────────────
// Covers: headings, bold, inline code, code blocks, blockquotes, tables, lists, links

function renderMarkdown(md) {
  if (!md) return '';
  let html = md
    // Code blocks
    .replace(/```[\s\S]*?```/g, m => {
      const code = m.replace(/^```[^\n]*\n?/, '').replace(/\n?```$/, '');
      return `<pre class="bg-gray-100 dark:bg-gray-700 rounded-lg p-3 overflow-x-auto text-xs font-mono my-3"><code>${code.replace(/</g, '&lt;')}</code></pre>`;
    })
    // Headings
    .replace(/^### (.+)$/gm, '<h3 class="text-base font-semibold mt-5 mb-2">$1</h3>')
    .replace(/^## (.+)$/gm,  '<h2 class="text-lg font-bold mt-6 mb-2">$1</h2>')
    .replace(/^# (.+)$/gm,   '<h1 class="text-xl font-bold mt-4 mb-3">$1</h1>')
    // Blockquotes
    .replace(/^> (.+)$/gm, '<blockquote class="border-l-4 border-blue-400 pl-4 italic text-gray-500 dark:text-gray-400 my-3">$1</blockquote>')
    // Tables (simple)
    .replace(/^\|(.+)\|$/gm, (row) => {
      const cells = row.split('|').filter(Boolean).map(c => c.trim());
      const isHeader = false;
      return `<tr>${cells.map(c => `<td class="border border-gray-200 dark:border-gray-600 px-3 py-1.5 text-sm">${c}</td>`).join('')}</tr>`;
    })
    // Unordered lists
    .replace(/^[-*] (.+)$/gm, '<li class="ml-5 list-disc text-sm">$1</li>')
    // Ordered lists
    .replace(/^\d+\. (.+)$/gm, '<li class="ml-5 list-decimal text-sm">$1</li>')
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold">$1</strong>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code class="bg-gray-100 dark:bg-gray-700 rounded px-1 py-0.5 text-xs font-mono">$1</code>')
    // Links
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a class="text-blue-600 dark:text-blue-400 underline" href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    // Paragraphs (double newline)
    .replace(/\n\n/g, '</p><p class="text-sm leading-relaxed my-2">')
    .replace(/\n/g, '<br/>');

  return `<p class="text-sm leading-relaxed my-2">${html}</p>`;
}

// ── Icons ──────────────────────────────────────────────────────────────────

function SearchIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>;
}
function PlusIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4"/></svg>;
}
function EditIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>;
}
function TrashIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>;
}
function EyeIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>;
}
function XIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/></svg>;
}
function MoonIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>;
}
function SunIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>;
}
function BookIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/></svg>;
}
function TagIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"/></svg>;
}
function CheckIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/></svg>;
}

// ── Category badge ──────────────────────────────────────────────────────────

function CategoryBadge({ category, dark }) {
  const cfg  = CATEGORY_CFG[category] || CATEGORY_CFG.onboarding;
  const mode = dark ? 'dark' : 'light';
  const label = CATEGORIES.find(c => c.value === category)?.label || category;
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${cfg[mode]}`}>
      {label}
    </span>
  );
}

// ── Status toggle ───────────────────────────────────────────────────────────

function StatusToggle({ value, onChange, dark }) {
  return (
    <button
      type="button"
      onClick={() => onChange(value === 'active' ? 'draft' : 'active')}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
        value === 'active' ? 'bg-green-500' : (dark ? 'bg-gray-600' : 'bg-gray-300')
      }`}
    >
      <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
        value === 'active' ? 'translate-x-6' : 'translate-x-1'
      }`} />
    </button>
  );
}

// ── Tag input ───────────────────────────────────────────────────────────────

function TagInput({ tags, onChange, dark }) {
  const [input, setInput] = useState('');

  const addTag = (raw) => {
    const tag = raw.trim().toLowerCase().replace(/\s+/g, '-');
    if (tag && !tags.includes(tag)) onChange([...tags, tag]);
    setInput('');
  };

  const removeTag = (tag) => onChange(tags.filter(t => t !== tag));

  const handleKey = (e) => {
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag(input); }
    if (e.key === 'Backspace' && !input && tags.length) removeTag(tags[tags.length - 1]);
  };

  return (
    <div className={`flex flex-wrap gap-1.5 rounded-lg border px-3 py-2 min-h-[42px] cursor-text ${
      dark ? 'bg-gray-700 border-gray-600' : 'bg-white border-gray-200'
    }`} onClick={() => document.getElementById('tag-input-field')?.focus()}>
      {tags.map(tag => (
        <span key={tag} className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
          dark ? 'bg-blue-900/50 text-blue-300' : 'bg-blue-100 text-blue-700'
        }`}>
          <TagIcon className="h-3 w-3" />
          {tag}
          <button type="button" onClick={() => removeTag(tag)} className="hover:text-red-500 ml-0.5">
            <XIcon className="h-3 w-3" />
          </button>
        </span>
      ))}
      <input
        id="tag-input-field"
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={handleKey}
        onBlur={() => input && addTag(input)}
        placeholder={tags.length === 0 ? 'Add tags (press Enter or comma)' : ''}
        className={`flex-1 min-w-[140px] bg-transparent text-xs outline-none placeholder:text-gray-400 ${
          dark ? 'text-gray-200' : 'text-gray-700'
        }`}
      />
    </div>
  );
}

// ── Toolbar button (rich-text toolbar) ─────────────────────────────────────

function ToolbarBtn({ label, title, onClick, dark, active }) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={`rounded px-2 py-1 text-xs font-semibold transition-colors ${
        active
          ? (dark ? 'bg-blue-700 text-white' : 'bg-blue-100 text-blue-700')
          : (dark ? 'text-gray-300 hover:bg-gray-600' : 'text-gray-600 hover:bg-gray-100')
      }`}
    >
      {label}
    </button>
  );
}

// ── Rich text editor (textarea + toolbar) ───────────────────────────────────

function RichTextEditor({ value, onChange, dark }) {
  const ref = useRef(null);

  const wrap = (before, after = before) => {
    const el = ref.current;
    if (!el) return;
    const { selectionStart: s, selectionEnd: e } = el;
    const selected = value.slice(s, e);
    const next = value.slice(0, s) + before + selected + after + value.slice(e);
    onChange(next);
    setTimeout(() => { el.focus(); el.setSelectionRange(s + before.length, e + before.length); }, 0);
  };

  const insertPrefix = (prefix) => {
    const el = ref.current;
    if (!el) return;
    const { selectionStart: s } = el;
    const lineStart = value.lastIndexOf('\n', s - 1) + 1;
    const next = value.slice(0, lineStart) + prefix + value.slice(lineStart);
    onChange(next);
    setTimeout(() => { el.focus(); el.setSelectionRange(s + prefix.length, s + prefix.length); }, 0);
  };

  const inputCls = `w-full rounded-b-lg border-x border-b p-3 font-mono text-sm leading-relaxed resize-y min-h-[280px] focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset ${
    dark
      ? 'bg-gray-700 border-gray-600 text-gray-200 placeholder:text-gray-500'
      : 'bg-white border-gray-200 text-gray-800 placeholder:text-gray-400'
  }`;

  return (
    <div>
      {/* Toolbar */}
      <div className={`flex flex-wrap gap-1 rounded-t-lg border px-2 py-1.5 ${
        dark ? 'bg-gray-750 border-gray-600 bg-gray-700/80' : 'bg-gray-50 border-gray-200'
      }`}>
        <ToolbarBtn dark={dark} label="H1"   title="Heading 1"     onClick={() => insertPrefix('# ')} />
        <ToolbarBtn dark={dark} label="H2"   title="Heading 2"     onClick={() => insertPrefix('## ')} />
        <ToolbarBtn dark={dark} label="H3"   title="Heading 3"     onClick={() => insertPrefix('### ')} />
        <span className={`mx-1 w-px self-stretch ${dark ? 'bg-gray-600' : 'bg-gray-200'}`} />
        <ToolbarBtn dark={dark} label="B"    title="Bold"          onClick={() => wrap('**')} />
        <ToolbarBtn dark={dark} label="` `"  title="Inline code"   onClick={() => wrap('`')} />
        <span className={`mx-1 w-px self-stretch ${dark ? 'bg-gray-600' : 'bg-gray-200'}`} />
        <ToolbarBtn dark={dark} label="• List"  title="Bullet list"  onClick={() => insertPrefix('- ')} />
        <ToolbarBtn dark={dark} label="1. List" title="Ordered list" onClick={() => insertPrefix('1. ')} />
        <ToolbarBtn dark={dark} label="> Quote" title="Blockquote"   onClick={() => insertPrefix('> ')} />
        <span className={`mx-1 w-px self-stretch ${dark ? 'bg-gray-600' : 'bg-gray-200'}`} />
        <ToolbarBtn dark={dark} label="``` Code ```" title="Code block" onClick={() => wrap('```\n', '\n```')} />
      </div>
      <textarea
        ref={ref}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="Write your article content in Markdown…"
        className={inputCls}
      />
      <p className={`mt-1 text-xs ${dark ? 'text-gray-500' : 'text-gray-400'}`}>
        Markdown supported — use the toolbar or type directly.
      </p>
    </div>
  );
}

// ── Article form (create / edit) ────────────────────────────────────────────

const EMPTY_FORM = { title: '', category: 'onboarding', content: '', tags: [], status: 'active' };

function ArticleForm({ initial, onSave, onCancel, onDelete, dark, saving, deleting }) {
  const [form, setForm] = useState(initial || EMPTY_FORM);
  const isEdit = !!initial?.id;

  const set = (key, val) => setForm(prev => ({ ...prev, [key]: val }));

  const labelCls = `block text-xs font-semibold uppercase tracking-wide mb-1.5 ${dark ? 'text-gray-400' : 'text-gray-500'}`;
  const inputCls = `w-full rounded-lg border px-3 py-2 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 ${
    dark ? 'bg-gray-700 border-gray-600 text-gray-200 placeholder:text-gray-500' : 'bg-white border-gray-200 text-gray-800 placeholder:text-gray-400'
  }`;

  return (
    <form onSubmit={e => { e.preventDefault(); onSave(form); }} className="space-y-5">
      {/* Title */}
      <div>
        <label className={labelCls}>Title</label>
        <input
          required
          value={form.title}
          onChange={e => set('title', e.target.value)}
          placeholder="Article title…"
          className={inputCls}
        />
      </div>

      {/* Category + Status row */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelCls}>Category</label>
          <select value={form.category} onChange={e => set('category', e.target.value)} className={inputCls}>
            {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
        </div>
        <div>
          <label className={labelCls}>Status</label>
          <div className="flex items-center gap-3 mt-2">
            <StatusToggle value={form.status} onChange={v => set('status', v)} dark={dark} />
            <span className={`text-sm font-medium ${
              form.status === 'active'
                ? (dark ? 'text-green-400' : 'text-green-600')
                : (dark ? 'text-gray-400' : 'text-gray-500')
            }`}>
              {form.status === 'active' ? 'Active' : 'Draft'}
            </span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div>
        <label className={labelCls}>Content</label>
        <RichTextEditor value={form.content} onChange={v => set('content', v)} dark={dark} />
      </div>

      {/* Tags */}
      <div>
        <label className={labelCls}>Tags</label>
        <TagInput tags={form.tags} onChange={v => set('tags', v)} dark={dark} />
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between pt-2">
        <div className="flex items-center gap-2">
          <button
            type="submit"
            disabled={saving}
            className={`flex items-center gap-1.5 rounded-xl px-5 py-2.5 text-sm font-semibold text-white transition-colors disabled:opacity-60 ${
              dark ? 'bg-blue-600 hover:bg-blue-500' : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            <CheckIcon className="h-4 w-4" />
            {saving ? 'Saving…' : (isEdit ? 'Update Article' : 'Save Article')}
          </button>
          <button
            type="button"
            onClick={onCancel}
            className={`rounded-xl px-4 py-2.5 text-sm font-medium border transition-colors ${
              dark ? 'border-gray-600 text-gray-300 hover:bg-gray-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}
          >
            Cancel
          </button>
        </div>

        {isEdit && (
          <button
            type="button"
            onClick={() => onDelete(form.id)}
            disabled={deleting}
            className={`flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-sm font-semibold border transition-colors disabled:opacity-60 ${
              dark
                ? 'border-red-700 text-red-400 hover:bg-red-900/30'
                : 'border-red-200 text-red-600 hover:bg-red-50'
            }`}
          >
            <TrashIcon className="h-4 w-4" />
            {deleting ? 'Deleting…' : 'Delete Article'}
          </button>
        )}
      </div>
    </form>
  );
}

// ── Preview panel ───────────────────────────────────────────────────────────

function PreviewPanel({ article, searchQuery, dark }) {
  const text   = dark ? 'text-gray-100' : 'text-gray-900';
  const muted  = dark ? 'text-gray-400' : 'text-gray-500';
  const border = dark ? 'border-gray-700' : 'border-gray-200';

  const matchCount = useMemo(() => {
    if (!searchQuery) return 0;
    const re = new RegExp(searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    return (article.content.match(re) || []).length + (article.title.match(re) || []).length;
  }, [article, searchQuery]);

  return (
    <div className="space-y-4">
      {/* Preview header */}
      <div className={`rounded-xl border p-4 ${dark ? 'bg-gray-700/40 border-gray-600' : 'bg-blue-50 border-blue-200'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <EyeIcon className={`h-4 w-4 ${dark ? 'text-blue-400' : 'text-blue-600'}`} />
            <span className={`text-xs font-semibold uppercase tracking-wide ${dark ? 'text-blue-400' : 'text-blue-600'}`}>
              Customer Preview
            </span>
          </div>
          {searchQuery && (
            <span className={`text-xs font-medium ${dark ? 'text-gray-400' : 'text-gray-500'}`}>
              {matchCount > 0
                ? <span className="text-green-500">{matchCount} match{matchCount !== 1 ? 'es' : ''} for "{searchQuery}"</span>
                : <span className="text-red-500">No matches for "{searchQuery}"</span>}
            </span>
          )}
        </div>
        <p className={`text-xs mt-1 ${muted}`}>This is how customers see this article in the help centre.</p>
      </div>

      {/* Rendered article */}
      <div className={`rounded-2xl border overflow-hidden ${dark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-100 shadow-sm'}`}>

        {/* Article meta bar */}
        <div className={`px-6 py-4 border-b ${border} flex flex-wrap items-center gap-3`}>
          <CategoryBadge category={article.category} dark={dark} />
          <span className={`text-xs ${muted}`}>Updated {relativeDate(article.updated_at)}</span>
          <span className={`text-xs ${muted}`}>·</span>
          <span className={`text-xs ${muted}`}>{article.view_count.toLocaleString()} views</span>
          {article.status === 'draft' && (
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${dark ? 'bg-amber-900/40 text-amber-300' : 'bg-amber-100 text-amber-700'}`}>
              Draft — not visible to customers
            </span>
          )}
        </div>

        {/* Rendered markdown content */}
        <div className={`px-6 py-6 prose max-w-none ${dark ? 'text-gray-200' : 'text-gray-800'}`}>
          <h1
            className={`text-2xl font-bold mb-4 ${text}`}
            dangerouslySetInnerHTML={{ __html: highlight(article.title, searchQuery) }}
          />
          <div
            className="article-body"
            dangerouslySetInnerHTML={{ __html: highlight(renderMarkdown(article.content), searchQuery) }}
          />
        </div>

        {/* Tags */}
        {article.tags?.length > 0 && (
          <div className={`px-6 py-4 border-t ${border} flex flex-wrap gap-2`}>
            {article.tags.map(tag => (
              <span key={tag} className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                dark ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-600'
              }`}>
                <TagIcon className="h-3 w-3" />
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

export default function KnowledgeBaseManager({ apiBase = '' }) {
  const [dark,       setDark]       = useState(false);
  const [articles,   setArticles]   = useState(MOCK_ARTICLES);
  const [search,     setSearch]     = useState('');
  const [catFilter,  setCatFilter]  = useState('all');
  const [panel,      setPanel]      = useState('list');   // 'list' | 'new' | 'edit' | 'preview'
  const [selected,   setSelected]   = useState(null);     // article being edited / previewed
  const [saving,     setSaving]     = useState(false);
  const [deleting,   setDeleting]   = useState(false);
  const [toast,      setToast]      = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null); // article id pending confirm

  // ── API helpers ────────────────────────────────────────────────────────

  const fetchArticles = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/api/kb/articles`);
      if (res.ok) setArticles(await res.json());
    } catch { /* keep mock */ }
  }, [apiBase]);

  useEffect(() => { fetchArticles(); }, [fetchArticles]);

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  };

  // ── Create ─────────────────────────────────────────────────────────────

  const handleCreate = async (form) => {
    setSaving(true);
    try {
      const res = await fetch(`${apiBase}/api/kb/articles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const created = res.ok ? await res.json() : { ...form, id: `art-${Date.now()}`, view_count: 0, updated_at: new Date().toISOString() };
      setArticles(prev => [created, ...prev]);
      setPanel('list');
      showToast('Article created successfully.');
    } catch {
      showToast('Failed to create article.', 'error');
    } finally {
      setSaving(false);
    }
  };

  // ── Update ─────────────────────────────────────────────────────────────

  const handleUpdate = async (form) => {
    setSaving(true);
    try {
      const res = await fetch(`${apiBase}/api/kb/articles/${form.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const updated = res.ok ? await res.json() : { ...form, updated_at: new Date().toISOString() };
      setArticles(prev => prev.map(a => a.id === updated.id ? updated : a));
      setPanel('list');
      showToast('Article updated successfully.');
    } catch {
      showToast('Failed to update article.', 'error');
    } finally {
      setSaving(false);
    }
  };

  // ── Delete ─────────────────────────────────────────────────────────────

  const handleDelete = async (id) => {
    setDeleteConfirm(null);
    setDeleting(true);
    try {
      await fetch(`${apiBase}/api/kb/articles/${id}`, { method: 'DELETE' });
      setArticles(prev => prev.filter(a => a.id !== id));
      setPanel('list');
      showToast('Article deleted.');
    } catch {
      showToast('Failed to delete article.', 'error');
    } finally {
      setDeleting(false);
    }
  };

  // ── Filtered list ──────────────────────────────────────────────────────

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return articles.filter(a => {
      if (catFilter !== 'all' && a.category !== catFilter) return false;
      if (!q) return true;
      return (
        a.title.toLowerCase().includes(q) ||
        a.content.toLowerCase().includes(q) ||
        a.tags.some(t => t.includes(q))
      );
    });
  }, [articles, search, catFilter]);

  // ── Theme ──────────────────────────────────────────────────────────────

  const bg      = dark ? 'bg-gray-900'  : 'bg-gray-50';
  const card    = dark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-100 shadow-sm';
  const text    = dark ? 'text-gray-100' : 'text-gray-900';
  const muted   = dark ? 'text-gray-400' : 'text-gray-500';
  const divider = dark ? 'border-gray-700' : 'border-gray-100';
  const hover   = dark ? 'hover:bg-gray-700/50' : 'hover:bg-gray-50';
  const inputCls = `rounded-lg border px-3 py-1.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 ${
    dark ? 'bg-gray-700 border-gray-600 text-gray-200 placeholder:text-gray-500' : 'bg-white border-gray-200 text-gray-700 placeholder:text-gray-400'
  }`;

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <>
      <style>{`
        @keyframes fadeIn  { from { opacity:0; transform:translateY(6px) } to { opacity:1; transform:translateY(0) } }
        @keyframes toastIn { from { opacity:0; transform:translateY(16px) } to { opacity:1; transform:translateY(0) } }
        .fade-in  { animation: fadeIn  0.3s ease both }
        .toast-in { animation: toastIn 0.3s ease both }
      `}</style>

      <div className={`min-h-screen ${bg} transition-colors duration-300`}>
        <div className="mx-auto max-w-7xl px-4 py-6 space-y-5">

          {/* ── Page header ───────────────────────────────────────── */}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${dark ? 'bg-blue-900/40' : 'bg-blue-100'}`}>
                <BookIcon className={`h-5 w-5 ${dark ? 'text-blue-400' : 'text-blue-600'}`} />
              </div>
              <div>
                <h1 className={`text-xl font-bold ${text}`}>Knowledge Base</h1>
                <p className={`text-xs ${muted} mt-0.5`}>{articles.length} articles · {articles.filter(a => a.status === 'active').length} active</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setDark(d => !d)}
                className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                  dark ? 'border-gray-600 bg-gray-700 text-gray-300 hover:bg-gray-600' : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50 shadow-sm'
                }`}
              >
                {dark ? <SunIcon className="h-4 w-4" /> : <MoonIcon className="h-4 w-4" />}
                {dark ? 'Light' : 'Dark'}
              </button>

              {panel === 'list' && (
                <button
                  onClick={() => { setSelected(null); setPanel('new'); }}
                  className="flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-700 transition-colors shadow-sm"
                >
                  <PlusIcon className="h-4 w-4" />
                  New Article
                </button>
              )}
            </div>
          </div>

          {/* ── List panel ────────────────────────────────────────── */}
          {panel === 'list' && (
            <div className="space-y-4 fade-in">

              {/* Search + Filter bar */}
              <div className={`rounded-2xl border p-4 flex flex-wrap gap-3 items-center ${card}`}>
                <div className="relative flex-1 min-w-[200px]">
                  <SearchIcon className={`absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 ${muted}`} />
                  <input
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    placeholder="Search articles by title, content, or tag…"
                    className={`${inputCls} w-full pl-9`}
                  />
                  {search && (
                    <button onClick={() => setSearch('')} className={`absolute right-3 top-1/2 -translate-y-1/2 ${muted} hover:text-red-500`}>
                      <XIcon className="h-4 w-4" />
                    </button>
                  )}
                </div>

                <select value={catFilter} onChange={e => setCatFilter(e.target.value)} className={inputCls}>
                  <option value="all">All Categories</option>
                  {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>

                {(search || catFilter !== 'all') && (
                  <span className={`text-xs ${muted}`}>
                    {filtered.length} result{filtered.length !== 1 ? 's' : ''}
                  </span>
                )}
              </div>

              {/* Articles table */}
              <div className={`rounded-2xl border overflow-hidden ${card}`}>
                {/* Column headers */}
                <div className={`hidden md:grid grid-cols-[2fr_0.9fr_0.8fr_0.7fr_0.6fr_0.9fr] gap-0 px-5 py-3 border-b ${divider}`}>
                  {['Title', 'Category', 'Last Updated', 'Status', 'Views', 'Actions'].map(h => (
                    <span key={h} className={`text-xs font-semibold uppercase tracking-wide ${muted}`}>{h}</span>
                  ))}
                </div>

                {filtered.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-16 gap-3">
                    <SearchIcon className={`h-8 w-8 ${muted}`} />
                    <p className={`text-sm font-medium ${text}`}>No articles found</p>
                    <p className={`text-xs ${muted}`}>Try adjusting your search or filters</p>
                  </div>
                ) : (
                  <div className="divide-y divide-transparent">
                    {filtered.map((article, i) => (
                      <div
                        key={article.id}
                        className={`grid grid-cols-1 md:grid-cols-[2fr_0.9fr_0.8fr_0.7fr_0.6fr_0.9fr] gap-3 md:gap-0 px-5 py-4 border-b ${divider} ${hover} transition-colors fade-in`}
                        style={{ animationDelay: `${i * 25}ms` }}
                      >
                        {/* Title */}
                        <div className="flex flex-col justify-center min-w-0">
                          <span
                            className={`text-sm font-semibold ${text} truncate`}
                            dangerouslySetInnerHTML={{ __html: highlight(article.title, search) }}
                          />
                          {article.tags?.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-1">
                              {article.tags.slice(0, 3).map(tag => (
                                <span key={tag} className={`text-xs px-1.5 py-0.5 rounded ${
                                  dark ? 'bg-gray-700 text-gray-400' : 'bg-gray-100 text-gray-500'
                                }`}>{tag}</span>
                              ))}
                              {article.tags.length > 3 && <span className={`text-xs ${muted}`}>+{article.tags.length - 3}</span>}
                            </div>
                          )}
                        </div>

                        {/* Category */}
                        <div className="flex items-center">
                          <CategoryBadge category={article.category} dark={dark} />
                        </div>

                        {/* Last updated */}
                        <div className="flex items-center">
                          <span className={`text-xs ${muted}`}>{relativeDate(article.updated_at)}</span>
                        </div>

                        {/* Status */}
                        <div className="flex items-center">
                          <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                            article.status === 'active'
                              ? (dark ? 'bg-green-900/40 text-green-300' : 'bg-green-100 text-green-700')
                              : (dark ? 'bg-gray-700 text-gray-400' : 'bg-gray-100 text-gray-500')
                          }`}>
                            <span className={`h-1.5 w-1.5 rounded-full ${article.status === 'active' ? 'bg-green-500' : 'bg-gray-400'}`} />
                            {article.status === 'active' ? 'Active' : 'Draft'}
                          </span>
                        </div>

                        {/* Views */}
                        <div className="flex items-center">
                          <span className={`text-xs font-mono ${muted}`}>{article.view_count.toLocaleString()}</span>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => { setSelected(article); setPanel('preview'); }}
                            title="Preview"
                            className={`flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium border transition-colors ${
                              dark ? 'border-gray-600 text-gray-300 hover:bg-gray-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                            }`}
                          >
                            <EyeIcon className="h-3.5 w-3.5" />
                            Preview
                          </button>
                          <button
                            onClick={() => { setSelected(article); setPanel('edit'); }}
                            title="Edit"
                            className={`flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium border transition-colors ${
                              dark ? 'border-blue-700 text-blue-400 hover:bg-blue-900/30' : 'border-blue-200 text-blue-600 hover:bg-blue-50'
                            }`}
                          >
                            <EditIcon className="h-3.5 w-3.5" />
                            Edit
                          </button>
                          <button
                            onClick={() => setDeleteConfirm(article.id)}
                            title="Delete"
                            className={`flex items-center gap-1 rounded-lg p-1.5 text-xs border transition-colors ${
                              dark ? 'border-gray-600 text-gray-500 hover:border-red-700 hover:text-red-400' : 'border-gray-200 text-gray-400 hover:border-red-200 hover:text-red-500'
                            }`}
                          >
                            <TrashIcon className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Footer */}
                <div className={`px-5 py-3 border-t ${divider} flex items-center justify-between`}>
                  <span className={`text-xs ${muted}`}>{articles.filter(a => a.status === 'active').length} active · {articles.filter(a => a.status === 'draft').length} drafts</span>
                  <span className={`text-xs ${muted}`}>{articles.reduce((s, a) => s + a.view_count, 0).toLocaleString()} total views</span>
                </div>
              </div>
            </div>
          )}

          {/* ── New Article panel ─────────────────────────────────── */}
          {panel === 'new' && (
            <div className={`rounded-2xl border p-6 fade-in ${card}`}>
              <div className="flex items-center justify-between mb-6">
                <h2 className={`text-base font-bold ${text}`}>New Article</h2>
                <button onClick={() => setPanel('list')} className={`${muted} hover:text-red-500 transition-colors`}>
                  <XIcon className="h-5 w-5" />
                </button>
              </div>
              <ArticleForm
                onSave={handleCreate}
                onCancel={() => setPanel('list')}
                dark={dark}
                saving={saving}
              />
            </div>
          )}

          {/* ── Edit Article panel ────────────────────────────────── */}
          {panel === 'edit' && selected && (
            <div className={`rounded-2xl border p-6 fade-in ${card}`}>
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className={`text-base font-bold ${text}`}>Edit Article</h2>
                  <p className={`text-xs ${muted} mt-0.5`}>{selected.title}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPanel('preview')}
                    className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                      dark ? 'border-gray-600 text-gray-300 hover:bg-gray-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <EyeIcon className="h-4 w-4" />
                    Preview
                  </button>
                  <button onClick={() => setPanel('list')} className={`${muted} hover:text-red-500 transition-colors`}>
                    <XIcon className="h-5 w-5" />
                  </button>
                </div>
              </div>
              <ArticleForm
                initial={selected}
                onSave={handleUpdate}
                onCancel={() => setPanel('list')}
                onDelete={(id) => setDeleteConfirm(id)}
                dark={dark}
                saving={saving}
                deleting={deleting}
              />
            </div>
          )}

          {/* ── Preview panel ─────────────────────────────────────── */}
          {panel === 'preview' && selected && (
            <div className="space-y-4 fade-in">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPanel('list')}
                    className={`rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                      dark ? 'border-gray-600 text-gray-300 hover:bg-gray-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    ← Back to List
                  </button>
                  <button
                    onClick={() => setPanel('edit')}
                    className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                      dark ? 'border-blue-700 text-blue-400 hover:bg-blue-900/30' : 'border-blue-200 text-blue-600 hover:bg-blue-50'
                    }`}
                  >
                    <EditIcon className="h-3.5 w-3.5" />
                    Edit Article
                  </button>
                </div>

                {/* Test search in preview */}
                <div className="relative">
                  <SearchIcon className={`absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 ${muted}`} />
                  <input
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    placeholder="Test search match…"
                    className={`${inputCls} pl-9 w-56`}
                  />
                </div>
              </div>

              <PreviewPanel article={selected} searchQuery={search} dark={dark} />
            </div>
          )}

        </div>
      </div>

      {/* ── Delete confirmation modal ──────────────────────────────── */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className={`rounded-2xl border p-6 w-full max-w-sm shadow-2xl fade-in ${card}`}>
            <div className={`flex h-12 w-12 items-center justify-center rounded-full mb-4 ${dark ? 'bg-red-900/40' : 'bg-red-100'}`}>
              <TrashIcon className={`h-6 w-6 ${dark ? 'text-red-400' : 'text-red-600'}`} />
            </div>
            <h3 className={`text-base font-bold ${text} mb-1`}>Delete Article?</h3>
            <p className={`text-sm ${muted} mb-5`}>
              This action cannot be undone. The article will be permanently removed from the knowledge base.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => handleDelete(deleteConfirm)}
                className="flex-1 rounded-xl bg-red-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-700 transition-colors"
              >
                Yes, Delete
              </button>
              <button
                onClick={() => setDeleteConfirm(null)}
                className={`flex-1 rounded-xl border px-4 py-2.5 text-sm font-medium transition-colors ${
                  dark ? 'border-gray-600 text-gray-300 hover:bg-gray-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                }`}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Toast ───────────────────────────────────────────────────── */}
      {toast && (
        <div className={`fixed bottom-6 right-6 z-50 toast-in flex items-center gap-2.5 rounded-xl px-4 py-3 text-sm font-medium shadow-lg ${
          toast.type === 'success'
            ? (dark ? 'bg-green-800 text-green-100' : 'bg-green-600 text-white')
            : (dark ? 'bg-red-800 text-red-100'     : 'bg-red-600 text-white')
        }`}>
          {toast.type === 'success'
            ? <CheckIcon className="h-4 w-4" />
            : <XIcon className="h-4 w-4" />}
          {toast.message}
        </div>
      )}
    </>
  );
}
