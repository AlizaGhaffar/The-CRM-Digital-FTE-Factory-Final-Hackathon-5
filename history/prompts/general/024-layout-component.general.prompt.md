---
id: "024"
title: Main Application Layout Component
stage: green
date: 2026-03-08
surface: agent
model: claude-sonnet-4-6
feature: none
branch: master
user: admin
command: none
labels: ["frontend","react","admin","layout","sidebar","navigation","mobile","tailwind"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - frontend/components/Layout.jsx
tests:
  - none
---

## Prompt

Create main application Layout with sidebar navigation (8 items with badges), header (status/refresh/profile/notifications), breadcrumbs, dynamic routing, mobile responsive (collapsible sidebar, bottom nav, hamburger), light/dark mode.

## Response snapshot

Created `frontend/components/Layout.jsx`. Architecture:

- **ThemeContext** exported — child pages can consume `useTheme()` for dark mode without prop drilling
- **Sidebar** — collapsible (w-56 ↔ w-16) with icon-only mode; active indicator bar; badge/dot per item; tooltip on hover when collapsed; user mini-profile footer; Cmd/Ctrl+B keyboard shortcut toggles
- **Header** — breadcrumb from BREADCRUMBS map, live online status dot with ping animation, last-updated relative time, Refresh button with spinner, dark toggle, notification bell with unread counter badge, user avatar with profile dropdown
- **NotifPanel** — dropdown with unread count, mark-all-read, type-keyed emoji icons, blue dot on unread items, outside-click dismiss
- **ProfileDropdown** — user info card, Your Profile / Settings / Sign Out menu, outside-click dismiss
- **MobileDrawer** — full overlay with backdrop blur, slide-in animation, same nav items with badges, close button; locks body scroll while open
- **BottomNav** — fixed bottom bar for 5 key nav items; active indicator top-bar; badge counters; `safe-area-inset-bottom` padding for iOS
- **Dynamic routing** — demo mode renders DemoPage placeholder; production mode syncs with `window.location.pathname` and uses `history.pushState`
- **ThemeContext.Provider** wraps entire layout; dark mode persisted to localStorage; `document.documentElement.classList` toggled for CSS `dark:` variant support
- Main content area `key={activePage}` triggers fade-in animation on page switch; `pb-20 lg:pb-0` accounts for bottom nav height

## Outcome

- ✅ Impact: Complete application shell — all NimbusFlow admin components can be mounted inside this layout
- 🧪 Tests: none added
- 📁 Files: frontend/components/Layout.jsx (created)
- 🔁 Next prompts: Wire all admin components (AdminDashboard, EscalationsQueue, KnowledgeBaseManager, ChannelConfig, AnalyticsDashboard) into Layout routing; add search command palette (Cmd+K); write integration tests
- 🧠 Reflection: Exporting ThemeContext avoids prop-drilling dark mode through every child component; `key={activePage}` on main gives free page transition animations

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): none
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Add Cmd+K command palette for keyboard-driven navigation between pages
