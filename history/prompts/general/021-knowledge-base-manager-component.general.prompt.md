---
id: "021"
title: Knowledge Base Manager Admin Component
stage: green
date: 2026-03-08
surface: agent
model: claude-sonnet-4-6
feature: none
branch: master
user: admin
command: none
labels: ["frontend","react","admin","knowledge-base","tailwind","markdown"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - frontend/components/KnowledgeBaseManager.jsx
tests:
  - none
---

## Prompt

Create Knowledge Base Manager for admin:

File: frontend/components/KnowledgeBaseManager.jsx

Features:
1. Search bar at top
2. Filter by category
3. Articles list: Title, Category, Last updated, Status (Active/Draft), View count, Edit/Delete buttons
4. Add New Article form: Title field, Category dropdown, Content (rich text editor), Tags input, Status toggle (Active/Draft), Save button
5. Edit Article: Same form pre-filled, Update button, Cancel button, Delete option
6. Preview mode: See how article looks to customers, Test search matches

## Response snapshot

Created `frontend/components/KnowledgeBaseManager.jsx` (React 18 + Tailwind CSS). Key architecture:

- **Panel-based navigation** — `panel` state switches between `list`, `new`, `edit`, and `preview` views with `fade-in` animations; no routing dependency
- **Search bar** with live filtering across title, content, and tags; clear button; real-time result count
- **Category filter** dropdown (7 categories: Onboarding, Account, Billing, AI Behaviour, Integrations, Reporting, Legal) with colour-coded badges
- **Articles table** (responsive grid): Title + tag chips, Category badge, Last Updated (relative), Active/Draft status badge, View count, Preview/Edit/Delete actions
- **ArticleForm** component shared by New and Edit panels; fields: Title input, Category select, Status toggle (green switch), Markdown editor with toolbar, TagInput
- **RichTextEditor** — textarea with Markdown toolbar (H1/H2/H3, Bold, Inline code, Bullet list, Ordered list, Blockquote, Code block); uses `insertPrefix` and `wrap` helpers to modify selection
- **TagInput** — inline tag chips with keyboard (Enter/comma to add, Backspace to remove), slug-normalised
- **PreviewPanel** — renders lightweight Markdown→HTML (headings, bold, code, lists, blockquotes, tables, links), highlights search term matches with `<mark>`, shows match count / "no matches" indicator, shows category/date/views meta bar and tags footer
- **Delete confirmation modal** with backdrop blur
- **Toast notifications** (success/error, 3.5s auto-dismiss)
- **Dark/light mode** toggle consistent with all other NimbusFlow admin components
- API endpoints wired: GET/POST/PUT/DELETE `/api/kb/articles`, graceful fallback to mock data (8 articles)

## Outcome

- ✅ Impact: Admin can fully manage knowledge base articles — create, edit, delete, preview rendered output, and test search matching — from a single self-contained component
- 🧪 Tests: none added
- 📁 Files: frontend/components/KnowledgeBaseManager.jsx (created)
- 🔁 Next prompts: Wire into admin routing; add image/file attachment support; add article version history; write unit tests for Markdown renderer
- 🧠 Reflection: Panel-based single-component approach avoids router dependency while keeping the UX clean; shared ArticleForm between new/edit reduces duplication

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): none
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Add sortable columns (by views, last updated) to the articles table
