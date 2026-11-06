import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { fetchJobs, type Job, type JobStatus, type StatusGroup } from '../api/jobs'
import { Skeleton } from '../components/Skeleton/Skeleton'
import '../styles/Page.css'
import '../styles/Jobs.css'

const PAGE_SIZE = 25

const GROUPS: { key: StatusGroup; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'review', label: 'Lyric review' },
    { key: 'pick', label: 'Pick a take' },
    { key: 'progress', label: 'In progress' },
    { key: 'ready', label: 'Ready' },
    { key: 'done', label: 'Done' },
    { key: 'failed', label: 'Failed' },
    { key: 'overdue', label: 'Overdue' },
]

type Kind = 'need' | 'run' | 'wait' | 'done' | 'fail'

const STATUS: Record<JobStatus, { label: string; kind: Kind }> = {
    queued: { label: 'Queued', kind: 'wait' },
    generating_lyrics: { label: 'Writing lyrics', kind: 'run' },
    lyrics_ready: { label: 'Lyric review', kind: 'need' },
    lyrics_approved: { label: 'Lyrics approved', kind: 'wait' },
    generating_music: { label: 'Generating music', kind: 'run' },
    uploading: { label: 'Uploading to R2', kind: 'run' },
    music_ready: { label: 'Pick a take', kind: 'need' },
    ready: { label: 'Ready · copy to CRM', kind: 'need' },
    done: { label: 'Done', kind: 'done' },
    failed: { label: 'Failed', kind: 'fail' },
    cancelled: { label: 'Cancelled', kind: 'done' },
}

const isGroup = (v: string | null): v is StatusGroup => GROUPS.some((g) => g.key === v)

export default function Jobs() {
    const [params, setParams] = useSearchParams()
    const status: StatusGroup = isGroup(params.get('status')) ? (params.get('status') as StatusGroup) : 'all'
    const q = params.get('q') ?? ''
    const page = Math.max(1, Number(params.get('page')) || 1)

    const [search, setSearch] = useState(q)

    const update = (patch: Record<string, string | number | null>) => {
        const next = new URLSearchParams(params)
        for (const [k, v] of Object.entries(patch)) {
            if (v === null || v === '' || (k === 'status' && v === 'all') || (k === 'page' && v === 1)) next.delete(k)
            else next.set(k, String(v))
        }
        setParams(next, { replace: true })
    }

    useEffect(() => {
        const t = setTimeout(() => {
            if (search.trim() !== q) update({ q: search.trim(), page: 1 })
        }, 350)
        return () => clearTimeout(t)
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [search])

    const { data, isPending, isError, isFetching, refetch } = useQuery({
        queryKey: ['jobs', { status, q, page }],
        queryFn: () => fetchJobs({ status, q, page, page_size: PAGE_SIZE }),
        placeholderData: keepPreviousData,
        refetchInterval: 30_000,
    })

    const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
    const refreshing = isFetching && !isPending

    return (
        <div className="pg">
            <header className="pg-head">
                <div className="pg-eyebrow">
                    <span className="pg-mini-eq" aria-hidden="true"><i /><i /><i /><i /></span>
                    Track 02 · Jobs
                </div>
                <h1 className="pg-title">Every <em>Song</em> in progress</h1>
                <p className="pg-sub">One row per song in generation - the first song and every revision</p>
            </header>

            <div className="jb-toolbar">
                <label className="jb-search">
                    <SearchIcon />
                    <span className="jb-sr">Tìm job</span>
                    <input
                        type="search"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Tìm theo số đơn, tên khách, tên bài…"
                        maxLength={100}
                    />
                </label>
                <StatusDropdown
                    value={status}
                    counts={data?.counts}
                    onChange={(v) => update({ status: v, page: 1 })}
                />
            </div>

            <section className={`jb-card${refreshing ? ' is-refreshing' : ''}`} aria-busy={isFetching}>
                <span className="jb-progress" aria-hidden="true" />
                <div className="jb-scroll">
                    <table className="jb-table">
                        <thead>
                            <tr>
                                <th>Order</th>
                                <th>Song · customer</th>
                                <th>Package</th>
                                <th>Status</th>
                                <th>Due</th>
                                <th>Updated</th>
                                <th><span className="jb-sr">Mở</span></th>
                            </tr>
                        </thead>
                        <tbody>
                            {isPending ? (
                                <JobRowsSkeleton />
                            ) : isError ? (
                                <tr>
                                    <td colSpan={7} className="jb-empty">
                                        <div className="jb-empty-title">Không tải được danh sách.</div>
                                        <p>Kiểm tra backend ở cổng 8002 rồi thử lại.</p>
                                        <button type="button" className="jb-btn" onClick={() => refetch()}>Thử lại</button>
                                    </td>
                                </tr>
                            ) : data.items.length === 0 ? (
                                <tr>
                                    <td colSpan={7} className="jb-empty">
                                        <div className="jb-empty-title">Không có bài nào ở đây.</div>
                                        <p>{q ? `Không có job nào khớp "${q}".` : 'Chọn trạng thái khác để xem các job còn lại.'}</p>
                                    </td>
                                </tr>
                            ) : (
                                data.items.map((job) => <JobRow key={job.id} job={job} />)
                            )}
                        </tbody>
                    </table>
                </div>
            </section>

            <footer className="jb-foot">
                <span className="jb-mono">
                    {data ? `Showing ${data.items.length} of ${data.total}` : 'Loading…'} · Side A
                </span>
                <div className="jb-pager">
                    <button type="button" className="jb-btn" disabled={page <= 1} onClick={() => update({ page: page - 1 })}>
                        Trước
                    </button>
                    <span className="jb-mono">{page} / {totalPages}</span>
                    <button
                        type="button"
                        className="jb-btn"
                        disabled={!data || page >= totalPages}
                        onClick={() => update({ page: page + 1 })}
                    >
                        Sau
                    </button>
                </div>
            </footer>
        </div>
    )
}

function JobRow({ job }: { job: Job }) {
    const s = STATUS[job.status]
    const closed = job.status === 'done' || job.status === 'cancelled'
    const note = job.status === 'failed' ? job.error_step ?? job.error_message ?? 'Lỗi' : job.site_name

    return (
        <tr>
            <td>
                <div className="jb-mono jb-order">{job.order_number}</div>
                <div className="jb-muted">{job.revision_no === 0 ? 'Initial' : `Revision #${job.revision_no}`}</div>
            </td>
            <td className="jb-song">
                <div className={`jb-title${job.title ? '' : ' is-empty'}`}>{job.title ?? 'Chưa có tên bài'}</div>
                <div className="jb-sub">{job.customer_name ?? job.customer_email ?? '—'}</div>
            </td>
            <td>
                <span className={`jb-pkg ${job.delivery_option === '1_day' ? 'is-fast' : ''}`}>
                    {job.delivery_option === '1_day' ? '1-day' : '3-day'}
                </span>
            </td>
            <td>
                <span className={`jb-pill is-${s.kind}`}>
                    {s.kind === 'need' && <span className="jb-dot" />}
                    {(s.kind === 'run' || s.kind === 'wait') && <span className={`jb-spin${s.kind === 'wait' ? ' is-slow' : ''}`} />}
                    {s.kind === 'done' && <CheckIcon />}
                    {s.kind === 'fail' && <AlertIcon />}
                    {s.label}
                </span>
                <div className="jb-muted" title={job.error_message ?? undefined}>{note}</div>
            </td>
            <td>
                <div className={`jb-due${job.is_overdue ? ' is-overdue' : ''}`}>
                    {job.is_overdue && <ClockIcon />}
                    {closed ? '—' : dueLabel(job.due_at)}
                </div>
                <div className="jb-muted">{formatDate(job.due_at)}</div>
            </td>
            <td className="jb-sub">{ago(job.updated_at)}</td>
            <td>
                <Link className="jb-open" to={`/jobs/${job.id}`}>
                    Mở <ArrowIcon />
                </Link>
            </td>
        </tr>
    )
}

function JobRowsSkeleton() {
    return (
        <>
            {Array.from({ length: 8 }, (_, i) => (
                <tr key={i} className="jb-sk-row" aria-hidden="true">
                    <td>
                        <Skeleton width={84} height={12} radius={4} />
                        <Skeleton width={48} height={10} radius={4} style={{ marginTop: 8 }} />
                    </td>
                    <td className="jb-song">
                        <Skeleton width={i % 2 ? '62%' : '78%'} height={18} radius={6} />
                        <Skeleton width="44%" height={11} radius={4} style={{ marginTop: 8 }} />
                    </td>
                    <td><Skeleton width={56} height={24} radius={999} /></td>
                    <td>
                        <Skeleton width={i % 3 ? 120 : 150} height={28} radius={999} />
                        <Skeleton width={80} height={10} radius={4} style={{ marginTop: 8 }} />
                    </td>
                    <td>
                        <Skeleton width={70} height={13} radius={4} />
                        <Skeleton width={90} height={10} radius={4} style={{ marginTop: 8 }} />
                    </td>
                    <td><Skeleton width={56} height={12} radius={4} /></td>
                    <td><Skeleton width={64} height={36} radius={999} /></td>
                </tr>
            ))}
            <tr className="jb-sr"><td role="status">Đang tải danh sách job…</td></tr>
        </>
    )
}

function StatusDropdown({
    value,
    counts,
    onChange,
}: {
    value: StatusGroup
    counts?: Record<StatusGroup, number>
    onChange: (v: StatusGroup) => void
}) {
    const [open, setOpen] = useState(false)
    const ref = useRef<HTMLDivElement>(null)
    const current = GROUPS.find((g) => g.key === value)!

    useEffect(() => {
        if (!open) return
        const onDown = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
        }
        const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
        document.addEventListener('mousedown', onDown)
        document.addEventListener('keydown', onKey)
        return () => {
            document.removeEventListener('mousedown', onDown)
            document.removeEventListener('keydown', onKey)
        }
    }, [open])

    const pick = (v: StatusGroup) => {
        onChange(v)
        setOpen(false)
    }

    return (
        <div className="jb-dd" ref={ref}>
            <button
                type="button"
                className="jb-dd-btn"
                aria-haspopup="listbox"
                aria-expanded={open}
                onClick={() => setOpen((v) => !v)}
            >
                <span className="jb-mono jb-dd-label">Status</span>
                <div className="jb-dd-val">
                    <span className="jb-dd-value">{current.label} ({counts ? counts[value] : '…'})</span>
                    <ChevronIcon up={open} />
                </div>
            </button>
            {open && (
                <div className="jb-dd-menu" role="listbox" aria-label="Lọc theo trạng thái">
                    {GROUPS.map((g) => (
                        <button
                            key={g.key}
                            type="button"
                            role="option"
                            aria-selected={g.key === value}
                            className={`jb-dd-opt${g.key === value ? ' is-on' : ''}`}
                            onClick={() => pick(g.key)}
                        >
                            <span className="jb-dd-check">{g.key === value && <CheckIcon />}</span>
                            <span className="jb-dd-name">{g.label}</span>
                            <b>{counts ? counts[g.key] : '…'}</b>
                        </button>
                    ))}
                </div>
            )}
        </div>
    )
}

function span(ms: number) {
    const m = Math.round(Math.abs(ms) / 60_000)
    if (m < 60) return `${m}m`
    const h = Math.floor(m / 60)
    if (h < 24) return m % 60 && h < 6 ? `${h}h ${m % 60}m` : `${h}h`
    const d = Math.floor(h / 24)
    return h % 24 ? `${d}d ${h % 24}h` : `${d}d`
}

function dueLabel(iso: string) {
    const diff = new Date(iso).getTime() - Date.now()
    return diff < 0 ? `Overdue ${span(diff)}` : `in ${span(diff)}`
}

function ago(iso: string) {
    const diff = Date.now() - new Date(iso).getTime()
    return diff < 60_000 ? 'just now' : `${span(diff)} ago`
}

const dateFmt = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
function formatDate(iso: string) {
    return dateFmt.format(new Date(iso))
}

const ic = {
    viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
    strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true,
}

function SearchIcon() {
    return <svg {...ic} width={18} height={18} strokeWidth={1.9} className="jb-search-icon"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></svg>
}
function ChevronIcon({ up }: { up: boolean }) {
    return <svg {...ic} width={16} height={16} strokeWidth={2} className={`jb-chev${up ? ' is-up' : ''}`}><path d="M6 9l6 6 6-6" /></svg>
}
function CheckIcon() {
    return <svg {...ic} width={13} height={13} strokeWidth={2.6}><path d="M5 12l5 5L20 7" /></svg>
}
function AlertIcon() {
    return <svg {...ic} width={13} height={13} strokeWidth={2.4}><path d="M12 9v4M12 17h.01" /><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /></svg>
}
function ClockIcon() {
    return <svg {...ic} width={14} height={14} strokeWidth={2.4}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>
}
function ArrowIcon() {
    return <svg {...ic} width={14} height={14} strokeWidth={2}><path d="M5 12h14M13 6l6 6-6 6" /></svg>
}