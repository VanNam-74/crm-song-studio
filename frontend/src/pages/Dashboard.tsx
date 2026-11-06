import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import '../styles/Page.css'

const SHORTCUTS = [
    { to: '/jobs', track: '02', title: 'Jobs', text: 'Duyệt lyric, chọn bản nhạc, copy sang HIS CRM.', admin: false },
    { to: '/sites', track: '03', title: 'Sites', text: 'Website gửi đơn, webhook và secret.', admin: true },
    { to: '/prompts', track: '04', title: 'Prompts', text: 'Prompt viết lyric và các phiên bản.', admin: true },
    { to: '/providers', track: '05', title: 'Music providers', text: 'Suno cookie, credit và giới hạn tốc độ.', admin: true },
]

export default function Dashboard() {
    const { user } = useAuth()
    const name = user?.full_name || user?.email?.split('@')[0]
    const items = SHORTCUTS.filter((s) => !s.admin || user?.role === 'admin')

    return (
        <div className="pg">
            <header className="pg-head">
                <div className="pg-eyebrow">
                    <span className="pg-mini-eq" aria-hidden="true"><i /><i /><i /><i /></span>
                    Track 01 · Dashboard
                </div>
                <h1 className="pg-title">Chào {name}.</h1>
                <p className="pg-sub">Phòng thu đã sẵn sàng. Chọn một mục để bắt đầu.</p>
            </header>

            <section className="pg-grid" aria-label="Lối tắt">
                {items.map((s) => (
                    <Link key={s.to} to={s.to} className="pg-card">
                        <span className="pg-card-track">{s.track}</span>
                        <span className="pg-card-title">{s.title}</span>
                        <span className="pg-card-text">{s.text}</span>
                    </Link>
                ))}
            </section>
        </div>
    )
}