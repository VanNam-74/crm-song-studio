import { lazy } from 'react'
import { Route, Routes } from 'react-router-dom'
import { RequireAuth } from './auth/RequireAuth'
import AdminLayout from './layouts/AdminLayout'
import Login from './pages/Login'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Jobs = lazy(() => import('./pages/Jobs'))
const Sites = lazy(() => import('./pages/Sites'))
const Prompts = lazy(() => import('./pages/Prompts'))
const Providers = lazy(() => import('./pages/Providers'))
const JobDetail = lazy(() => import('./pages/JobDetail'))


export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route element={<RequireAuth />}>
        <Route element={<AdminLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="jobs" element={<Jobs />} />
          <Route path="jobs/:id" element={<JobDetail />} />


          <Route element={<RequireAuth roles={['admin']} />}>
            <Route path="sites" element={<Sites />} />
            <Route path="prompts" element={<Prompts />} />
            <Route path="providers" element={<Providers />} />
          </Route>
        </Route>
      </Route>

      <Route path="/403" element={<p>You don't have access to this page.</p>} />
      <Route path="*" element={<p>Page not found.</p>} />
    </Routes>
  )
}