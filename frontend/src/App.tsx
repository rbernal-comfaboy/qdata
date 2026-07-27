import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './hooks/useAuth'
import { useTheme } from './hooks/useTheme'
import Layout from './components/layout/Layout'
import { Loader2 } from 'lucide-react'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Login = lazy(() => import('./pages/Login'))
const Register = lazy(() => import('./pages/Register'))
const Analyze = lazy(() => import('./pages/Analyze'))
const Reports = lazy(() => import('./pages/Reports'))
const ReportDetail = lazy(() => import('./pages/ReportDetail'))
const RuleDetail = lazy(() => import('./pages/RuleDetail'))
const ErrorDetail = lazy(() => import('./pages/ErrorDetail'))
const Rules = lazy(() => import('./pages/Rules'))
const Scheduler = lazy(() => import('./pages/Scheduler'))
const SchedulerNew = lazy(() => import('./pages/SchedulerNew'))
const Settings = lazy(() => import('./pages/Settings'))
const Processes = lazy(() => import('./pages/Processes'))
const ProcessDetail = lazy(() => import('./pages/ProcessDetail'))
const DataSources = lazy(() => import('./pages/DataSources'))
const Connections = lazy(() => import('./pages/Connections'))
const Sources = lazy(() => import('./pages/Sources'))
const SourceForm = lazy(() => import('./pages/SourceForm'))
const Groups = lazy(() => import('./pages/Groups'))
const GroupDashboard = lazy(() => import('./pages/GroupDashboard'))
const AdminUsers = lazy(() => import('./pages/AdminUsers'))

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
    </div>
  )
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token)
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  useTheme()
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
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
      </Suspense>
    </BrowserRouter>
  )
}
