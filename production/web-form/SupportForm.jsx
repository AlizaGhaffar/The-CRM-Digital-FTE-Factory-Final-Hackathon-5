/**
 * production/web-form/SupportForm.jsx
 *
 * NimbusFlow Web Support Form — Exercise 2.2 Required Build
 *
 * Standalone, embeddable React component. Submits to POST /support/submit
 * and displays real-time validation, loading, success, and error states.
 *
 * Usage (Next.js page):
 *   import SupportForm from '@/components/SupportForm';
 *   export default function SupportPage() {
 *     return <SupportForm apiEndpoint="/support/submit" />;
 *   }
 *
 * Usage (standalone embed in any HTML page):
 *   <div id="support-form-root"></div>
 *   <script>
 *     ReactDOM.render(
 *       React.createElement(SupportForm, { apiEndpoint: 'https://api.nimbusflow.io/support/submit' }),
 *       document.getElementById('support-form-root')
 *     );
 *   </script>
 *
 * Requirements: React 18+, Tailwind CSS
 */

import { useState, useEffect, useCallback } from 'react';

// ── Constants ──────────────────────────────────────────────────────────────

const CATEGORIES = [
  { value: '',           label: 'Select a category…' },
  { value: 'general',   label: 'General Question' },
  { value: 'technical', label: 'Technical Support' },
  { value: 'billing',   label: 'Billing Inquiry' },
  { value: 'bug_report',label: 'Bug Report' },
  { value: 'feedback',  label: 'Feedback' },
];

const PRIORITIES = [
  { value: 'low',    label: 'Low — Not urgent' },
  { value: 'medium', label: 'Medium — Need help soon' },
  { value: 'high',   label: 'High — Urgent issue' },
];

const MESSAGE_MAX = 1000;
const MESSAGE_MIN = 10;

const INITIAL_FORM = {
  name:     '',
  email:    '',
  subject:  '',
  category: '',
  priority: 'medium',
  message:  '',
};

// ── Validators ─────────────────────────────────────────────────────────────

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validate(fields) {
  const errors = {};

  if (!fields.name.trim())
    errors.name = 'Name is required.';
  else if (fields.name.trim().length < 2)
    errors.name = 'Name must be at least 2 characters.';

  if (!fields.email.trim())
    errors.email = 'Email is required.';
  else if (!EMAIL_RE.test(fields.email.trim()))
    errors.email = 'Please enter a valid email address.';

  if (!fields.subject.trim())
    errors.subject = 'Subject is required.';
  else if (fields.subject.trim().length < 5)
    errors.subject = 'Subject must be at least 5 characters.';

  if (!fields.category)
    errors.category = 'Please select a category.';

  if (!fields.message.trim())
    errors.message = 'Message is required.';
  else if (fields.message.trim().length < MESSAGE_MIN)
    errors.message = `Message must be at least ${MESSAGE_MIN} characters.`;
  else if (fields.message.length > MESSAGE_MAX)
    errors.message = `Message must be ${MESSAGE_MAX} characters or fewer.`;

  return errors;
}

// ── Sub-components ─────────────────────────────────────────────────────────

function FieldError({ message }) {
  if (!message) return null;
  return (
    <p role="alert" className="mt-1 text-sm text-red-600 flex items-center gap-1">
      <svg className="w-3.5 h-3.5 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
      </svg>
      {message}
    </p>
  );
}

function Label({ htmlFor, children, required }) {
  return (
    <label htmlFor={htmlFor} className="block text-sm font-medium text-gray-700 mb-1">
      {children}
      {required && <span className="text-red-500 ml-0.5" aria-hidden="true">*</span>}
    </label>
  );
}

function Spinner() {
  return (
    <svg
      className="animate-spin h-5 w-5 text-white"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}

// ── Success state ──────────────────────────────────────────────────────────

function SuccessView({ ticketId, estimatedTime, onReset }) {
  return (
    <div className="text-center py-8 px-4">
      {/* Checkmark icon */}
      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
        <svg className="h-8 w-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      </div>

      <h2 className="text-2xl font-bold text-gray-900 mb-2">
        Request Submitted!
      </h2>
      <p className="text-gray-500 mb-6">
        Our AI assistant will review your request and respond shortly.
      </p>

      {/* Ticket ID */}
      <div className="mx-auto max-w-sm rounded-lg border border-gray-200 bg-gray-50 p-4 mb-6">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-1">
          Your Ticket ID
        </p>
        <p className="font-mono text-sm font-semibold text-gray-900 break-all">
          {ticketId}
        </p>
        <p className="mt-1 text-xs text-gray-400">
          Save this ID to track your request status.
        </p>
      </div>

      {/* Estimated response time */}
      <div className="flex items-center justify-center gap-2 text-sm text-gray-600 mb-8">
        <svg className="h-4 w-4 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>Estimated response time: <strong>{estimatedTime || 'within 5 minutes'}</strong></span>
      </div>

      <button
        onClick={onReset}
        className="rounded-lg border border-gray-300 bg-white px-5 py-2.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
      >
        Submit another request
      </button>
    </div>
  );
}

// ── Main form ──────────────────────────────────────────────────────────────

export default function SupportForm({ apiEndpoint = '/support/submit' }) {
  const [formData, setFormData]       = useState(INITIAL_FORM);
  const [touched, setTouched]         = useState({});
  const [errors, setErrors]           = useState({});
  const [status, setStatus]           = useState('idle');   // idle | submitting | success | error
  const [ticketId, setTicketId]       = useState(null);
  const [estimatedTime, setEstimated] = useState(null);
  const [serverError, setServerError] = useState('');

  // Re-validate on every formData change
  useEffect(() => {
    setErrors(validate(formData));
  }, [formData]);

  const isValid     = Object.keys(errors).length === 0;
  const isSubmitting = status === 'submitting';
  const charCount   = formData.message.length;
  const charOver    = charCount > MESSAGE_MAX;

  // ── Handlers ────────────────────────────────────────────────────────────

  const handleChange = useCallback((e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  }, []);

  const handleBlur = useCallback((e) => {
    setTouched(prev => ({ ...prev, [e.target.name]: true }));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Mark all fields as touched to show all errors on submit attempt
    setTouched({ name: true, email: true, subject: true, category: true, message: true });

    if (!isValid) return;

    setStatus('submitting');
    setServerError('');

    try {
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name:     formData.name.trim(),
          email:    formData.email.trim(),
          subject:  formData.subject.trim(),
          category: formData.category,
          priority: formData.priority,
          message:  formData.message.trim(),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        // FastAPI validation errors come as { detail: [...] } or { detail: "..." }
        const detail = Array.isArray(data.detail)
          ? data.detail.map(d => d.msg).join(' ')
          : data.detail || 'Something went wrong. Please try again.';
        throw new Error(detail);
      }

      setTicketId(data.ticket_id);
      setEstimated(data.estimated_response_time);
      setStatus('success');

    } catch (err) {
      setServerError(err.message || 'Network error. Please check your connection and try again.');
      setStatus('error');
    }
  };

  const handleReset = () => {
    setFormData(INITIAL_FORM);
    setTouched({});
    setErrors({});
    setStatus('idle');
    setTicketId(null);
    setServerError('');
  };

  // ── Render helpers ───────────────────────────────────────────────────────

  const fieldClass = (name) =>
    [
      'block w-full rounded-lg border px-3 py-2.5 text-sm shadow-sm',
      'focus:outline-none focus:ring-2 focus:ring-offset-0 transition-colors',
      touched[name] && errors[name]
        ? 'border-red-400 focus:border-red-400 focus:ring-red-300 bg-red-50'
        : 'border-gray-300 focus:border-blue-500 focus:ring-blue-200 bg-white',
    ].join(' ');

  // ── Success view ─────────────────────────────────────────────────────────

  if (status === 'success') {
    return (
      <div className="mx-auto max-w-lg rounded-2xl border border-gray-200 bg-white shadow-sm">
        <SuccessView
          ticketId={ticketId}
          estimatedTime={estimatedTime}
          onReset={handleReset}
        />
      </div>
    );
  }

  // ── Form view ────────────────────────────────────────────────────────────

  return (
    <div className="mx-auto max-w-lg">
      <div className="rounded-2xl border border-gray-200 bg-white shadow-sm">

        {/* Header */}
        <div className="rounded-t-2xl bg-gradient-to-r from-blue-600 to-blue-500 px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/20">
              <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192l-3.536 3.536M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-5 0a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white">Contact Support</h1>
              <p className="text-xs text-blue-100">We typically respond within 5 minutes</p>
            </div>
          </div>
        </div>

        {/* Form body */}
        <form onSubmit={handleSubmit} noValidate className="px-6 py-6 space-y-5">

          {/* Server error banner */}
          {status === 'error' && serverError && (
            <div
              role="alert"
              className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4"
            >
              <svg className="h-5 w-5 flex-shrink-0 text-red-500 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <div>
                <p className="text-sm font-medium text-red-800">Submission failed</p>
                <p className="text-sm text-red-700 mt-0.5">{serverError}</p>
              </div>
            </div>
          )}

          {/* Name + Email — two columns on sm+ */}
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">

            {/* Name */}
            <div>
              <Label htmlFor="name" required>Full Name</Label>
              <input
                id="name"
                name="name"
                type="text"
                autoComplete="name"
                placeholder="Jane Smith"
                value={formData.name}
                onChange={handleChange}
                onBlur={handleBlur}
                disabled={isSubmitting}
                className={fieldClass('name')}
                aria-describedby={touched.name && errors.name ? 'name-error' : undefined}
              />
              <FieldError message={touched.name && errors.name} />
            </div>

            {/* Email */}
            <div>
              <Label htmlFor="email" required>Email Address</Label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                placeholder="jane@company.com"
                value={formData.email}
                onChange={handleChange}
                onBlur={handleBlur}
                disabled={isSubmitting}
                className={fieldClass('email')}
                aria-describedby={touched.email && errors.email ? 'email-error' : undefined}
              />
              <FieldError message={touched.email && errors.email} />
            </div>

          </div>

          {/* Subject */}
          <div>
            <Label htmlFor="subject" required>Subject</Label>
            <input
              id="subject"
              name="subject"
              type="text"
              placeholder="Brief description of your issue"
              value={formData.subject}
              onChange={handleChange}
              onBlur={handleBlur}
              disabled={isSubmitting}
              className={fieldClass('subject')}
            />
            <FieldError message={touched.subject && errors.subject} />
          </div>

          {/* Category + Priority — two columns on sm+ */}
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">

            {/* Category */}
            <div>
              <Label htmlFor="category" required>Category</Label>
              <select
                id="category"
                name="category"
                value={formData.category}
                onChange={handleChange}
                onBlur={handleBlur}
                disabled={isSubmitting}
                className={fieldClass('category')}
              >
                {CATEGORIES.map(({ value, label }) => (
                  <option key={value} value={value} disabled={value === ''}>
                    {label}
                  </option>
                ))}
              </select>
              <FieldError message={touched.category && errors.category} />
            </div>

            {/* Priority */}
            <div>
              <Label htmlFor="priority">Priority</Label>
              <select
                id="priority"
                name="priority"
                value={formData.priority}
                onChange={handleChange}
                disabled={isSubmitting}
                className={fieldClass('priority')}
              >
                {PRIORITIES.map(({ value, label }) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>

          </div>

          {/* Message */}
          <div>
            <div className="flex items-baseline justify-between mb-1">
              <Label htmlFor="message" required>Message</Label>
              <span
                className={`text-xs tabular-nums ${
                  charOver
                    ? 'text-red-600 font-semibold'
                    : charCount >= MESSAGE_MAX * 0.9
                    ? 'text-amber-600'
                    : 'text-gray-400'
                }`}
                aria-live="polite"
              >
                {charCount} / {MESSAGE_MAX}
              </span>
            </div>
            <textarea
              id="message"
              name="message"
              rows={5}
              placeholder="Describe your issue in detail…"
              value={formData.message}
              onChange={handleChange}
              onBlur={handleBlur}
              disabled={isSubmitting}
              className={`${fieldClass('message')} resize-y min-h-[120px]`}
            />
            <FieldError message={touched.message && errors.message} />
          </div>

          {/* Honeypot — visually hidden, bots fill this in */}
          <div className="hidden" aria-hidden="true">
            <input
              type="text"
              name="honeypot"
              tabIndex={-1}
              autoComplete="off"
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={isSubmitting || (Object.keys(touched).length > 0 && !isValid)}
            className={[
              'w-full flex items-center justify-center gap-2 rounded-lg px-4 py-3',
              'text-sm font-semibold text-white shadow-sm transition-all',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
              isSubmitting || (Object.keys(touched).length > 0 && !isValid)
                ? 'bg-blue-300 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800',
            ].join(' ')}
          >
            {isSubmitting ? (
              <>
                <Spinner />
                <span>Sending…</span>
              </>
            ) : (
              <>
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
                <span>Send Message</span>
              </>
            )}
          </button>

          <p className="text-center text-xs text-gray-400">
            Fields marked <span className="text-red-500">*</span> are required.
            We'll reply to your email address.
          </p>

        </form>
      </div>
    </div>
  );
}
