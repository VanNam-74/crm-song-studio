import { useEffect, useId, useRef, useState, type CSSProperties, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useAuth } from '../auth/AuthProvider'
import '../styles/Login.css'

type Phase = 'idle' | 'loading' | 'success'

const copy = {
    eyebrow: 'TRACK 01 · LOGIN',
    title: 'Welcome Back',
    subtitle: 'Log in to enter the Song Studio.',
    email: 'Email',
    password: 'Password',
    otp: 'Verification Code',
    otpHint: '6 digits from your 2FA app',
    submit: 'Log In',
    loading: 'Placing the needle on the record…',
    showPassword: 'Show Password',
    hidePassword: 'Hide Password',
    missing: 'Missing notes — please enter both email and password.',
    wrong: 'Wrong email, password or verification code.',
    tooMany: 'Too many attempts — please wait a bit before trying again.',
    offline: 'Unable to connect to the studio. Please check your internet connection and try again.',
    footnote: 'Forgot your password or lost your 2FA device? Please contact an administrator to reset it.',
    welcome: 'Welcome Back',
    welcomeText: 'Opening the Song Studio…',
    status: {
        idle: ['STANDBY', 'Ready — the needle will drop when you log in.'],
        loading: ['CUEING', 'Connecting to the studio…'],
        success: ['NOW PLAYING', 'Successfully entered the studio.'],
    } as Record<Phase, [string, string]>,
}

const strength = (len: number) => {
    if (len === 0) return { mark: '—', text: 'not entered', max: 0 }
    if (len < 6) return { mark: 'p', text: 'weak', max: 8 }
    if (len < 10) return { mark: 'mf', text: 'medium', max: 12 }
    return { mark: 'ff', text: 'strong', max: 16 }
}

const prefersReducedMotion = () =>
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

export default function Login() {
    const { user, login } = useAuth()
    const navigate = useNavigate()
    const location = useLocation()
    const fromPath = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname
    const from = fromPath && fromPath !== '/login' ? fromPath : '/'

    const [phase, setPhase] = useState<Phase>('idle')
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [otp, setOtp] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [shake, setShake] = useState(false)
    const [welcomeName, setWelcomeName] = useState('')

    const labelPathId = useId().replace(/:/g, '')
    const redirectTimer = useRef<number | undefined>(undefined)
    useEffect(() => () => window.clearTimeout(redirectTimer.current), [])

    if (user && phase === 'idle') return <Navigate to={from} replace />

    const fail = (message: string) => {
        setError(message)
        setShake(true)
    }

    const onSubmit = async (e: FormEvent) => {
        e.preventDefault()
        if (phase !== 'idle') return
        if (!email.trim() || !password) {
            fail(copy.missing)
            return
        }
        setError(null)
        setPhase('loading')
        const started = Date.now()
        try {
            await login(email.trim(), password, otp.trim() || undefined)
            await sleep(Math.max(0, 900 - (Date.now() - started)))
            setWelcomeName(email.trim().split('@')[0])
            setPhase('success')
            redirectTimer.current = window.setTimeout(
                () => navigate(from, { replace: true }),
                prefersReducedMotion() ? 400 : 2600,
            )
        } catch (err) {
            setPhase('idle')
            const status = axios.isAxiosError(err) ? err.response?.status : undefined
            fail(status === 401 || status === 400 ? copy.wrong : status === 429 ? copy.tooMany : copy.offline)
        }
    }

    const meter = strength(password.length)
    const litBars = Math.min(20, Math.round(password.length * 1.6))
    const [statusLabel, statusText] = copy.status[phase]

    return (
        <div className={`sa-root phase-${phase}`}>
            <div className="sa-bg" aria-hidden="true">
                <span className="sa-blob b1" />
                <span className="sa-blob b2" />
                <span className="sa-blob b3" />
                <div className="sa-staff s1"><i /><i /><i /><i /><i /></div>
                <div className="sa-staff s2"><i /><i /><i /><i /><i /></div>
                <QuarterNote className="sa-note n1" />
                <BeamedNotes className="sa-note n2 soft" />
                <EighthNote className="sa-note n3" />
                <HalfNote className="sa-note n4 soft" />
                <EighthNote className="sa-note n5 soft" />
                <QuarterNote className="sa-note n6" />
            </div>

            <div className="sa-playhead" aria-hidden="true" />

            <main className="sa-main">
                <section className="sa-stage">
                    <header className="sa-brand">
                        <LogoMark />
                        <div>
                            <div className="sa-brand-name">Song Studio</div>
                            <div className="sa-mono sa-brand-sub">HEART INTO SONG · CONSOLE</div>
                        </div>
                    </header>

                    <div className="sa-deck">
                        <span className="sa-halo h1" aria-hidden="true" />
                        <span className="sa-halo h2" aria-hidden="true" />
                        <div className="sa-disc" role="img" aria-label="Đĩa than Side A đang quay">
                            <Vinyl pathId={`sa-label-${labelPathId}`} />
                            <span className="sa-sheen" />
                        </div>
                        <Tonearm />
                    </div>

                    <div className="sa-caption">
                        <span className="sa-dot" aria-hidden="true" />
                        <span className="sa-mono">{statusLabel}</span>
                        <span>{statusText}</span>
                    </div>
                </section>

                <section className="sa-panel">
                    <div className="sa-ghost" aria-hidden="true" />
                    <div className={`sa-card${shake ? ' is-shaking' : ''}`} onAnimationEnd={() => setShake(false)}>
                        {phase !== 'success' ? (
                            <form className="sa-form" onSubmit={onSubmit} noValidate aria-busy={phase === 'loading'}>
                                <div className="sa-eyebrow">
                                    <span className="sa-mini-eq" aria-hidden="true"><i /><i /><i /><i /></span>
                                    <span className="sa-mono">{copy.eyebrow}</span>
                                </div>
                                <h1 className="sa-title">{copy.title}</h1>
                                <p className="sa-sub">{copy.subtitle}</p>

                                {error && (
                                    <div className="sa-alert" role="alert">
                                        <AlertIcon />
                                        <span>{error}</span>
                                    </div>
                                )}

                                <div className="sa-field">
                                    <label className="sa-label" htmlFor="sa-email">{copy.email}</label>
                                    <input
                                        id="sa-email"
                                        className="sa-input"
                                        type="email"
                                        autoComplete="username"
                                        inputMode="email"
                                        placeholder="ban@thenewmoon.work"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        disabled={phase === 'loading'}
                                    />
                                </div>

                                <div className="sa-field">
                                    <label className="sa-label" htmlFor="sa-password">{copy.password}</label>
                                    <div className="sa-pass">
                                        <input
                                            id="sa-password"
                                            className="sa-input"
                                            type={showPassword ? 'text' : 'password'}
                                            autoComplete="current-password"
                                            placeholder="••••••••••"
                                            value={password}
                                            onChange={(e) => setPassword(e.target.value)}
                                            disabled={phase === 'loading'}
                                        />
                                        <button
                                            type="button"
                                            className="sa-eye"
                                            aria-label={showPassword ? copy.hidePassword : copy.showPassword}
                                            aria-pressed={showPassword}
                                            onClick={() => setShowPassword((v) => !v)}
                                        >
                                            <span key={showPassword ? 'on' : 'off'} className="sa-eye-icon">
                                                {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                                            </span>
                                        </button>
                                    </div>
                                    <div className="sa-meter">
                                        <div className="sa-meter-bars" aria-hidden="true">
                                            {Array.from({ length: 20 }, (_, i) => {
                                                const on = i < litBars
                                                const h = on ? 6 + (((i * 7) % 11) / 10) * meter.max : 4
                                                return <i key={i} className={on ? 'on' : undefined} style={{ height: h }} />
                                            })}
                                        </div>
                                        <span className="sa-meter-label" aria-hidden="true">{meter.mark}</span>
                                        <span className="sa-sr" aria-live="polite">Độ mạnh mật khẩu: {meter.text}</span>
                                    </div>
                                </div>

                                <div className="sa-field">
                                    <label className="sa-label" htmlFor="sa-otp">
                                        {copy.otp} <small>· {copy.otpHint}</small>
                                    </label>
                                    <input
                                        id="sa-otp"
                                        className="sa-input sa-otp"
                                        type="text"
                                        inputMode="numeric"
                                        autoComplete="one-time-code"
                                        pattern="[0-9]*"
                                        placeholder="000000"
                                        value={otp}
                                        onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                        disabled={phase === 'loading'}
                                    />
                                </div>

                                <button type="submit" className="sa-btn sa-btn-primary" disabled={phase === 'loading'}>
                                    {phase === 'loading' ? (
                                        <>
                                            <span className="sa-btn-eq" aria-hidden="true"><i /><i /><i /><i /><i /></span>
                                            {copy.loading}
                                        </>
                                    ) : (
                                        <>
                                            <span className="sa-play" aria-hidden="true"><PlayIcon /></span>
                                            {copy.submit}
                                        </>
                                    )}
                                </button>

                                <p className="sa-foot">{copy.footnote}</p>
                            </form>
                        ) : (
                            <div className="sa-welcome" role="status">
                                <div className="sa-eyebrow">
                                    <span className="sa-mini-eq" aria-hidden="true"><i /><i /><i /><i /></span>
                                    <span className="sa-mono">NOW PLAYING</span>
                                </div>
                                <h1 className="sa-title">
                                    {copy.welcome}
                                    {welcomeName ? `, ${welcomeName}` : ''}.
                                </h1>
                                <p className="sa-sub">{copy.welcomeText}</p>
                                <div className="sa-wave" aria-hidden="true">
                                    {Array.from({ length: 32 }, (_, i) => (
                                        <i
                                            key={i}
                                            style={{
                                                height: 14 + Math.abs(Math.sin(i * 1.7)) * 42,
                                                animationDelay: `${(i % 8) * 0.09}s`,
                                            }}
                                        />
                                    ))}
                                </div>
                                <div className="sa-progress">
                                    <span className="sa-mono">0:00</span>
                                    <span className="sa-track"><span /></span>
                                    <span className="sa-mono">3:24</span>
                                </div>
                            </div>
                        )}

                        {phase === 'success' && (
                            <div className="sa-rise" aria-hidden="true">
                                <QuarterNote style={{ left: '14%', width: 18, animationDelay: '0s' }} />
                                <EighthNote style={{ left: '32%', width: 22, animationDelay: '.25s' }} />
                                <BeamedNotes style={{ left: '50%', width: 34, animationDelay: '.1s' }} />
                                <HalfNote style={{ left: '68%', width: 18, animationDelay: '.4s' }} />
                                <EighthNote style={{ left: '84%', width: 20, animationDelay: '.6s' }} />
                            </div>
                        )}
                    </div>
                </section>
            </main>
        </div>
    )
}

type SvgProps = { className?: string; style?: CSSProperties }

function Vinyl({ pathId }: { pathId: string }) {
    const grooves = [192, 181, 170, 159, 148, 136, 123, 110, 96]
    return (
        <svg className="sa-vinyl" viewBox="0 0 400 400" aria-hidden="true">
            <defs>
                <path id={pathId} d="M200,200 m-54,0 a54,54 0 1,1 108,0 a54,54 0 1,1 -108,0" />
            </defs>
            <circle cx="200" cy="200" r="200" fill="#141414" />
            {grooves.map((r, i) => (
                <circle key={r} cx="200" cy="200" r={r} fill="none" stroke={`rgba(255,255,255,${i % 2 ? 0.04 : 0.08})`} strokeWidth="1" />
            ))}
            <circle cx="200" cy="200" r="72" fill="#F2F2EF" />
            <circle cx="200" cy="200" r="65" fill="none" stroke="rgba(0,0,0,.14)" />
            <text fontFamily="'JetBrains Mono', monospace" fontSize="10" fontWeight="500" letterSpacing="2.6" fill="#111">
                <textPath href={`#${pathId}`}>SIDE A · TRACK 01 · 33⅓ RPM ·</textPath>
            </text>
            <text x="200" y="186" textAnchor="middle" fontFamily="'Playfair Display', Georgia, serif" fontStyle="italic" fontSize="17" fill="#111">
                Side A
            </text>
            <circle cx="200" cy="200" r="5" fill="#F6F6F4" stroke="rgba(0,0,0,.25)" />
            <text x="200" y="226" textAnchor="middle" fontFamily="'JetBrains Mono', monospace" fontSize="8" letterSpacing="2" fill="#555">
                STEREO
            </text>
        </svg>
    )
}

function Tonearm() {
    return (
        <svg className="sa-arm" viewBox="0 0 160 300" aria-hidden="true">
            <circle cx="134" cy="12" r="10" fill="#1E1E1E" />
            <line x1="120" y1="30" x2="134" y2="12" stroke="#9A9A96" strokeWidth="5" strokeLinecap="round" />
            <line x1="120" y1="30" x2="72" y2="232" stroke="#D9D9D5" strokeWidth="6" strokeLinecap="round" />
            <line x1="120" y1="30" x2="72" y2="232" stroke="#FFFFFF" strokeWidth="1.5" strokeLinecap="round" opacity=".7" />
            <circle cx="120" cy="30" r="22" fill="#EDEDEA" stroke="rgba(0,0,0,.14)" />
            <circle cx="120" cy="30" r="9" fill="#111" />
            <rect x="58" y="226" width="26" height="40" rx="5" fill="#111" transform="rotate(14 71 246)" />
            <rect x="62" y="262" width="6" height="8" rx="1.5" fill="#555" transform="rotate(14 65 266)" />
        </svg>
    )
}

function LogoMark() {
    return (
        <svg width="38" height="38" viewBox="0 0 38 38" aria-hidden="true">
            <circle cx="19" cy="19" r="18" fill="#141414" />
            <circle cx="19" cy="19" r="13" fill="none" stroke="rgba(255,255,255,.1)" />
            <circle cx="19" cy="19" r="9" fill="none" stroke="rgba(255,255,255,.08)" />
            <circle cx="19" cy="19" r="6" fill="#F2F2EF" />
            <circle cx="19" cy="19" r="1.6" fill="#141414" />
        </svg>
    )
}

function QuarterNote({ className, style }: SvgProps) {
    return (
        <svg className={className} style={style} viewBox="0 0 32 56" aria-hidden="true">
            <ellipse cx="11" cy="46" rx="10" ry="7.5" transform="rotate(-22 11 46)" fill="currentColor" />
            <rect x="18.6" y="4" width="2.6" height="42" fill="currentColor" />
        </svg>
    )
}

function EighthNote({ className, style }: SvgProps) {
    return (
        <svg className={className} style={style} viewBox="0 0 34 56" aria-hidden="true">
            <ellipse cx="11" cy="46" rx="10" ry="7.5" transform="rotate(-22 11 46)" fill="currentColor" />
            <rect x="18.6" y="4" width="2.6" height="42" fill="currentColor" />
            <path d="M21.2 4c1 8 12 11 10 23 0-8-5-11-10-13z" fill="currentColor" />
        </svg>
    )
}

function BeamedNotes({ className, style }: SvgProps) {
    return (
        <svg className={className} style={style} viewBox="0 0 64 56" aria-hidden="true">
            <ellipse cx="11" cy="46" rx="10" ry="7.5" transform="rotate(-22 11 46)" fill="currentColor" />
            <ellipse cx="47" cy="42" rx="10" ry="7.5" transform="rotate(-22 47 42)" fill="currentColor" />
            <rect x="18.6" y="8" width="2.6" height="38" fill="currentColor" />
            <rect x="54.6" y="4" width="2.6" height="38" fill="currentColor" />
            <path d="M18.6 8 L57.2 3 L57.2 10 L18.6 15 Z" fill="currentColor" />
        </svg>
    )
}

function HalfNote({ className, style }: SvgProps) {
    return (
        <svg className={className} style={style} viewBox="0 0 32 56" aria-hidden="true">
            <ellipse cx="11" cy="46" rx="8.6" ry="6.2" transform="rotate(-22 11 46)" fill="none" stroke="currentColor" strokeWidth="3" />
            <rect x="18.2" y="4" width="2.6" height="40" fill="currentColor" />
        </svg>
    )
}

function PlayIcon() {
    return (
        <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
            <path d="M3.5 2.2v7.6L9.8 6z" fill="currentColor" />
        </svg>
    )
}

function EyeIcon() {
    return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" />
            <circle cx="12" cy="12" r="3" />
        </svg>
    )
}

function EyeOffIcon() {
    return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M3 3l18 18" />
            <path d="M10.6 5.1A10.7 10.7 0 0 1 12 5c6.4 0 10 7 10 7a17.6 17.6 0 0 1-3.2 4.1" />
            <path d="M6.6 6.6C3.8 8.4 2 12 2 12s3.6 7 10 7c1.9 0 3.6-.6 5-1.5" />
            <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
        </svg>
    )
}

function AlertIcon() {
    return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ flexShrink: 0, marginTop: 1 }}>
            <circle cx="12" cy="12" r="9" />
            <path d="M12 7.5v5.5" />
            <path d="M12 16.5h.01" />
        </svg>
    )
}
