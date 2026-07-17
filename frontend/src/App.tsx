import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './hooks/useAuth'
import { useTheme } from './hooks/useTheme'
import Layout from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import Register from './pages/Register'
import Analyze from './pages/Analyze'
import Reports from './pages/Reports'
import ReportDetail from './pages/ReportDetail'
import RuleDetail from './pages/RuleDetail'
import ErrorDetail from './pages/ErrorDetail'
import Rules from './pages/Rules'
import Scheduler from './pages/Scheduler'
import SchedulerNew from './pages/SchedulerNew'
import Settings from './pages/Settings'
import Processes from './pages/Processes'
import ProcessDetail from './pages/ProcessDetail'
import DataSources from './pages/DataSources'
import Connections from './pages/Connections'
import Sources from './pages/Sources'
import SourceForm from './pages/SourceForm'
import Groups from './pages/Groups'
import GroupDashboard from './pages/GroupDashboard'
import AdminUsers from './pages/AdminUsers'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token)
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  useTheme()
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="processes" element={<Processes />} />
          <Route path="processes/:id" element={<ProcessDetail />} />
          <Route path="connections" element={<Connections />} />
          <Route path="datasources" element={<Sources />} />
          <Route path="datasources/new" element={<SourceForm />} />
          <Route path="datasources/:id/edit" element={<SourceForm />} />
          <Route path="analyze" element={<Analyze />} />
          <Route path="reports" element={<Reports />} />
          <Route path="reports/:id" element={<ReportDetail />} />
          <Route path="reports/:reportId/rules/:ruleIdx" element={<RuleDetail />} />
          <Route path="reports/:reportId/rules/:ruleIdx/errors/:errorIdx" element={<ErrorDetail />} />
          <Route path="rules" element={<Rules />} />
          <Route path="scheduler" element={<Scheduler />} />
          <Route path="scheduler/new" element={<SchedulerNew />} />
          <Route path="groups" element={<Groups />} />
          <Route path="groups/:groupId" element={<GroupDashboard />} />
          <Route path="settings" element={<Settings />} />
          <Route path="admin/users" element={<AdminUsers />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
