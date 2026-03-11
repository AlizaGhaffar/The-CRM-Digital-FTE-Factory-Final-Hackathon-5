/**
 * frontend/services/api.js
 *
 * NimbusFlow — Centralised API client
 *
 * All API calls go through this module. Each function:
 *   - Prepends BASE_URL (env var or empty string for same-origin)
 *   - Attaches auth header from token store
 *   - Normalises errors into ApiError instances
 *   - Falls back to mock data when the server is unreachable (dev mode)
 *
 * Usage:
 *   import api from '@/services/api';
 *   const metrics = await api.getDashboardMetrics();
 *
 * Environment variables (Next.js / Vite):
 *   NEXT_PUBLIC_API_BASE  or  VITE_API_BASE  — defaults to ''
 */

// ── Config ─────────────────────────────────────────────────────────────────

const BASE_URL =
  (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_API_BASE) ||
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE) ||
  '';

const DEFAULT_TIMEOUT_MS = 15_000;

// ── Token store (swap for your auth solution) ───────────────────────────────

const token = {
  get()  { return typeof localStorage !== 'undefined' ? localStorage.getItem('nf_token') : null; },
  set(t) { if (typeof localStorage !== 'undefined') localStorage.setItem('nf_token', t); },
  clear(){ if (typeof localStorage !== 'undefined') localStorage.removeItem('nf_token'); },
};

// ── ApiError ────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name   = 'ApiError';
    this.status = status;   // HTTP status code (or 0 for network errors)
    this.body   = body;     // parsed JSON body if available
  }
}

// ── Core fetch wrapper ──────────────────────────────────────────────────────

async function request(method, path, { body, params, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  const url = new URL(`${BASE_URL}${path}`, window?.location?.href ?? 'http://localhost');
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, v);
    });
  }

  const headers = { 'Content-Type': 'application/json', Accept: 'application/json' };
  const tok = token.get();
  if (tok) headers['Authorization'] = `Bearer ${tok}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response;
  try {
    response = await fetch(url.toString(), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if (err.name === 'AbortError') throw new ApiError('Request timed out', 0, null);
    throw new ApiError(err.message ?? 'Network error', 0, null);
  } finally {
    clearTimeout(timer);
  }

  if (response.status === 401) { token.clear(); }

  // Parse body (may be empty on 204)
  let parsed = null;
  const ct = response.headers.get('content-type') ?? '';
  if (ct.includes('application/json') && response.status !== 204) {
    try { parsed = await response.json(); } catch { /* ignore */ }
  }

  if (!response.ok) {
    const msg = parsed?.detail ?? parsed?.message ?? parsed?.error ?? `HTTP ${response.status}`;
    throw new ApiError(msg, response.status, parsed);
  }

  return parsed;
}

const get  = (path, opts)       => request('GET',    path, opts);
const post = (path, body, opts) => request('POST',   path, { body, ...opts });
const put  = (path, body, opts) => request('PUT',    path, { body, ...opts });
const del  = (path, opts)       => request('DELETE', path, opts);

// ── Mock data (returned when server is unreachable in development) ───────────

const IS_DEV = typeof process !== 'undefined'
  ? process.env.NODE_ENV !== 'production'
  : true;

function mockFallback(fn) {
  return async (...args) => {
    try {
      return await fn(...args);
    } catch (err) {
      if (IS_DEV && (err.status === 0 || err.status === 404)) {
        console.warn(`[api] Falling back to mock for: ${fn.name}`);
        return MOCKS[fn.name]?.(...args) ?? null;
      }
      throw err;
    }
  };
}

// ── Mock implementations ────────────────────────────────────────────────────

const MOCKS = {

  submitTicket: (formData) => ({
    ticket_id: `TKT-${Date.now()}`,
    status:    'open',
    message:   'Ticket created successfully.',
    created_at: new Date().toISOString(),
    ...formData,
  }),

  getTicketStatus: (ticketId) => ({
    ticket_id:    ticketId,
    status:       'in_progress',
    subject:      'GitHub integration not syncing',
    channel:      'email',
    priority:     'high',
    customer_email: 'alice@corp.com',
    created_at:   new Date(Date.now() - 25 * 60000).toISOString(),
    updated_at:   new Date(Date.now() - 5  * 60000).toISOString(),
    messages: [
      { role: 'customer', content: 'My GitHub integration stopped syncing yesterday.', ts: new Date(Date.now() - 25 * 60000).toISOString() },
      { role: 'ai',       content: 'I can help with that. Could you confirm which repo is affected?', ts: new Date(Date.now() - 24 * 60000).toISOString() },
      { role: 'customer', content: 'All repos. It was working fine before the update.', ts: new Date(Date.now() - 20 * 60000).toISOString() },
    ],
  }),

  getDashboardMetrics: () => ({
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
  }),

  getRecentTickets: (limit = 10) => ({
    tickets: Array.from({ length: Math.min(limit, 6) }, (_, i) => ({
      ticket_id:      `tid-${i + 1}`,
      customer_email: ['alice@corp.com','bob@startup.io','carol@tech.dev','dave@bigco.com','eve@design.co','frank@media.io'][i],
      channel:        ['email','whatsapp','web_form','email','whatsapp','web_form'][i],
      subject:        ['GitHub integration not syncing','API rate limit exceeded','Cannot export CSV','SSO config help','Dashboard charts broken','Billing cycle question'][i],
      status:         ['open','in_progress','resolved','escalated','open','open'][i],
      priority:       ['high','high','medium','high','medium','low'][i],
      created_at:     new Date(Date.now() - (i + 1) * 15 * 60000).toISOString(),
    })),
    total: 1284,
    page:  1,
  }),

  getActivityFeed: () => ({
    events: [
      { id: 1, type: 'ticket_opened',   channel: 'email',    message: 'alice@corp.com opened a new ticket',        time: new Date(Date.now() - 2 * 60000).toISOString() },
      { id: 2, type: 'escalated',       channel: 'whatsapp', message: 'dave@bigco.com escalated to human agent',   time: new Date(Date.now() - 5 * 60000).toISOString() },
      { id: 3, type: 'resolved',        channel: 'web_form', message: 'carol@tech.dev ticket resolved by AI',      time: new Date(Date.now() - 9 * 60000).toISOString() },
      { id: 4, type: 'ticket_opened',   channel: 'whatsapp', message: 'bob@startup.io opened a new ticket',        time: new Date(Date.now() - 14 * 60000).toISOString() },
      { id: 5, type: 'sentiment_alert', channel: 'email',    message: 'Low sentiment (0.22) detected — monitoring', time: new Date(Date.now() - 31 * 60000).toISOString() },
    ],
  }),

  getEscalations: () => ([
    { ticket_id: 'esc-001', customer_name: 'Alice Nguyen', customer_email: 'alice@corp.com', channel: 'email', priority: 'high', escalation_reason: 'billing_dispute', wait_since: new Date(Date.now() - 52 * 60000).toISOString(), last_customer_msg: 'I was charged twice this month.', ai_response: 'Thank you for reaching out…', why_escalated: 'Customer requested human. Confidence: 0.31.' },
    { ticket_id: 'esc-002', customer_name: 'Bob Martinez', customer_email: 'bob@startup.io', channel: 'whatsapp', priority: 'high', escalation_reason: 'technical_complexity', wait_since: new Date(Date.now() - 18 * 60000).toISOString(), last_customer_msg: 'Webhook is failing silently.', ai_response: 'Webhook delivery issues can be caused by…', why_escalated: 'Multi-step debugging exceeded AI capability.' },
  ]),

  getConversation: (ticketId) => ({
    ticket_id: ticketId,
    customer:  { name: 'Alice Nguyen', email: 'alice@corp.com', channel: 'email' },
    messages:  [
      { id: 'msg-1', role: 'customer', content: 'My GitHub integration stopped syncing.', timestamp: new Date(Date.now() - 25 * 60000).toISOString(), channel: 'email' },
      { id: 'msg-2', role: 'ai',       content: 'I can help. Which repository is affected?',  timestamp: new Date(Date.now() - 24 * 60000).toISOString(), channel: 'email' },
      { id: 'msg-3', role: 'customer', content: 'All repos — it broke after the last update.', timestamp: new Date(Date.now() - 20 * 60000).toISOString(), channel: 'email' },
    ],
    status: 'in_progress',
  }),

  respondToTicket: (ticketId, message) => ({
    message_id: `msg-${Date.now()}`,
    ticket_id:  ticketId,
    content:    message,
    role:       'agent',
    timestamp:  new Date().toISOString(),
  }),

  escalateTicket: (ticketId) => ({
    ticket_id: ticketId,
    status:    'escalated',
    escalated_at: new Date().toISOString(),
  }),

  resolveTicket: (ticketId) => ({
    ticket_id:   ticketId,
    status:      'resolved',
    resolved_at: new Date().toISOString(),
  }),

  getKnowledgeBase: () => ({
    articles: [
      { id: 'art-001', title: 'Getting Started with NimbusFlow', category: 'onboarding', status: 'active', tags: ['setup','quickstart'], view_count: 4821, updated_at: new Date(Date.now() - 2 * 86400000).toISOString(), content: '# Getting Started\n\nWelcome to NimbusFlow…' },
      { id: 'art-002', title: 'How to Reset Your Password',       category: 'account',    status: 'active', tags: ['password','login'],  view_count: 3102, updated_at: new Date(Date.now() - 5 * 86400000).toISOString(), content: '# Password Reset\n\nFollow these steps…' },
    ],
    total: 2,
  }),

  createKbArticle: (data) => ({
    id:         `art-${Date.now()}`,
    view_count: 0,
    updated_at: new Date().toISOString(),
    ...data,
  }),

  updateKbArticle: (id, data) => ({
    id,
    updated_at: new Date().toISOString(),
    ...data,
  }),

  deleteKbArticle: () => ({ success: true }),

  getChannelMetrics: () => ({
    email:    { count: 612, avg_sentiment: 0.48, escalation_rate: 22.1, avg_response_ms: 2100, resolved: 477 },
    whatsapp: { count: 418, avg_sentiment: 0.73, escalation_rate: 12.4, avg_response_ms: 1400, resolved: 366 },
    web_form: { count: 254, avg_sentiment: 0.61, escalation_rate: 21.3, avg_response_ms: 1900, resolved: 200 },
  }),

  getAnalytics: (range = 'week') => ({
    range,
    generated_at: new Date().toISOString(),
    summary: { total_tickets: 387, resolved: 298, escalated: 72, avg_response_ms: 1840, csat: 4.2 },
    volume_by_day: [
      { day: 'Mon', email: 52, whatsapp: 38, web: 21 },
      { day: 'Tue', email: 67, whatsapp: 44, web: 29 },
      { day: 'Wed', email: 58, whatsapp: 51, web: 34 },
      { day: 'Thu', email: 71, whatsapp: 39, web: 28 },
      { day: 'Fri', email: 83, whatsapp: 62, web: 41 },
      { day: 'Sat', email: 29, whatsapp: 18, web: 12 },
      { day: 'Sun', email: 21, whatsapp: 12, web:  8 },
    ],
    sentiment_trend: [
      { day: 'Mon', score: 0.61 }, { day: 'Tue', score: 0.58 }, { day: 'Wed', score: 0.64 },
      { day: 'Thu', score: 0.55 }, { day: 'Fri', score: 0.67 }, { day: 'Sat', score: 0.71 }, { day: 'Sun', score: 0.69 },
    ],
  }),
};

// ── Public API ──────────────────────────────────────────────────────────────

/**
 * 1. Submit a new support ticket.
 * @param {{ name: string, email: string, subject: string, message: string, channel?: string }} formData
 */
async function submitTicket(formData) {
  return post('/support/submit', formData);
}

/**
 * 2. Get the status and conversation of a specific ticket.
 * @param {string} ticketId
 */
async function getTicketStatus(ticketId) {
  return get(`/support/ticket/${encodeURIComponent(ticketId)}`);
}

/**
 * 3. Get real-time dashboard metrics.
 */
async function getDashboardMetrics() {
  return get('/metrics/dashboard');
}

/**
 * 4. Get recent tickets list.
 * @param {number} [limit=10]
 */
async function getRecentTickets(limit = 10) {
  return get('/tickets/recent', { params: { limit } });
}

/**
 * 5. Get live activity feed events.
 */
async function getActivityFeed() {
  return get('/activity/live');
}

/**
 * 6. Get all escalated tickets awaiting human review.
 */
async function getEscalations() {
  return get('/escalations');
}

/**
 * 7. Get full conversation thread for a ticket.
 * @param {string} ticketId
 */
async function getConversation(ticketId) {
  return get(`/conversations/${encodeURIComponent(ticketId)}`);
}

/**
 * 8. Post a human agent reply to a ticket.
 * @param {string} ticketId
 * @param {string} message
 */
async function respondToTicket(ticketId, message) {
  return post(`/tickets/${encodeURIComponent(ticketId)}/respond`, { message });
}

/**
 * 9. Escalate a ticket to a human agent.
 * @param {string} ticketId
 * @param {string} [reason='Manual escalation']
 */
async function escalateTicket(ticketId, reason = 'Manual escalation') {
  return post(`/tickets/${encodeURIComponent(ticketId)}/escalate`, { reason });
}

/**
 * 10. Mark a ticket as resolved.
 * @param {string} ticketId
 */
async function resolveTicket(ticketId) {
  return post(`/tickets/${encodeURIComponent(ticketId)}/resolve`);
}

/**
 * 11. Get all knowledge base articles.
 * @param {{ category?: string, status?: string, q?: string }} [filters]
 */
async function getKnowledgeBase(filters) {
  return get('/kb/articles', { params: filters });
}

/**
 * 12. Create a new KB article.
 * @param {{ title: string, category: string, content: string, tags: string[], status: string }} data
 */
async function createKbArticle(data) {
  return post('/kb/articles', data);
}

/**
 * 13. Update an existing KB article.
 * @param {string} id
 * @param {Partial<{title,category,content,tags,status}>} data
 */
async function updateKbArticle(id, data) {
  return put(`/kb/articles/${encodeURIComponent(id)}`, data);
}

/**
 * 14. Delete a KB article.
 * @param {string} id
 */
async function deleteKbArticle(id) {
  return del(`/kb/articles/${encodeURIComponent(id)}`);
}

/**
 * 15. Get per-channel performance metrics.
 */
async function getChannelMetrics() {
  return get('/metrics/channels');
}

/**
 * 16. Get analytics data for a time range.
 * @param {'today'|'week'|'month'|'custom'} range
 * @param {{ from?: string, to?: string }} [custom]
 */
async function getAnalytics(range = 'week', custom = {}) {
  return get('/analytics', { params: { range, ...custom } });
}

// ── Wrap every function with mock fallback in dev ───────────────────────────

const api = {
  submitTicket:       mockFallback(submitTicket),
  getTicketStatus:    mockFallback(getTicketStatus),
  getDashboardMetrics:mockFallback(getDashboardMetrics),
  getRecentTickets:   mockFallback(getRecentTickets),
  getActivityFeed:    mockFallback(getActivityFeed),
  getEscalations:     mockFallback(getEscalations),
  getConversation:    mockFallback(getConversation),
  respondToTicket:    mockFallback(respondToTicket),
  escalateTicket:     mockFallback(escalateTicket),
  resolveTicket:      mockFallback(resolveTicket),
  getKnowledgeBase:   mockFallback(getKnowledgeBase),
  createKbArticle:    mockFallback(createKbArticle),
  updateKbArticle:    mockFallback(updateKbArticle),
  deleteKbArticle:    mockFallback(deleteKbArticle),
  getChannelMetrics:  mockFallback(getChannelMetrics),
  getAnalytics:       mockFallback(getAnalytics),

  // Auth helpers
  token,
  ApiError,
};

export default api;

// Named exports for tree-shaking
export {
  submitTicket,
  getTicketStatus,
  getDashboardMetrics,
  getRecentTickets,
  getActivityFeed,
  getEscalations,
  getConversation,
  respondToTicket,
  escalateTicket,
  resolveTicket,
  getKnowledgeBase,
  createKbArticle,
  updateKbArticle,
  deleteKbArticle,
  getChannelMetrics,
  getAnalytics,
};
