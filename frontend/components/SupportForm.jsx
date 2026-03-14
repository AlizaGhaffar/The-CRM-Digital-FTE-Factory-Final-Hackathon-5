/**
 * frontend/components/SupportForm.jsx
 *
 * NimbusFlow — Customer Support Form (REQUIRED Web Support Form)
 * Clean, modern design with gradient background and smooth animations.
 *
 * Usage (Next.js):
 *   import SupportForm from '@/components/SupportForm';
 *   export default function SupportPage() {
 *     return <SupportForm apiEndpoint="/support/submit" />;
 *   }
 *
 * Requirements: React 18+, Tailwind CSS
 */

import { useState, useEffect, useCallback } from 'react';

// ── Data ───────────────────────────────────────────────────────────────────

const CATEGORIES = [
  { value: '',            label: 'Select a category…' },
  { value: 'general',    label: '💬  General Question' },
  { value: 'technical',  label: '🔧  Technical Support' },
  { value: 'billing',    label: '💳  Billing Inquiry' },
  { value: 'bug_report', label: '🐛  Bug Report' },
  { value: 'feedback',   label: '⭐  Feedback' },
];

const PRIORITIES = [
  { value: 'low',    label: '🟢  Low — Not urgent',       color: 'text-green-600' },
  { value: 'medium', label: '🟡  Medium — Need help soon', color: 'text-yellow-600' },
  { value: 'high',   label: '🔴  High — Urgent issue',    color: 'text-red-600' },
];

const MESSAGE_MAX = 1000;
const MESSAGE_MIN = 10;
const EMAIL_RE    = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const INITIAL = {
  name: '', email: '', subject: '',
  category: '', priority: 'medium', message: '',
};

// ── Validate ───────────────────────────────────────────────────────────────

function validate(f) {
  const e = {};
  if (!f.name.trim())                      e.name    = 'Full name is required.';
  else if (f.name.trim().length < 2)       e.name    = 'At least 2 characters.';
  if (!f.email.trim())                     e.email   = 'Email is required.';
  else if (!EMAIL_RE.test(f.email.trim())) e.email   = 'Enter a valid email address.';
  if (!f.subject.trim())                   e.subject = 'Subject is required.';
  else if (f.subject.trim().length < 5)    e.subject = 'At least 5 characters.';
  if (!f.category)                         e.category= 'Please choose a category.';
  if (!f.message.trim())                   e.message = 'Message is required.';
  else if (f.message.trim().length < MESSAGE_MIN) e.message = `At least ${MESSAGE_MIN} characters.`;
  else if (f.message.length > MESSAGE_MAX)        e.message = `Max ${MESSAGE_MAX} characters.`;
  return e;
}

// ── Tiny helpers ───────────────────────────────────────────────────────────

function FieldError({ msg }) {
  if (!msg) return null;
  return (
    <p className="mt-1.5 flex items-center gap-1 text-xs text-red-500 animate-fadeIn">
      <svg className="w-3 h-3 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd"/>
      </svg>
      {msg}
    </p>
  );
}

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
    </svg>
  );
}

// ── Success view ───────────────────────────────────────────────────────────

function SuccessView({ ticketId, estimatedTime, onReset }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 px-6 text-center animate-fadeIn">

      {/* Animated checkmark */}
      <div className="relative mb-6">
        <div className="absolute inset-0 rounded-full bg-green-400 opacity-20 animate-ping" />
        <div className="relative flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-green-400 to-emerald-500 shadow-lg shadow-green-200">
          <svg className="h-10 w-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
          </svg>
        </div>
      </div>

      <h2 className="text-2xl font-bold text-gray-900 mb-1">You're all set!</h2>
      <p className="text-gray-500 text-sm mb-8 max-w-xs">
        Our AI support team received your request and will respond shortly.
      </p>

      {/* Ticket card */}
      <div className="w-full max-w-sm rounded-2xl border border-gray-100 bg-gray-50 p-5 mb-6 text-left shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs font-semibold uppercase tracking-widest text-gray-400">
            Ticket Created
          </span>
        </div>
        <p className="font-mono text-sm font-bold text-gray-800 break-all mb-1">
          {ticketId}
        </p>
        <p className="text-xs text-gray-400">Save this ID to check your ticket status.</p>

        <div className="mt-4 pt-4 border-t border-gray-200 flex items-center gap-2 text-xs text-gray-500">
          <svg className="h-3.5 w-3.5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          Estimated response: <strong className="text-gray-700">{estimatedTime || 'within 5 min'}</strong>
        </div>
      </div>

      <a
        href={`/ticket/${ticketId}`}
        className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md hover:bg-blue-700 transition-all mb-2"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
        </svg>
        Track My Ticket
      </a>

      <button
        onClick={onReset}
        className="flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-5 py-2.5 text-sm font-medium text-gray-600 shadow-sm hover:bg-gray-50 hover:shadow transition-all"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4"/>
        </svg>
        Submit another request
      </button>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export default function SupportForm({ apiEndpoint = '/support/submit' }) {
  const [form,        setForm]        = useState(INITIAL);
  const [touched,     setTouched]     = useState({});
  const [errors,      setErrors]      = useState({});
  const [status,      setStatus]      = useState('idle');   // idle|submitting|success|error
  const [ticketId,    setTicketId]    = useState('');
  const [estTime,     setEstTime]     = useState('');
  const [serverError, setServerError] = useState('');

  useEffect(() => { setErrors(validate(form)); }, [form]);

  const isValid      = Object.keys(errors).length === 0;
  const isSubmitting = status === 'submitting';
  const charCount    = form.message.length;
  const charPct      = charCount / MESSAGE_MAX;

  const handleChange = useCallback(e => {
    const { name, value } = e.target;
    setForm(p => ({ ...p, [name]: value }));
  }, []);

  const handleBlur = useCallback(e => {
    setTouched(p => ({ ...p, [e.target.name]: true }));
  }, []);

  const handleSubmit = async e => {
    e.preventDefault();
    setTouched({ name:true, email:true, subject:true, category:true, message:true });
    if (!isValid) return;

    setStatus('submitting');
    setServerError('');

    try {
      const res  = await fetch(apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name:     form.name.trim(),
          email:    form.email.trim(),
          subject:  form.subject.trim(),
          category: form.category,
          priority: form.priority,
          message:  form.message.trim(),
        }),
      });
      const data = await res.json();

      if (!res.ok) {
        const detail = Array.isArray(data.detail)
          ? data.detail.map(d => d.msg).join(' ')
          : data.detail || 'Something went wrong.';
        throw new Error(detail);
      }

      setTicketId(data.ticket_id);
      setEstTime(data.estimated_response_time);
      setStatus('success');
    } catch (err) {
      setServerError(err.message || 'Network error. Please try again.');
      setStatus('error');
    }
  };

  const handleReset = () => {
    setForm(INITIAL);
    setTouched({});
    setErrors({});
    setStatus('idle');
    setTicketId('');
    setServerError('');
  };

  // field ring classes
  const ring = name =>
    touched[name] && errors[name]
      ? 'border-red-300 bg-red-50/50 focus:ring-red-300 focus:border-red-400'
      : 'border-gray-200 bg-white focus:ring-blue-200 focus:border-blue-400';

  const inputCls = name =>
    `w-full rounded-xl border px-4 py-3 text-sm text-gray-800 shadow-sm outline-none
     focus:ring-2 transition-all duration-200 placeholder:text-gray-300 ${ring(name)}`;

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <>
      {/* Global animation keyframes injected once */}
      <style>{`
        @keyframes fadeIn  { from { opacity:0; transform:translateY(8px) } to { opacity:1; transform:translateY(0) } }
        @keyframes slideUp { from { opacity:0; transform:translateY(20px)} to { opacity:1; transform:translateY(0) } }
        .animate-fadeIn  { animation: fadeIn  0.3s ease both }
        .animate-slideUp { animation: slideUp 0.4s ease both }
      `}</style>

      {/* Page wrapper — gradient background */}
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 flex items-center justify-center p-4">

        <div className="w-full max-w-lg animate-slideUp">

          {/* Card */}
          <div className="rounded-3xl bg-white shadow-2xl shadow-blue-900/30 overflow-hidden">

            {/* Header */}
            <div className="relative overflow-hidden bg-gradient-to-br from-blue-600 via-blue-500 to-indigo-600 px-8 py-7">
              {/* Decorative circles */}
              <div className="absolute -top-8 -right-8 h-32 w-32 rounded-full bg-white/5" />
              <div className="absolute -bottom-10 -left-6 h-24 w-24 rounded-full bg-white/5" />

              <div className="relative flex items-center gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/15 backdrop-blur-sm">
                  <svg className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                      d="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192l-3.536 3.536M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-5 0a4 4 0 11-8 0 4 4 0 018 0z"/>
                  </svg>
                </div>
                <div>
                  <h1 className="text-xl font-bold text-white">Contact Support</h1>
                  <p className="text-xs text-blue-200 mt-0.5">We typically respond within 5 minutes</p>
                </div>
              </div>

              {/* Progress dots */}
              <div className="relative mt-5 flex items-center gap-1.5">
                {['Details', 'Category', 'Message'].map((step, i) => (
                  <div key={step} className="flex items-center gap-1.5">
                    <div className={`h-1.5 rounded-full transition-all duration-500 ${
                      i === 0 ? 'w-8 bg-white' :
                      i === 1 ? 'w-5 bg-white/50' :
                              'w-3 bg-white/30'
                    }`}/>
                  </div>
                ))}
                <span className="ml-auto text-xs text-blue-200">Fill all fields below</span>
              </div>
            </div>

            {/* Body */}
            <div className="px-8 py-7">

              {status === 'success' ? (
                <SuccessView ticketId={ticketId} estimatedTime={estTime} onReset={handleReset} />
              ) : (
                <form onSubmit={handleSubmit} noValidate className="space-y-5">

                  {/* Server error */}
                  {status === 'error' && serverError && (
                    <div className="flex items-start gap-3 rounded-xl bg-red-50 border border-red-100 px-4 py-3.5 animate-fadeIn">
                      <svg className="h-5 w-5 text-red-400 flex-shrink-0 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd"/>
                      </svg>
                      <div>
                        <p className="text-sm font-semibold text-red-700">Submission failed</p>
                        <p className="text-xs text-red-600 mt-0.5">{serverError}</p>
                      </div>
                    </div>
                  )}

                  {/* Name + Email */}
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div>
                      <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                        Full Name <span className="text-red-400">*</span>
                      </label>
                      <input
                        name="name" type="text" autoComplete="name"
                        placeholder="Jane Smith"
                        value={form.name} onChange={handleChange} onBlur={handleBlur}
                        disabled={isSubmitting}
                        className={inputCls('name')}
                      />
                      <FieldError msg={touched.name && errors.name} />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                        Email <span className="text-red-400">*</span>
                      </label>
                      <input
                        name="email" type="email" autoComplete="email"
                        placeholder="jane@company.com"
                        value={form.email} onChange={handleChange} onBlur={handleBlur}
                        disabled={isSubmitting}
                        className={inputCls('email')}
                      />
                      <FieldError msg={touched.email && errors.email} />
                    </div>
                  </div>

                  {/* Subject */}
                  <div>
                    <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                      Subject <span className="text-red-400">*</span>
                    </label>
                    <input
                      name="subject" type="text"
                      placeholder="Brief description of your issue"
                      value={form.subject} onChange={handleChange} onBlur={handleBlur}
                      disabled={isSubmitting}
                      className={inputCls('subject')}
                    />
                    <FieldError msg={touched.subject && errors.subject} />
                  </div>

                  {/* Category + Priority */}
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div>
                      <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                        Category <span className="text-red-400">*</span>
                      </label>
                      <select
                        name="category"
                        value={form.category} onChange={handleChange} onBlur={handleBlur}
                        disabled={isSubmitting}
                        className={inputCls('category')}
                      >
                        {CATEGORIES.map(({ value, label }) => (
                          <option key={value} value={value} disabled={value === ''}>{label}</option>
                        ))}
                      </select>
                      <FieldError msg={touched.category && errors.category} />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                        Priority
                      </label>
                      <select
                        name="priority"
                        value={form.priority} onChange={handleChange}
                        disabled={isSubmitting}
                        className={inputCls('priority')}
                      >
                        {PRIORITIES.map(({ value, label }) => (
                          <option key={value} value={value}>{label}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* Message */}
                  <div>
                    <div className="flex items-baseline justify-between mb-2">
                      <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        Message <span className="text-red-400">*</span>
                      </label>
                      <div className="flex items-center gap-1.5">
                        {/* Mini progress bar */}
                        <div className="h-1 w-16 rounded-full bg-gray-100 overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-300 ${
                              charPct > 1    ? 'bg-red-500' :
                              charPct > 0.9  ? 'bg-amber-400' :
                                              'bg-blue-400'
                            }`}
                            style={{ width: `${Math.min(charPct * 100, 100)}%` }}
                          />
                        </div>
                        <span className={`text-xs tabular-nums font-medium ${
                          charPct > 1   ? 'text-red-500' :
                          charPct > 0.9 ? 'text-amber-500' :
                                         'text-gray-400'
                        }`}>
                          {charCount}/{MESSAGE_MAX}
                        </span>
                      </div>
                    </div>
                    <textarea
                      name="message" rows={5}
                      placeholder="Please describe your issue in detail…"
                      value={form.message} onChange={handleChange} onBlur={handleBlur}
                      disabled={isSubmitting}
                      className={`${inputCls('message')} resize-y min-h-[120px]`}
                    />
                    <FieldError msg={touched.message && errors.message} />
                  </div>

                  {/* Honeypot */}
                  <div className="hidden" aria-hidden="true">
                    <input type="text" name="honeypot" tabIndex={-1} autoComplete="off" />
                  </div>

                  {/* Submit */}
                  <button
                    type="submit"
                    disabled={isSubmitting || (Object.keys(touched).length > 0 && !isValid)}
                    className={`
                      w-full flex items-center justify-center gap-2.5 rounded-xl px-6 py-3.5
                      text-sm font-semibold text-white shadow-lg transition-all duration-200
                      focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2
                      ${isSubmitting || (Object.keys(touched).length > 0 && !isValid)
                        ? 'bg-blue-300 cursor-not-allowed shadow-none'
                        : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 hover:shadow-blue-200 active:scale-[0.98]'}
                    `}
                  >
                    {isSubmitting ? (
                      <><Spinner /><span>Sending your message…</span></>
                    ) : (
                      <>
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
                        </svg>
                        <span>Send Message</span>
                      </>
                    )}
                  </button>

                  <p className="text-center text-xs text-gray-400">
                    <span className="text-red-400">*</span> Required fields.
                    We'll reply to your email address within minutes.
                  </p>

                </form>
              )}
            </div>
          </div>

          {/* Subtle footer */}
          <p className="mt-4 text-center text-xs text-blue-300/50">
            Powered by NimbusFlow AI Support
          </p>
        </div>
      </div>
    </>
  );
}
