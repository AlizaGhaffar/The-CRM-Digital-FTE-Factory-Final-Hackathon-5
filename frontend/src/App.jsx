import { Routes, Route, Navigate, Outlet } from 'react-router-dom'
import Layout from '../components/Layout'
import LandingPage from '../components/LandingPage'
import SupportForm from '../components/SupportForm'
import AdminDashboard from '../components/AdminDashboard'
import EscalationsQueue from '../components/EscalationsQueue'
import KnowledgeBaseManager from '../components/KnowledgeBaseManager'
import AnalyticsDashboard from '../components/AnalyticsDashboard'
import ChannelConfig from '../components/ChannelConfig'
import ConversationViewer from '../components/ConversationViewer'
import TicketStatus from '../components/TicketStatus'

// Wraps Layout with <Outlet> so nested routes render inside the sidebar
function AdminLayout() {
  return (
    <Layout>
      <Outlet />
    </Layout>
  )
}

export default function App() {
  return (
    <Routes>
      {/* Public: Landing Page */}
      <Route path="/" element={<LandingPage />} />
      {/* Public: Support Form (also opened as modal from landing page) */}
      <Route path="/support" element={<SupportForm apiEndpoint="/support/submit" />} />
      <Route path="/ticket/:ticketId" element={<TicketStatus />} />

      {/* Admin Panel */}
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<AdminDashboard />} />
        <Route path="tickets" element={<AdminDashboard />} />
        <Route path="conversations" element={<ConversationViewer />} />
        <Route path="escalations" element={<EscalationsQueue />} />
        <Route path="knowledge" element={<KnowledgeBaseManager />} />
        <Route path="analytics" element={<AnalyticsDashboard />} />
        <Route path="channels" element={<ChannelConfig />} />
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
