export function span(ms: number) {
    const m = Math.round(Math.abs(ms) / 60_000)
    if (m < 60) return `${m}m`
    const h = Math.floor(m / 60)
    if (h < 24) return m % 60 && h < 6 ? `${h}h ${m % 60}m` : `${h}h`
    const d = Math.floor(h / 24)
    return h % 24 ? `${d}d ${h % 24}h` : `${d}d`
}

export function dueLabel(iso: string) {
    const diff = new Date(iso).getTime() - Date.now()
    return diff < 0 ? `Overdue ${span(diff)}` : `Due in ${span(diff)}`
}

export function ago(iso: string) {
    const diff = Date.now() - new Date(iso).getTime()
    return diff < 60_000 ? 'just now' : `${span(diff)} ago`
}

const dateFmt = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })

export function formatDate(iso: string) {
    return dateFmt.format(new Date(iso))
}

export function formatDuration(sec: number | string | null | undefined) {
    const s = Math.round(Number(sec) || 0)
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export function formatBytes(n: number | null | undefined) {
    if (!n) return ''
    return n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.round(n / 1024)} KB`
}

export async function copyText(text: string) {
    try {
        await navigator.clipboard.writeText(text)
        return true
    } catch {
        const el = document.createElement('textarea')
        el.value = text
        el.style.position = 'fixed'
        el.style.opacity = '0'
        document.body.appendChild(el)
        el.select()
        const ok = document.execCommand('copy')
        el.remove()
        return ok
    }
}