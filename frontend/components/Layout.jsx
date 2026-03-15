/**
 * frontend/components/Layout.jsx
 *
 * NimbusFlow — Main Application Layout
 * Sidebar navigation, header, breadcrumbs, dynamic routing,
 * mobile-responsive bottom nav, dark/light mode, notifications.
 *
 * Usage (Next.js app router):
 *   // app/admin/layout.jsx
 *   import Layout from '@/components/Layout';
 *   export default function AdminLayout({ children }) {
 *     return <Layout>{children}</Layout>;
 *   }
 *
 * Usage (standalone / demo):
 *   import Layout from '@/components/Layout';
 *   <Layout demo />
 *
 * Requirements: React 18+, Tailwind CSS
 */

import { useState, useEffect, useRef, useCallback, createContext, useContext } from 'react';

// ── Theme context (shared with child pages) ─────────────────────────────────

export const ThemeContext = createContext({ dark: false, setDark: () => {} });
export const useTheme = () => useContext(ThemeContext);

// ── Navigation config ───────────────────────────────────────────────────────

const NAV_ITEMS = [
  { id: 'dashboard',     label: 'Dashboard',      emoji: '🏠', path: '/admin',                  badge: null },
  { id: 'tickets',       label: 'Tickets',         emoji: '🎫', path: '/admin/tickets',          badge: 12 },
  { id: 'conversations', label: 'Conversations',   emoji: '💬', path: '/admin/conversations',    badge: 5 },
  { id: 'escalations',   label: 'Escalations',     emoji: '⚠️', path: '/admin/escalations',     badge: 8, urgent: true },
  { id: 'knowledge',     label: 'Knowledge Base',  emoji: '📚', path: '/admin/knowledge',        badge: null },
  { id: 'analytics',     label: 'Analytics',       emoji: '📊', path: '/admin/analytics',        badge: null },
  { id: 'channels',      label: 'Channels',        emoji: '📡', path: '/admin/channels',         badge: null },
  { id: 'settings',      label: 'Settings',        emoji: '⚙️', path: '/admin/settings',        badge: null },
];

// Bottom nav shows first 5 most important items on mobile
const BOTTOM_NAV = ['dashboard', 'tickets', 'escalations', 'analytics', 'settings'];

// Breadcrumb map
const BREADCRUMBS = {
  dashboard:     ['Dashboard'],
  tickets:       ['Dashboard', 'Tickets'],
  conversations: ['Dashboard', 'Conversations'],
  escalations:   ['Dashboard', 'Escalations'],
  knowledge:     ['Dashboard', 'Knowledge Base'],
  analytics:     ['Dashboard', 'Analytics'],
  channels:      ['Dashboard', 'Channels'],
  settings:      ['Dashboard', 'Settings'],
};

// Mock notifications
const MOCK_NOTIFS = [
  { id: 1, type: 'escalation', text: '8 tickets awaiting human review',          time: '2m ago',  read: false },
  { id: 2, type: 'sentiment',  text: 'Low sentiment detected — eve@design.co',  time: '14m ago', read: false },
  { id: 3, type: 'system',     text: 'WhatsApp webhook reconnected successfully', time: '1h ago',  read: true },
  { id: 4, type: 'ticket',     text: 'TKT-00421 escalated by AI agent',          time: '2h ago',  read: true },
  { id: 5, type: 'system',     text: 'Knowledge base sync completed (8 articles)','time': '3h ago', read: true },
];

const NOTIF_ICON = {
  escalation: '⚠️',
  sentiment:  '😟',
  system:     '🔧',
  ticket:     '🎫',
};

// ── Demo page components ────────────────────────────────────────────────────

function DemoPage({ page, dark }) {
  const text  = dark ? 'text-gray-300' : 'text-gray-600';
  const label = NAV_ITEMS.find(n => n.id === page)?.label || 'Page';
  const emoji = NAV_ITEMS.find(n => n.id === page)?.emoji || '📄';
  return (
    <div className={`flex flex-col items-center justify-center min-h-[60vh] gap-4 ${text}`}>
      <span className="text-6xl">{emoji}</span>
      <p className="text-xl font-semibold">{label}</p>
      <p className="text-sm opacity-60">Mount your <code className="font-mono">{label}</code> component here.</p>
    </div>
  );
}

// ── Icons ──────────────────────────────────────────────────────────────────

function BellIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/></svg>;
}
function ChevronIcon({ className, open }) {
  return <svg className={`${className} transition-transform duration-200 ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/></svg>;
}
function MenuIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16"/></svg>;
}
function XIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/></svg>;
}
function RefreshIcon({ className, spinning }) {
  return <svg className={`${className} ${spinning ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>;
}
function MoonIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>;
}
function SunIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>;
}
function LogoutIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>;
}
function UserIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>;
}
function CogIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>;
}
function CheckIcon({ className }) {
  return <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/></svg>;
}

// ── Sidebar ─────────────────────────────────────────────────────────────────

function Sidebar({ dark, activePage, onNavigate, collapsed, onCollapse }) {
  const bg      = dark ? 'bg-gray-950 border-purple-900/40' : 'bg-white border-purple-100';
  const text    = dark ? 'text-gray-100' : 'text-gray-900';
  const muted   = dark ? 'text-purple-400' : 'text-gray-500';
  const logo    = dark ? 'text-violet-400' : 'text-violet-600';

  return (
    <aside className={`flex flex-col h-full border-r transition-all duration-300 ${bg} ${
      collapsed ? 'w-16' : 'w-56'
    }`}>
      {/* Logo */}
      <div className={`flex items-center h-14 px-4 border-b ${dark ? 'border-gray-800' : 'border-gray-100'} flex-shrink-0`}>
        <div className="flex items-center gap-2.5 min-w-0">
          <div className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl font-bold text-sm ${
            dark ? 'bg-violet-700 text-white' : 'bg-violet-600 text-white'
          }`}>N</div>
          {!collapsed && (
            <span className={`text-sm font-bold truncate ${logo}`}>NimbusFlow</span>
          )}
        </div>
        <button
          onClick={onCollapse}
          className={`ml-auto flex-shrink-0 rounded-lg p-1 transition-colors ${
            dark ? 'text-gray-500 hover:text-gray-300 hover:bg-gray-700' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
          }`}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <MenuIcon className="h-4 w-4" />
        </button>
      </div>

      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto py-3 space-y-0.5 px-2">
        {NAV_ITEMS.map(item => {
          const active = activePage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              title={collapsed ? item.label : undefined}
              className={`w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-150 group relative ${
                active
                  ? (dark
                      ? 'bg-violet-900/50 text-violet-400 shadow-sm'
                      : 'bg-violet-50 text-violet-700 shadow-sm')
                  : (dark
                      ? 'text-purple-400 hover:bg-purple-900/30 hover:text-purple-200'
                      : 'text-gray-600 hover:bg-purple-50 hover:text-gray-900')
              }`}
            >
              {/* Active indicator bar */}
              {active && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-r bg-violet-500" />
              )}

              <span className="text-base flex-shrink-0 leading-none">{item.emoji}</span>

              {!collapsed && (
                <span className="flex-1 truncate text-left text-xs">{item.label}</span>
              )}

              {/* Badge */}
              {item.badge && !collapsed && (
                <span className={`flex-shrink-0 rounded-full px-1.5 py-0.5 text-xs font-bold leading-none ${
                  item.urgent
                    ? (dark ? 'bg-red-900/60 text-red-300' : 'bg-red-100 text-red-700')
                    : (dark ? 'bg-violet-900/60 text-violet-300' : 'bg-violet-100 text-violet-700')
                }`}>
                  {item.badge}
                </span>
              )}

              {/* Collapsed badge dot */}
              {item.badge && collapsed && (
                <span className={`absolute top-1.5 right-1.5 h-2 w-2 rounded-full ${item.urgent ? 'bg-red-500' : 'bg-violet-500'}`} />
              )}

              {/* Tooltip on collapsed */}
              {collapsed && (
                <div className={`absolute left-full ml-3 z-50 hidden group-hover:flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold shadow-lg whitespace-nowrap pointer-events-none ${
                  dark ? 'bg-gray-700 text-gray-200' : 'bg-gray-900 text-white'
                }`}>
                  {item.label}
                  {item.badge && (
                    <span className={`rounded-full px-1.5 py-0.5 text-xs font-bold ${
                      item.urgent ? 'bg-red-600 text-white' : 'bg-gray-600 text-gray-200'
                    }`}>{item.badge}</span>
                  )}
                </div>
              )}
            </button>
          );
        })}
      </nav>

      {/* Sidebar footer — user mini */}
      {!collapsed && (
        <div className={`flex items-center gap-2.5 px-4 py-3 border-t ${dark ? 'border-gray-800' : 'border-gray-100'} flex-shrink-0`}>
          <div className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold ${
            dark ? 'bg-violet-900 text-violet-300' : 'bg-violet-100 text-violet-700'
          }`}>AC</div>
          <div className="flex-1 min-w-0">
            <p className={`text-xs font-semibold truncate ${text}`}>Alex Chen</p>
            <p className={`text-xs truncate ${muted}`}>Admin</p>
          </div>
        </div>
      )}
      {collapsed && (
        <div className="flex justify-center py-3 border-t border-gray-800 flex-shrink-0">
          <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
            dark ? 'bg-violet-900 text-violet-300' : 'bg-violet-100 text-violet-700'
          }`}>AC</div>
        </div>
      )}
    </aside>
  );
}

// ── Notification panel ──────────────────────────────────────────────────────

function NotifPanel({ dark, notifs, onRead, onClose, panelRef }) {
  const card    = dark ? 'bg-gray-950 border-purple-900/40' : 'bg-white border-purple-100';
  const text    = dark ? 'text-gray-100' : 'text-gray-900';
  const muted   = dark ? 'text-purple-400' : 'text-gray-500';
  const divider = dark ? 'border-purple-900/40' : 'border-purple-100';
  const hover   = dark ? 'hover:bg-purple-900/20' : 'hover:bg-purple-50';

  const unread = notifs.filter(n => !n.read).length;

  return (
    <div
      ref={panelRef}
      className={`absolute right-0 top-full mt-2 z-50 w-80 rounded-2xl border shadow-2xl overflow-hidden ${card}`}
    >
      {/* Header */}
      <div className={`flex items-center justify-between px-4 py-3 border-b ${divider}`}>
        <div className="flex items-center gap-2">
          <span className={`text-sm font-bold ${text}`}>Notifications</span>
          {unread > 0 && (
            <span className="rounded-full bg-violet-600 px-1.5 py-0.5 text-xs font-bold text-white">{unread}</span>
          )}
        </div>
        <button onClick={() => onRead('all')} className={`text-xs font-medium ${dark ? 'text-violet-400 hover:text-violet-300' : 'text-violet-600 hover:text-violet-700'}`}>
          Mark all read
        </button>
      </div>

      {/* List */}
      <div className="max-h-72 overflow-y-auto divide-y divide-transparent">
        {notifs.map(n => (
          <button
            key={n.id}
            onClick={() => onRead(n.id)}
            className={`w-full text-left flex items-start gap-3 px-4 py-3 transition-colors ${hover} ${
              !n.read ? (dark ? 'bg-blue-900/10' : 'bg-blue-50/60') : ''
            }`}
          >
            <span className="text-lg leading-none flex-shrink-0 mt-0.5">{NOTIF_ICON[n.type]}</span>
            <div className="flex-1 min-w-0">
              <p className={`text-xs leading-snug ${!n.read ? (dark ? 'text-gray-200 font-semibold' : 'text-gray-800 font-semibold') : (dark ? 'text-gray-400' : 'text-gray-600')}`}>
                {n.text}
              </p>
              <p className={`text-xs mt-0.5 ${muted}`}>{n.time}</p>
            </div>
            {!n.read && <span className="h-2 w-2 rounded-full bg-violet-500 flex-shrink-0 mt-1.5" />}
          </button>
        ))}
      </div>

      {/* Footer */}
      <div className={`px-4 py-2.5 border-t ${divider}`}>
        <button className={`text-xs font-medium ${dark ? 'text-violet-400 hover:text-violet-300' : 'text-violet-600 hover:text-violet-700'}`}>
          View all notifications →
        </button>
      </div>
    </div>
  );
}

// ── User profile dropdown ───────────────────────────────────────────────────

function ProfileDropdown({ dark, onNavigate, dropRef }) {
  const card    = dark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200';
  const text    = dark ? 'text-gray-200' : 'text-gray-700';
  const muted   = dark ? 'text-gray-400' : 'text-gray-500';
  const divider = dark ? 'border-gray-700' : 'border-gray-100';
  const hover   = dark ? 'hover:bg-gray-700' : 'hover:bg-gray-50';

  const items = [
    { label: 'Your Profile',  icon: UserIcon,   action: () => onNavigate('settings') },
    { label: 'Settings',      icon: CogIcon,    action: () => onNavigate('settings') },
    { divider: true },
    { label: 'Sign Out',      icon: LogoutIcon, action: () => alert('Sign out'), danger: true },
  ];

  return (
    <div
      ref={dropRef}
      className={`absolute right-0 top-full mt-2 z-50 w-48 rounded-2xl border shadow-2xl overflow-hidden ${card}`}
    >
      {/* User info */}
      <div className={`px-4 py-3 border-b ${divider}`}>
        <p className={`text-xs font-bold ${dark ? 'text-gray-100' : 'text-gray-900'}`}>Alex Chen</p>
        <p className={`text-xs ${muted}`}>alex@nimbusflow.io</p>
        <span className={`inline-block mt-1 rounded-full px-2 py-0.5 text-xs font-semibold ${
          dark ? 'bg-violet-900/40 text-violet-300' : 'bg-violet-100 text-violet-700'
        }`}>Admin</span>
      </div>

      {/* Menu items */}
      <div className="py-1">
        {items.map((item, i) =>
          item.divider ? (
            <div key={i} className={`my-1 border-t ${divider}`} />
          ) : (
            <button
              key={item.label}
              onClick={item.action}
              className={`w-full flex items-center gap-2.5 px-4 py-2 text-xs font-medium transition-colors ${hover} ${
                item.danger
                  ? (dark ? 'text-red-400 hover:bg-red-900/20' : 'text-red-600 hover:bg-red-50')
                  : text
              }`}
            >
              <item.icon className="h-3.5 w-3.5 flex-shrink-0" />
              {item.label}
            </button>
          )
        )}
      </div>
    </div>
  );
}

// ── Header ──────────────────────────────────────────────────────────────────

function Header({ dark, setDark, activePage, notifs, onNotifRead, refreshing, onRefresh, onNavigate, onMobileMenu }) {
  const [notifOpen,   setNotifOpen]   = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const notifRef   = useRef(null);
  const profileRef = useRef(null);
  const notifBtnRef   = useRef(null);
  const profileBtnRef = useRef(null);

  const unread = notifs.filter(n => !n.read).length;

  // Close dropdowns on outside click
  useEffect(() => {
    function handler(e) {
      if (notifRef.current && !notifRef.current.contains(e.target) && !notifBtnRef.current?.contains(e.target))
        setNotifOpen(false);
      if (profileRef.current && !profileRef.current.contains(e.target) && !profileBtnRef.current?.contains(e.target))
        setProfileOpen(false);
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const bg      = dark ? 'bg-gray-900 border-gray-800' : 'bg-white border-gray-100';
  const text    = dark ? 'text-gray-100' : 'text-gray-900';
  const muted   = dark ? 'text-gray-400' : 'text-gray-500';
  const btnCls  = `flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-medium transition-colors ${
    dark ? 'border-purple-800/50 text-purple-300 hover:bg-purple-900/30' : 'border-purple-200 text-gray-600 hover:bg-purple-50'
  }`;

  // Breadcrumb
  const crumbs = BREADCRUMBS[activePage] || ['Dashboard'];

  // Simulated online
  const online = true;
  const [lastUpdate, setLastUpdate] = useState(new Date());
  useEffect(() => { if (!refreshing) setLastUpdate(new Date()); }, [refreshing]);

  function relTime(d) {
    const s = Math.floor((Date.now() - d) / 1000);
    if (s < 60) return `${s}s ago`;
    return `${Math.floor(s / 60)}m ago`;
  }

  return (
    <header className={`flex items-center h-14 px-4 gap-3 border-b flex-shrink-0 ${bg}`}>
      {/* Mobile hamburger */}
      <button
        onClick={onMobileMenu}
        className={`lg:hidden flex-shrink-0 rounded-lg p-1.5 transition-colors ${
          dark ? 'text-gray-400 hover:text-gray-200 hover:bg-gray-700' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
        }`}
      >
        <MenuIcon className="h-5 w-5" />
      </button>

      {/* Breadcrumb + page title */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          {crumbs.map((crumb, i) => (
            <span key={crumb} className="flex items-center gap-1.5">
              {i > 0 && <span className={`text-xs ${muted}`}>/</span>}
              <span className={`text-xs ${i === crumbs.length - 1 ? `font-bold ${text}` : muted}`}>
                {crumb}
              </span>
            </span>
          ))}
        </div>
      </div>

      {/* System status */}
      <div className="hidden sm:flex items-center gap-1.5">
        <span className="relative flex h-2 w-2">
          <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${online ? 'bg-green-400 animate-ping' : 'bg-red-400'}`} />
          <span className={`relative inline-flex h-2 w-2 rounded-full ${online ? 'bg-green-500' : 'bg-red-500'}`} />
        </span>
        <span className={`text-xs ${muted}`}>{online ? 'Online' : 'Offline'}</span>
        <span className={`text-xs ${muted} hidden md:inline`}>· Updated {relTime(lastUpdate)}</span>
      </div>

      {/* Refresh */}
      <button onClick={onRefresh} disabled={refreshing} className={btnCls}>
        <RefreshIcon className="h-3.5 w-3.5" spinning={refreshing} />
        <span className="hidden sm:inline">Refresh</span>
      </button>

      {/* Dark toggle */}
      <button onClick={() => setDark(d => !d)} className={btnCls}>
        {dark ? <SunIcon className="h-3.5 w-3.5" /> : <MoonIcon className="h-3.5 w-3.5" />}
      </button>

      {/* Notification bell */}
      <div className="relative">
        <button
          ref={notifBtnRef}
          onClick={() => { setNotifOpen(o => !o); setProfileOpen(false); }}
          className={`relative flex items-center justify-center h-8 w-8 rounded-xl transition-colors ${
            notifOpen
              ? (dark ? 'bg-purple-900/50 text-violet-400' : 'bg-violet-50 text-violet-600')
              : (dark ? 'text-purple-400 hover:bg-purple-900/30 hover:text-purple-200' : 'text-gray-500 hover:bg-purple-50 hover:text-gray-700')
          }`}
        >
          <BellIcon className="h-4.5 w-4.5 h-[18px] w-[18px]" />
          {unread > 0 && (
            <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-violet-600 text-white text-[10px] font-bold leading-none">
              {unread > 9 ? '9+' : unread}
            </span>
          )}
        </button>
        {notifOpen && (
          <NotifPanel dark={dark} notifs={notifs} onRead={onNotifRead} onClose={() => setNotifOpen(false)} panelRef={notifRef} />
        )}
      </div>

      {/* User profile */}
      <div className="relative">
        <button
          ref={profileBtnRef}
          onClick={() => { setProfileOpen(o => !o); setNotifOpen(false); }}
          className={`flex items-center gap-2 rounded-xl px-2 py-1.5 transition-colors ${
            profileOpen
              ? (dark ? 'bg-gray-700' : 'bg-gray-100')
              : (dark ? 'hover:bg-gray-700' : 'hover:bg-gray-50')
          }`}
        >
          <div className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold ${
            dark ? 'bg-violet-900 text-violet-300' : 'bg-violet-100 text-violet-700'
          }`}>AC</div>
          <span className={`hidden md:block text-xs font-semibold ${text}`}>Alex</span>
          <ChevronIcon className={`hidden md:block h-3 w-3 ${muted}`} open={profileOpen} />
        </button>
        {profileOpen && (
          <ProfileDropdown dark={dark} onNavigate={(page) => { onNavigate(page); setProfileOpen(false); }} dropRef={profileRef} />
        )}
      </div>
    </header>
  );
}

// ── Mobile overlay sidebar ──────────────────────────────────────────────────

function MobileDrawer({ dark, activePage, onNavigate, onClose }) {
  const bg = dark ? 'bg-gray-900' : 'bg-white';
  const muted = dark ? 'text-gray-400' : 'text-gray-500';
  const text = dark ? 'text-gray-100' : 'text-gray-900';

  // Trap scroll
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      {/* Drawer */}
      <div className={`absolute left-0 top-0 bottom-0 w-64 flex flex-col shadow-2xl ${bg}`}
        style={{ animation: 'slideInLeft 0.25s ease' }}>

        {/* Header */}
        <div className={`flex items-center justify-between h-14 px-4 border-b ${dark ? 'border-gray-800' : 'border-gray-100'}`}>
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-600 text-white font-bold text-sm">N</div>
            <span className={`text-sm font-bold ${dark ? 'text-violet-400' : 'text-violet-600'}`}>NimbusFlow</span>
          </div>
          <button onClick={onClose} className={`rounded-lg p-1.5 ${dark ? 'text-gray-400 hover:bg-gray-700' : 'text-gray-500 hover:bg-gray-100'}`}>
            <XIcon className="h-5 w-5" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
          {NAV_ITEMS.map(item => {
            const active = activePage === item.id;
            return (
              <button
                key={item.id}
                onClick={() => { onNavigate(item.id); onClose(); }}
                className={`w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors relative ${
                  active
                    ? (dark ? 'bg-violet-900/50 text-violet-400' : 'bg-violet-50 text-violet-700')
                    : (dark ? 'text-purple-400 hover:bg-purple-900/30 hover:text-purple-200' : 'text-gray-600 hover:bg-purple-50 hover:text-gray-900')
                }`}
              >
                {active && <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-r bg-violet-500" />}
                <span className="text-base leading-none">{item.emoji}</span>
                <span className="flex-1 text-xs text-left">{item.label}</span>
                {item.badge && (
                  <span className={`rounded-full px-1.5 py-0.5 text-xs font-bold ${
                    item.urgent ? (dark ? 'bg-red-900/60 text-red-300' : 'bg-red-100 text-red-700') : (dark ? 'bg-violet-900/60 text-violet-300' : 'bg-violet-100 text-violet-700')
                  }`}>{item.badge}</span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Footer */}
        <div className={`flex items-center gap-2.5 px-4 py-3 border-t ${dark ? 'border-gray-800' : 'border-gray-100'}`}>
          <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${dark ? 'bg-blue-800 text-blue-200' : 'bg-blue-100 text-blue-700'}`}>AC</div>
          <div>
            <p className={`text-xs font-semibold ${text}`}>Alex Chen</p>
            <p className={`text-xs ${muted}`}>Admin</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Bottom navigation (mobile) ──────────────────────────────────────────────

function BottomNav({ dark, activePage, onNavigate }) {
  const bg   = dark ? 'bg-gray-900 border-gray-800' : 'bg-white border-gray-100';
  const bottomItems = NAV_ITEMS.filter(n => BOTTOM_NAV.includes(n.id));

  return (
    <nav className={`fixed bottom-0 left-0 right-0 z-40 flex items-stretch border-t lg:hidden ${bg}`}
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}>
      {bottomItems.map(item => {
        const active = activePage === item.id;
        return (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            className={`flex-1 flex flex-col items-center justify-center gap-1 py-2 text-xs font-medium transition-colors relative ${
              active
                ? (dark ? 'text-violet-400' : 'text-violet-600')
                : (dark ? 'text-purple-600 hover:text-purple-300' : 'text-gray-500 hover:text-gray-700')
            }`}
          >
            {active && <span className={`absolute top-0 left-1/2 -translate-x-1/2 h-0.5 w-8 rounded-b ${dark ? 'bg-violet-400' : 'bg-violet-600'}`} />}
            <span className="text-lg leading-none relative">
              {item.emoji}
              {item.badge && (
                <span className={`absolute -top-1 -right-2 flex h-3.5 w-3.5 items-center justify-center rounded-full text-white text-[8px] font-bold ${item.urgent ? 'bg-red-500' : 'bg-violet-600'}`}>
                  {item.badge > 9 ? '9+' : item.badge}
                </span>
              )}
            </span>
            <span className="text-[10px] leading-none">{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

// ── Main Layout ─────────────────────────────────────────────────────────────

export default function Layout({ children, demo = false }) {
  const [dark,         setDark]         = useState(false);
  const [activePage,   setActivePage]   = useState('dashboard');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileOpen,   setMobileOpen]   = useState(false);
  const [refreshing,   setRefreshing]   = useState(false);
  const [notifs,       setNotifs]       = useState(MOCK_NOTIFS);
  const [toast,        setToast]        = useState(null);

  // Sync dark mode with localStorage
  useEffect(() => {
    const saved = localStorage.getItem('nf-dark');
    if (saved !== null) setDark(saved === 'true');
  }, []);
  useEffect(() => {
    localStorage.setItem('nf-dark', dark);
    document.documentElement.classList.toggle('dark', dark);
  }, [dark]);

  // Handle URL-based routing (when not in demo mode)
  useEffect(() => {
    if (demo) return;
    const path = window.location.pathname;
    const match = NAV_ITEMS.find(n => path.startsWith(n.path) && n.path !== '/admin') || NAV_ITEMS[0];
    setActivePage(match.id);
  }, [demo]);

  const handleNavigate = (pageId) => {
    setActivePage(pageId);
    if (!demo) {
      const item = NAV_ITEMS.find(n => n.id === pageId);
      if (item) window.history.pushState({}, '', item.path);
    }
  };

  const handleRefresh = () => {
    setRefreshing(true);
    setTimeout(() => setRefreshing(false), 1200);
  };

  const handleNotifRead = (id) => {
    setNotifs(prev =>
      id === 'all'
        ? prev.map(n => ({ ...n, read: true }))
        : prev.map(n => n.id === id ? { ...n, read: true } : n)
    );
  };

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  // Keyboard shortcut: Cmd/Ctrl + B to toggle sidebar
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
        e.preventDefault();
        setSidebarCollapsed(c => !c);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // ── Theme classes ──────────────────────────────────────────────────────

  const bg   = dark ? 'bg-gray-950' : 'bg-purple-50/30';
  const text = dark ? 'text-gray-100' : 'text-gray-900';

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <ThemeContext.Provider value={{ dark, setDark }}>
      <style>{`
        @keyframes fadeIn      { from { opacity:0; transform:translateY(4px) } to { opacity:1; transform:translateY(0) } }
        @keyframes slideInLeft { from { opacity:0; transform:translateX(-100%) } to { opacity:1; transform:translateX(0) } }
        @keyframes toastIn     { from { opacity:0; transform:translateY(16px) } to { opacity:1; transform:translateY(0) } }
        .fade-in  { animation: fadeIn  0.3s ease both }
        .toast-in { animation: toastIn 0.3s ease both }
      `}</style>

      <div className={`flex h-screen overflow-hidden ${bg} transition-colors duration-300`}>

        {/* ── Desktop sidebar ────────────────────────────────────────── */}
        <div className="hidden lg:flex flex-shrink-0">
          <Sidebar
            dark={dark}
            activePage={activePage}
            onNavigate={handleNavigate}
            collapsed={sidebarCollapsed}
            onCollapse={() => setSidebarCollapsed(c => !c)}
          />
        </div>

        {/* ── Mobile drawer ──────────────────────────────────────────── */}
        {mobileOpen && (
          <MobileDrawer
            dark={dark}
            activePage={activePage}
            onNavigate={handleNavigate}
            onClose={() => setMobileOpen(false)}
          />
        )}

        {/* ── Main content column ────────────────────────────────────── */}
        <div className="flex flex-col flex-1 min-w-0">

          {/* Header */}
          <Header
            dark={dark}
            setDark={setDark}
            activePage={activePage}
            notifs={notifs}
            onNotifRead={handleNotifRead}
            refreshing={refreshing}
            onRefresh={handleRefresh}
            onNavigate={handleNavigate}
            onMobileMenu={() => setMobileOpen(true)}
          />

          {/* Scrollable main area */}
          <main className={`flex-1 overflow-y-auto pb-20 lg:pb-0 fade-in`} key={activePage}>
            {demo ? (
              <DemoPage page={activePage} dark={dark} />
            ) : (
              children
            )}
          </main>
        </div>
      </div>

      {/* ── Mobile bottom nav ──────────────────────────────────────────── */}
      <BottomNav dark={dark} activePage={activePage} onNavigate={handleNavigate} />

      {/* ── Toast ────────────────────────────────────────────────────── */}
      {toast && (
        <div className={`fixed bottom-20 lg:bottom-6 right-6 z-50 toast-in flex items-center gap-2.5 rounded-xl px-4 py-3 text-sm font-medium shadow-lg ${
          toast.type === 'success'
            ? (dark ? 'bg-green-800 text-green-100' : 'bg-green-600 text-white')
            : (dark ? 'bg-red-800 text-red-100'     : 'bg-red-600 text-white')
        }`}>
          {toast.type === 'success' ? <CheckIcon className="h-4 w-4" /> : <XIcon className="h-4 w-4" />}
          {toast.msg}
        </div>
      )}
    </ThemeContext.Provider>
  );
}
