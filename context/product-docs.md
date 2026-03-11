# NimbusFlow — Product Documentation

## Table of Contents
1. Getting Started
2. Projects & Tasks
3. Sprint Planning
4. Integrations
5. API & Webhooks
6. Billing & Plans
7. Security & SSO
8. Mobile App
9. Data Export
10. Troubleshooting

---

## 1. Getting Started

### Creating Your Account
1. Visit app.nimbusflow.io/signup
2. Enter your work email and create a password (min 8 chars, 1 uppercase, 1 number)
3. Verify your email within 24 hours
4. Invite your team members from Settings > Team

### Workspace Setup
- Each account gets one **Workspace**
- Workspace URL: `yourcompany.nimbusflow.io`
- You can rename your workspace in Settings > General

### Inviting Team Members
- Go to Settings > Team > Invite Members
- Enter email addresses (comma-separated for bulk)
- Set role: **Admin**, **Member**, or **Viewer**
- Invitations expire after 7 days
- Resend from Settings > Team > Pending Invites

---

## 2. Projects & Tasks

### Creating a Project
- Click "+ New Project" in the left sidebar
- Choose template: Scrum, Kanban, or Blank
- Set visibility: Public (all workspace members) or Private (invite-only)
- Max projects: 3 (Starter), Unlimited (Growth+)

### Task Fields
| Field | Description |
|-------|-------------|
| Title | Required, max 500 chars |
| Description | Rich text, supports markdown |
| Assignee | Single user |
| Due Date | Optional |
| Priority | Low / Medium / High / Critical |
| Labels | Custom tags |
| Story Points | Fibonacci scale (1, 2, 3, 5, 8, 13) |
| Status | To Do / In Progress / In Review / Done |

### Task Dependencies
- Link tasks as "Blocks" or "Blocked by"
- Available on Growth and Business plans
- Circular dependencies are not allowed

### Subtasks
- Add subtasks from the task detail view
- Max 50 subtasks per task
- Subtasks inherit parent's project and sprint

---

## 3. Sprint Planning

### Creating a Sprint
1. Navigate to your project > Sprints tab
2. Click "+ New Sprint"
3. Set sprint name, start date, and end date
4. Drag tasks from Backlog into the sprint

### Sprint Rules
- Only one **active sprint** per project at a time
- Duration: 1–4 weeks recommended
- Start sprint from the Sprint view > "Start Sprint"
- Complete sprint: all incomplete tasks move to Backlog or next sprint

### Velocity Tracking
- Automatically calculated from story points
- View in Reports > Velocity Chart
- Available on Business and Enterprise plans

---

## 4. Integrations

### GitHub Integration
**Setup:**
1. Go to Settings > Integrations > GitHub
2. Click "Connect GitHub"
3. Authorize NimbusFlow OAuth app
4. Select repositories to sync

**Features:**
- Link PRs and commits to NimbusFlow tasks using `NF-[task-id]` in commit message
- Auto-close tasks when PR is merged
- Branch name suggestion from task title

**Troubleshooting:**
- Webhook not firing: Re-authorize from Settings > Integrations > GitHub > Reconnect
- PRs not linking: Ensure `NF-123` format (dash, not hash) in commit or PR title

### Slack Integration
**Setup:**
1. Settings > Integrations > Slack > Add to Slack
2. Choose notification channel
3. Select event types: task created, status change, mentions, sprint start/end

**Commands:**
- `/nimbus task [title]` — create task from Slack
- `/nimbus status NF-123` — check task status
- `/nimbus assign NF-123 @username` — assign task

### Google Workspace
- Sign in with Google SSO (all plans)
- Google Calendar sync for due dates (Growth+)
- Google Drive file attachments (Growth+)

### Figma
- Embed Figma frames directly in task descriptions
- Comment sync (Business+)

### API
- REST API docs: docs.nimbusflow.io/api
- GraphQL endpoint: api.nimbusflow.io/graphql
- Rate limits:
  - Starter: 60 requests/minute
  - Growth: 300 requests/minute
  - Business: 1,000 requests/minute
  - Enterprise: Custom

---

## 5. API & Webhooks

### Authentication
- API Key: Settings > Developer > API Keys
- Bearer token authentication: `Authorization: Bearer YOUR_API_KEY`
- OAuth 2.0 available for third-party integrations

### Webhook Setup
1. Settings > Developer > Webhooks > Add Webhook
2. Enter your endpoint URL (must be HTTPS)
3. Select events to subscribe to
4. Save and test with "Send Test Payload"

### Webhook Events
- `task.created`, `task.updated`, `task.deleted`
- `sprint.started`, `sprint.completed`
- `member.invited`, `member.removed`
- `comment.added`

### Common API Errors
| Code | Meaning | Fix |
|------|---------|-----|
| 401 | Invalid API key | Regenerate key in Settings > Developer |
| 403 | Insufficient permissions | Check user role (Admin required for some endpoints) |
| 429 | Rate limit exceeded | Reduce request frequency or upgrade plan |
| 422 | Validation error | Check request body against API docs |

---

## 6. Billing & Plans

### Upgrading Your Plan
1. Settings > Billing > Change Plan
2. Select new plan
3. Upgrade is immediate, billed pro-rata for current month

### Downgrading
- Downgrades take effect at end of billing period
- Data is preserved for 60 days after downgrade
- Starter plan: projects beyond limit become read-only

### Adding/Removing Seats
- Settings > Billing > Manage Seats
- Seats are billed monthly per active user
- Removing a user frees up their seat at next billing cycle

### Payment Methods
- Credit/Debit card (Visa, Mastercard, Amex)
- Invoice payment (Business and Enterprise)
- Annual billing: 2 months free

### Refund Policy
- No refunds on monthly plans
- Annual plans: prorated refund within 30 days of purchase
- Refund requests: billing@nimbusflow.io

---

## 7. Security & SSO

### SSO / SAML Setup (Business & Enterprise)
1. Settings > Security > SAML SSO
2. Download NimbusFlow metadata XML
3. Configure your IdP (Okta, Azure AD, Google Workspace)
4. Upload IdP metadata or enter SSO URL manually
5. Test with "Test SSO Connection"
6. Enable enforced SSO

**Supported IdPs:**
- Okta
- Azure Active Directory
- Google Workspace
- OneLogin
- Ping Identity
- Any SAML 2.0 compliant provider

### Two-Factor Authentication (2FA)
- Available on all plans
- Methods: Authenticator app (TOTP), SMS, Hardware key (Enterprise)
- Enforce 2FA workspace-wide: Settings > Security > Require 2FA

### Data Security
- Data encrypted at rest (AES-256) and in transit (TLS 1.3)
- SOC 2 Type II certified
- GDPR compliant
- Data residency: US, EU, APAC (Enterprise)
- Annual penetration testing

### Password Reset
1. Go to nimbusflow.io/forgot-password
2. Enter your work email
3. Check email for reset link (valid 1 hour)
4. If email not received: check spam, or contact support

---

## 8. Mobile App

### Download
- iOS: App Store — search "NimbusFlow"
- Android: Google Play — search "NimbusFlow"
- Minimum: iOS 14+, Android 9+

### Features
- View and update tasks
- Receive push notifications
- Record voice notes on tasks
- Offline mode: view cached tasks, sync when online

### Known Issues & Fixes
| Issue | Fix |
|-------|-----|
| App not syncing | Pull to refresh, or log out and back in |
| Push notifications not arriving | Settings > Notifications in app, re-enable |
| Blank screen on launch | Clear app cache (Android) or reinstall |
| Login loop | Clear cookies in device settings |

### Sync Delay
- Real-time sync via WebSocket
- If disconnected: changes sync within 60 seconds of reconnecting
- Offline changes: up to 72 hours of offline support

---

## 9. Data Export

### Export Formats
- **CSV:** Tasks, time logs, members
- **JSON:** Full workspace data
- **PDF:** Sprint reports, burndown charts

### How to Export
1. Settings > Data > Export
2. Choose export type
3. Select date range
4. Click "Generate Export"
5. Download link emailed within 5 minutes (large exports up to 30 minutes)

### GDPR Data Requests
- Request full data export: Settings > Privacy > Request My Data
- Processed within 30 days (usually 72 hours)
- Includes: tasks, comments, time logs, account data

---

## 10. Troubleshooting

### Can't Log In
1. Check if Caps Lock is on
2. Try password reset at nimbusflow.io/forgot-password
3. Check if SSO is enforced (contact your admin)
4. Try incognito/private browser window
5. Clear browser cache and cookies

### Task Not Saving
- Check internet connection
- Ensure task title is not empty
- Refresh and try again
- Check browser console for errors and report to support

### Integration Not Working
- Re-authorize the integration (Settings > Integrations)
- Check if API key has expired
- Verify webhook URL is publicly accessible (not localhost)

### Slow Performance
- Check status.nimbusflow.io for incidents
- Try a different browser
- Disable browser extensions
- Clear browser cache

### Account Locked
- 10 failed login attempts locks account for 30 minutes
- Contact support with your email to unlock immediately
