import { useEffect, useState, type CSSProperties } from 'react'
import './Loading.css'

type SpinnerSize = 'sm' | 'md' | 'lg' | number

const SIZES: Record<Exclude<SpinnerSize, number>, number> = { sm: 16, md: 24, lg: 36 }

export type SpinnerProps = {
    size?: SpinnerSize
    label?: string | null
    className?: string
    style?: CSSProperties
}

export function Spinner({ size = 'md', label = 'Đang tải', className, style }: SpinnerProps) {
    const px = typeof size === 'number' ? size : SIZES[size]
    const a11y = label === null ? { 'aria-hidden': true } : { role: 'status', 'aria-label': label }
    return (
        <span
            {...a11y}
            className={`ld-spinner${className ? ` ${className}` : ''}`}
            style={{ width: px, height: px, ...style }}
        >
            {Array.from({ length: 12 }, (_, i) => (
                <i key={i} style={{ transform: `rotate(${i * 30}deg)`, animationDelay: `${-1 + i / 12}s` }} />
            ))}
        </span>
    )
}

export type LoadingProps = {
    variant?: 'inline' | 'overlay' | 'fullscreen'
    label?: string
    size?: SpinnerSize
    delay?: number
    dim?: boolean
}

function useDelayedVisible(delay: number) {
    const [visible, setVisible] = useState(delay <= 0)
    useEffect(() => {
        if (delay <= 0) return
        const t = window.setTimeout(() => setVisible(true), delay)
        return () => window.clearTimeout(t)
    }, [delay])
    return visible
}

export function Loading({ variant = 'inline', label, size, delay, dim = true }: LoadingProps) {
    const visible = useDelayedVisible(delay ?? (variant === 'inline' ? 0 : 150))
    if (!visible) return null

    if (variant === 'inline') {
        return (
            <span className="ld-inline" role="status" aria-label={label ?? 'Đang tải'}>
                <Spinner size={size ?? 'sm'} label={null} />
                {label && <span className="ld-inline-label" aria-hidden="true">{label}</span>}
            </span>
        )
    }

    return (
        <div className={`ld-layer ld-${variant}${dim ? ' ld-dim' : ''}`}>
            <div className="ld-hud" role="status" aria-label={label ?? 'Đang tải'}>
                <Spinner size={size ?? 'lg'} label={null} />
                {label && <span className="ld-hud-label" aria-hidden="true">{label}</span>}
            </div>
        </div>
    )
}

export default Loading
