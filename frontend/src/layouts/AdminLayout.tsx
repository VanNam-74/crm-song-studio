import { Suspense, useEffect, useState, type ComponentType } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth, type Role } from '../auth/AuthProvider'
import { PageSkeleton } from '../components/Skeleton/Skeleton'
import { ConfirmDialog } from '../components/ConfirmDialog/ConfirmDialog'
import './AdminLayout.css'

type NavItem = { to: string; label: string; icon: ComponentType; end?: boolean }
type NavSection = { title: string; roles?: Role[]; items: NavItem[] }

const NAV: NavSection[] = [
    {
        title: 'Studio',
        items: [
            { to: '/', label: 'Dashboard', icon: GridIcon, end: true },
            { to: '/jobs', label: 'Jobs', icon: NoteIcon },
        ],
    },
    {
        title: 'Configuration',
        roles: ['admin'],
        items: [
            { to: '/sites', label: 'Sites', icon: GlobeIcon },
            { to: '/prompts', label: 'Prompts', icon: DocIcon },
            { to: '/providers', label: 'Music providers', icon: SlidersIcon },
        ],
    },
]

export default function AdminLayout() {
    const { user, logout } = useAuth()
    const navigate = useNavigate()
    const location = useLocation()
    const [open, setOpen] = useState(false)
    const [confirmLogout, setConfirmLogout] = useState(false)

    useEffect(() => setOpen(false), [location.pathname])

    useEffect(() => {
        if (!open) return
        const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
        window.addEventListener('keydown', onKey)
        return () => window.removeEventListener('keydown', onKey)
    }, [open])

    const sections = NAV.filter((s) => !s.roles || (user && s.roles.includes(user.role)))
    let track = 0

    const handleLogout = async () => {
        await logout()
        navigate('/login', { replace: true })
    }

    const initials = (user?.full_name || user?.email || '?')
        .split(/[\s@.]+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((w) => w[0]?.toUpperCase())
        .join('')

    return (
        <div className={`al-root${open ? ' is-open' : ''}`}>
            <div className="al-bg" aria-hidden="true">
                <span className="al-blob b1" />
                <span className="al-blob b2" />
                <div className="al-staff"><i /><i /><i /><i /><i /></div>
            </div>

            <header className="al-topbar">
                <button
                    type="button"
                    className="al-menu-btn"
                    aria-label={open ? 'Đóng menu' : 'Mở menu'}
                    aria-expanded={open}
                    aria-controls="al-sidebar"
                    onClick={() => setOpen((v) => !v)}
                >
                    {open ? <CloseIcon /> : <MenuIcon />}
                </button>
                <Brand compact />
            </header>

            <div className="al-scrim" aria-hidden="true" onClick={() => setOpen(false)} />

            <aside id="al-sidebar" className="al-sidebar">
                <Brand />

                <nav className="al-nav" aria-label="Menu chính">
                    {sections.map((section) => (
                        <div key={section.title} className="al-section">
                            <div className="al-section-title">{section.title}</div>
                            {section.items.map((item) => {
                                track += 1
                                const Icon = item.icon
                                return (
                                    <NavLink
                                        key={item.to}
                                        to={item.to}
                                        end={item.end}
                                        className={({ isActive }) => `al-link${isActive ? ' is-active' : ''}`}
                                    >
                                        <span className="al-track">{String(track).padStart(2, '0')}</span>
                                        <span className="al-icon"><Icon /></span>
                                        <span className="al-label">{item.label}</span>
                                        <span className="al-eq" aria-hidden="true"><i /><i /><i /></span>
                                    </NavLink>
                                )
                            })}
                        </div>
                    ))}
                </nav>

                <div className="al-user">
                    <div className="al-user-row">
                        <span className="al-avatar" aria-hidden="true">{initials}</span>
                        <div className="al-user-text">
                            <div className="al-user-name">{user?.full_name || user?.email}</div>
                            <div className="al-user-role">{user?.role} · now playing</div>
                        </div>
                    </div>
                    <button type="button" className="al-logout" onClick={() => setConfirmLogout(true)}>
                        <LogoutIcon />
                        Logout
                    </button>
                </div>
            </aside>

            <main className="al-main">
                <Suspense fallback={<PageSkeleton />}>
                    <Outlet />
                </Suspense>
            </main>

            <ConfirmDialog
                open={confirmLogout}
                title="Tạm dừng phiên làm việc?"
                description="Bạn sẽ cần đăng nhập lại, kèm mã 2FA, để quay lại Song Studio."
                cancelLabel="Cancel"
                confirmLabel="Logout"
                busyLabel="Đang dừng nhạc…"
                onConfirm={handleLogout}
                onClose={() => setConfirmLogout(false)}
            />
        </div>
    )
}



function Brand({ compact }: { compact?: boolean }) {
    return (
        <div className={`al-brand${compact ? ' is-compact' : ''}`}>
            <svg className="al-logo" width="36" height="36" viewBox="0 0 38 38" aria-hidden="true">
                <circle cx="19" cy="19" r="18" fill="#141414" />
                <circle cx="19" cy="19" r="13" fill="none" stroke="rgba(255,255,255,.1)" />
                <circle cx="19" cy="19" r="9" fill="none" stroke="rgba(255,255,255,.08)" />
                <circle cx="19" cy="19" r="6" fill="#F2F2EF" />
                <circle cx="25" cy="19" r="1.2" fill="#141414" />
                <circle cx="19" cy="19" r="1.6" fill="#141414" />
            </svg>
            <div>
                <div className="al-brand-name">Song Studio</div>
                {!compact && <div className="al-brand-sub">Side A · Console</div>}
            </div>
        </div>
    )
}

const stroke = {
    width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
    strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true,
}

function GridIcon() {
    return <svg {...stroke}><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></svg>
}
function NoteIcon() {
    return <svg {...stroke}><path d="M9 18V5l11-2v13" /><circle cx="6" cy="18" r="3" /><circle cx="17" cy="16" r="3" /></svg>
}
function GlobeIcon() {
    return <svg {...stroke}><circle cx="12" cy="12" r="9" /><path d="M3 12h18" /><path d="M12 3a14 14 0 0 1 0 18a14 14 0 0 1 0-18" /></svg>
}
function DocIcon() {
    return <svg {...stroke}><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><path d="M14 3v6h6" /><path d="M8 13h8M8 17h5" /></svg>
}
function SlidersIcon() {
    return <svg {...stroke}><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6" /></svg>
}
function LogoutIcon() {
    return <svg {...stroke}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="M16 17l5-5-5-5" /><path d="M21 12H9" /></svg>
}
function MenuIcon() {
    return <svg {...stroke} width={22} height={22}><path d="M4 7h16M4 12h16M4 17h10" /></svg>
}
function CloseIcon() {
    return <svg {...stroke} width={22} height={22}><path d="M6 6l12 12M18 6L6 18" /></svg>
}