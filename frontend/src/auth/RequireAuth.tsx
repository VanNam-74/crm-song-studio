import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { Loading } from '../components/Loading/Loading'
import { useAuth, type Role } from './AuthProvider'

export function RequireAuth({ roles }: { roles?: Role[] }) {
    const { user, isLoading } = useAuth()
    const location = useLocation()

    if (isLoading) return <Loading variant="fullscreen" label="Loading…" />
    if (!user) return <Navigate to="/login" replace state={{ from: location }} />
    if (roles && !roles.includes(user.role)) return <Navigate to="/403" replace />
    return <Outlet />
}
