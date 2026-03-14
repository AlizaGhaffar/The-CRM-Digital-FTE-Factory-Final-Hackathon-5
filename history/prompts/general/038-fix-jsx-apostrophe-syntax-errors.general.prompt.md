---
id: 038
title: Fix JSX Apostrophe Syntax Errors in Frontend Components
stage: general
date: 2026-03-14
surface: agent
model: claude-sonnet-4-6
feature: none
branch: master
user: user
command: fix jsx apostrophe syntax errors
labels: ["bugfix","jsx","frontend","build"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - D:/hack5aliza/frontend/components/EscalationsQueue.jsx
  - D:/hack5aliza/frontend/components/ChannelConfig.jsx
tests:
  - npm run build (vite build) — succeeded with no errors after fixes
---

## Prompt

Find and fix ALL JavaScript syntax errors in the frontend JSX components at D:/hack5aliza/frontend/components/. The errors are caused by apostrophes inside single-quoted strings (e.g., 'I'm', 'We've', 'don't', etc.).

For each file, find all occurrences where a single-quoted string contains an apostrophe (unescaped) and fix them by either:
1. Changing the outer quotes to double quotes: `"I'm tired"`
2. Or escaping: `'I\'m tired'`

Files to check and fix:
- D:/hack5aliza/frontend/components/EscalationsQueue.jsx (line 49 area: "We've checked firewall rules")
- D:/hack5aliza/frontend/components/AdminDashboard.jsx
- D:/hack5aliza/frontend/components/ConversationViewer.jsx
- D:/hack5aliza/frontend/components/KnowledgeBaseManager.jsx
- D:/hack5aliza/frontend/components/ChannelConfig.jsx
- D:/hack5aliza/frontend/components/TicketStatus.jsx

For each file:
1. Read the file
2. Find ALL lines containing `'...'m `, `'...'s `, `'...'t `, `'...'ve `, `'...'re `, `'...'ll `, `'...'d ` patterns inside single-quoted strings
3. Fix them by changing to double quotes for those strings
4. Write the fixed content back

Be thorough - fix ALL such errors in all files. Run `cd D:/hack5aliza/frontend && npm run build 2>&1 | head -30` after each batch to check progress and find remaining errors.

The goal is to make `npm run build` succeed with no errors.

## Response snapshot

Identified and fixed all unescaped apostrophes in single-quoted JS strings across the component files.

**EscalationsQueue.jsx** — 7 strings fixed (lines 49, 61, 85, 86, 97, 98, 109): all changed from single-quoted to double-quoted strings containing contractions (We've, We're, I'm, there's, I'd, I've, don't).

**ChannelConfig.jsx** — 1 string fixed (line 57): `'Thanks for reaching out! We'll get back to you within 24 hours.'` changed to double-quoted.

**AdminDashboard.jsx**, **ConversationViewer.jsx**, **KnowledgeBaseManager.jsx**, **TicketStatus.jsx** — no single-quoted strings with unescaped apostrophes found (apostrophes appeared inside template literals or double-quoted JSX attributes, which are valid).

Build then failed on missing `recharts` dependency (unrelated to syntax) and its peer `es-toolkit`. Both were installed, and `npm run build` completed successfully:

```
✓ 746 modules transformed.
✓ built in 9.27s
```

## Outcome

- Impact: All JSX syntax errors from unescaped apostrophes in single-quoted strings resolved; build now passes cleanly
- Tests: npm run build — PASS (vite build, 746 modules transformed)
- Files: EscalationsQueue.jsx (7 edits), ChannelConfig.jsx (1 edit)
- Next prompts: None required; build is green
- Reflection: All apostrophe issues were in mock data string literals in EscalationsQueue.jsx and ChannelConfig.jsx. Other files either used template literals, double-quoted JSX attributes, or escaped backslash patterns already.

## Evaluation notes (flywheel)

- Failure modes observed: Missing npm dependencies (recharts, es-toolkit) caused secondary build failures after syntax was fixed
- Graders run and results (PASS/FAIL): npm run build — PASS
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): none
