import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { useAuth } from '../auth/AuthProvider'
import {
    fetchJob, jobActions, type Clip, type JobAction, type JobDetail as Job, type LyricsInput,
} from '../api/jobDetail'
import type { JobStatus } from '../api/jobs'
import { ConfirmDialog } from '../components/ConfirmDialog/ConfirmDialog'
import { Skeleton } from '../components/Skeleton/Skeleton'
import { ago, copyText, dueLabel, formatBytes, formatDate, formatDuration } from '../lib/format'
import '../styles/JobDetail.css'

const RUNNING: JobStatus[] = ['queued', 'generating_lyrics', 'lyrics_approved', 'generating_music', 'uploading']

const STATUS: Record<JobStatus, { label: string; kind: 'need' | 'run' | 'done' | 'fail' }> = {
    queued: { label: 'Queued', kind: 'run' },
    generating_lyrics: { label: 'Writing lyrics', kind: 'run' },
    lyrics_ready: { label: 'Lyric review', kind: 'need' },
    lyrics_approved: { label: 'Lyrics approved', kind: 'run' },
    generating_music: { label: 'Generating music', kind: 'run' },
    uploading: { label: 'Uploading to R2', kind: 'run' },
    music_ready: { label: 'Pick a take', kind: 'need' },
    ready: { label: 'Ready · copy to CRM', kind: 'need' },
    done: { label: 'Done', kind: 'done' },
    failed: { label: 'Failed', kind: 'fail' },
    cancelled: { label: 'Cancelled', kind: 'done' },
}

const STEPS = ['Order received', 'Write lyrics', 'Review lyrics', 'Make music', 'Pick a take', 'Copy to CRM']

const STEP_INDEX: Record<JobStatus, number> = {
    queued: 1, generating_lyrics: 1, lyrics_ready: 2, lyrics_approved: 3, generating_music: 3,
    uploading: 3, music_ready: 4, ready: 5, done: 6, failed: -1, cancelled: -1,
}

type Run = <T>(key: string, fn: () => Promise<Job>, after?: () => T) => void

export default function JobDetail() {
    const { id } = useParams()
    const jobId = Number(id)
    const qc = useQueryClient()
    const { user } = useAuth()
    const canOperate = user?.role === 'admin' || user?.role === 'operator'

    const { data: job, isPending, isError, error, refetch } = useQuery({
        queryKey: ['job', jobId],
        queryFn: () => fetchJob(jobId),
        enabled: Number.isFinite(jobId),
        refetchInterval: (q) => (q.state.data && RUNNING.includes(q.state.data.status) ? 4000 : false),
    })

    const [busy, setBusy] = useState<string | null>(null)
    const [notice, setNotice] = useState<string | null>(null)
    const [confirmCancel, setConfirmCancel] = useState(false)

    const mutation = useMutation({
        mutationFn: async ({ fn }: { key: string; fn: () => Promise<Job> }) => fn(),
        onMutate: ({ key }) => {
            setBusy(key)
            setNotice(null)
        },
        onSuccess: (data) => {
            qc.setQueryData(['job', jobId], data)
            qc.invalidateQueries({ queryKey: ['jobs'] })
        },
        onError: (err) => {
            setNotice(errorText(err))
            refetch()
        },
        onSettled: () => setBusy(null),
    })

    const run: Run = (key, fn, after) =>
        mutation.mutate({ key, fn }, { onSuccess: () => after?.() })

    if (isPending) return <JobDetailSkeleton />

    if (isError || !job) {
        const notFound = isAxiosError(error) && error.response?.status === 404
        return (
            <div className="jd">
                <BackLink />
                <section className="jd-panel jd-empty">
                    <h1 className="jd-h2">{notFound ? 'Job not found.' : 'Could not load this job.'}</h1>
                    <p className="jd-muted">{notFound ? 'It may have been removed, or the link is wrong.' : errorText(error)}</p>
                    {!notFound && <button type="button" className="jd-btn is-light" onClick={() => refetch()}>Try again</button>}
                </section>
            </div>
        )
    }

    const can = (a: JobAction) => canOperate && job.actions.includes(a)
    const s = STATUS[job.status]
    const story = job.order.story as Record<string, unknown>
    const recipient = str(story.tnm_recipient_name)
    const occasion = str(story.tnm_occasion)
    const latestDraft = job.drafts[job.drafts.length - 1]
    const title = job.final_title || latestDraft?.title || 'Untitled song'
    const closed = job.status === 'done' || job.status === 'cancelled'

    return (
        <div className="jd">
            <BackLink />

            <header className="jd-head">
                <div className="jd-head-main">
                    <Disc spinning={!closed} />
                    <div className="jd-head-text">
                        <div className="jd-eyebrow">
                            {job.order.order_number} · Job #{job.id} · {job.revision_no === 0 ? 'Initial' : `Revision #${job.revision_no}`} · {job.site.name}
                        </div>
                        <h1 className="jd-title">{title}</h1>
                        <div className="jd-sub">
                            <span>
                                {job.order.customer_name ?? job.order.customer_email ?? 'Customer'}
                                {recipient && <> for <b>{recipient}</b></>}
                                {occasion && <> · {occasion}</>}
                            </span>
                            <span className={`jd-pkg${job.order.delivery_option === '1_day' ? ' is-fast' : ''}`}>
                                {job.order.delivery_option === '1_day' ? '1-day' : '3-day'}
                            </span>
                        </div>
                    </div>
                </div>
                <div className="jd-head-side">
                    <span className={`jd-pill is-${s.kind}`}>
                        {s.kind === 'need' && <span className="jd-dot" />}
                        {s.kind === 'run' && <span className="jd-spin" />}
                        {s.kind === 'done' && <CheckIcon />}
                        {s.kind === 'fail' && <AlertIcon />}
                        {s.label}
                    </span>
                    <div className={`jd-due${job.is_overdue ? ' is-overdue' : ''}`}>
                        <ClockIcon />
                        {closed ? `Due ${formatDate(job.due_at)}` : `${dueLabel(job.due_at)} · ${formatDate(job.due_at)}`}
                    </div>
                </div>
            </header>

            <Stepper status={job.status} errorStep={job.error_step} />

            {notice && (
                <div className="jd-notice" role="alert">
                    <AlertIcon />
                    <span>{notice}</span>
                    <button type="button" aria-label="Dismiss" onClick={() => setNotice(null)}>×</button>
                </div>
            )}

            {job.customer_feedback && (
                <section className="jd-panel jd-feedback">
                    <div className="jd-eyebrow">Customer feedback · revision #{job.revision_no}</div>
                    <p>{job.customer_feedback}</p>
                </section>
            )}

            <div className="jd-grid">
                <div className="jd-col">
                    {(job.status === 'queued' || job.status === 'generating_lyrics') && (
                        <WaitingPanel
                            eyebrow="Side A · Lyrics"
                            title="Writing the lyrics…"
                            text="OpenAI is drafting the song from the customer's story. This page refreshes on its own."
                        />
                    )}

                    {job.status === 'lyrics_ready' && (
                        <LyricsEditor key={`${job.id}-${job.updated_at}`} job={job} can={can} busy={busy} run={run} />
                    )}

                    {(job.status === 'lyrics_approved' || job.status === 'generating_music' || job.status === 'uploading') && (
                        <>
                            <WaitingPanel
                                eyebrow="Side A · Studio"
                                title={job.status === 'uploading' ? 'Uploading takes to R2…' : 'Recording the takes…'}
                                text="Suno is generating two takes from the approved lyrics. This page refreshes on its own."
                            />
                            <LyricsReadOnly job={job} />
                        </>
                    )}

                    {job.status === 'music_ready' && <TakePicker job={job} can={can} busy={busy} run={run} />}

                    {(job.status === 'ready' || job.status === 'done') && (
                        <Handoff job={job} can={can} busy={busy} run={run} />
                    )}

                    {job.status === 'failed' && <FailedPanel job={job} can={can} busy={busy} run={run} />}

                    {job.status === 'cancelled' && (
                        <section className="jd-panel">
                            <div className="jd-eyebrow">Side A · Stopped</div>
                            <h2 className="jd-h2">This job was cancelled.</h2>
                            <p className="jd-muted">Nothing else will run for it. The order history stays on the right.</p>
                        </section>
                    )}

                    {can('cancel') && (
                        <div className="jd-cancel-row">
                            <button type="button" className="jd-link-btn" onClick={() => setConfirmCancel(true)}>Cancel this job</button>
                        </div>
                    )}
                </div>

                <aside className="jd-col jd-aside">
                    <OrderCard job={job} />
                    <Timeline job={job} />
                </aside>
            </div>

            <ConfirmDialog
                open={confirmCancel}
                eyebrow="Side A · Stop"
                title="Cancel this job?"
                description="Workers will stop picking it up. You can't resume a cancelled job; a new revision would be needed."
                cancelLabel="Keep job"
                confirmLabel="Cancel job"
                busyLabel="Stopping…"
                onConfirm={async () => {
                    await mutation.mutateAsync({ key: 'cancel', fn: () => jobActions.cancel(job.id) }).catch(() => { })
                    setConfirmCancel(false)
                }}
                onClose={() => setConfirmCancel(false)}
            />
        </div>
    )
}

/* ------------------------------------------------------------------ */
/* Lyrics                                                              */
/* ------------------------------------------------------------------ */

function LyricsEditor({ job, can, busy, run }: PanelProps) {
    const latest = job.drafts[job.drafts.length - 1]
    const initial: LyricsInput = {
        title: job.final_title ?? latest?.title ?? '',
        style: job.final_style ?? latest?.style ?? '',
        lyrics: job.final_lyrics ?? latest?.lyrics ?? '',
    }
    const [form, setForm] = useState<LyricsInput>(initial)
    const [source, setSource] = useState<number | 'current'>('current')
    const [note, setNote] = useState('')

    const dirty = form.title !== initial.title || (form.style ?? '') !== (initial.style ?? '') || form.lyrics !== initial.lyrics
    const valid = form.title.trim() !== '' && form.lyrics.trim() !== ''
    const words = form.lyrics.trim() ? form.lyrics.trim().split(/\s+/).length : 0
    const editable = can('save_lyrics')

    const loadDraft = (no: number | 'current') => {
        setSource(no)
        if (no === 'current') return setForm(initial)
        const d = job.drafts.find((x) => x.no === no)
        if (d) setForm({ title: d.title ?? '', style: d.style ?? '', lyrics: d.lyrics ?? '' })
    }

    const payload = (): LyricsInput => ({ title: form.title.trim(), style: form.style?.trim() || null, lyrics: form.lyrics })

    return (
        <section className="jd-panel">
            <div className="jd-panel-head">
                <div>
                    <div className="jd-eyebrow">Side A · Lyrics</div>
                    <h2 className="jd-h2">Review the lyrics</h2>
                </div>
                {job.drafts.length > 0 && (
                    <div className="jd-tabs" role="tablist" aria-label="Lyric drafts">
                        <button type="button" role="tab" aria-selected={source === 'current'} className={source === 'current' ? 'is-on' : ''} onClick={() => loadDraft('current')}>
                            Current{job.lyrics_status === 'edited' ? ' · edited' : ''}
                        </button>
                        {job.drafts.map((d) => (
                            <button key={d.id} type="button" role="tab" aria-selected={source === d.no} className={source === d.no ? 'is-on' : ''} onClick={() => loadDraft(d.no)}>
                                Draft {d.no}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            <div className="jd-fields">
                <label className="jd-field">
                    <span className="jd-label">Song title</span>
                    <input className="jd-input is-title" value={form.title} disabled={!editable} maxLength={255}
                        onChange={(e) => setForm({ ...form, title: e.target.value })} />
                </label>
                <label className="jd-field">
                    <span className="jd-label">Style prompt for Suno</span>
                    <input className="jd-input" value={form.style ?? ''} disabled={!editable} maxLength={1000}
                        onChange={(e) => setForm({ ...form, style: e.target.value })} placeholder="e.g. warm acoustic ballad, male vocal" />
                </label>
            </div>

            <label className="jd-field">
                <span className="jd-label-row">
                    <span className="jd-label">Lyrics</span>
                    <span className="jd-hint">
                        {words} words{source !== 'current' && ` · loaded from Draft ${source}`}{dirty && ' · unsaved changes'}
                    </span>
                </span>
                <textarea className="jd-input jd-lyrics" value={form.lyrics} disabled={!editable}
                    onChange={(e) => setForm({ ...form, lyrics: e.target.value })} spellCheck />
            </label>

            {can('regenerate_lyrics') && (
                <div className="jd-rewrite">
                    <span className="jd-label">Rewrite with a note (optional)</span>
                    <div className="jd-rewrite-row">
                        <input className="jd-input" value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)}
                            placeholder="e.g. mention the Lisbon trip, make the chorus more upbeat" />
                        <button type="button" className="jd-btn is-ghost" disabled={!!busy}
                            onClick={() => run('regenerate', () => jobActions.regenerateLyrics(job.id, note.trim()))}>
                            {busy === 'regenerate' ? <span className="jd-spin" /> : <RefreshIcon />}
                            Rewrite (Draft {job.drafts.length + 1})
                        </button>
                    </div>
                </div>
            )}

            {editable && (
                <div className="jd-actions">
                    <span className="jd-hint jd-grow">Approving sends the lyrics to Suno for two takes.</span>
                    <button type="button" className="jd-btn is-light" disabled={!dirty || !valid || !!busy}
                        onClick={() => run('save', () => jobActions.saveLyrics(job.id, payload()))}>
                        {busy === 'save' && <span className="jd-spin" />}Save changes
                    </button>
                    <button type="button" className="jd-btn is-dark" disabled={!valid || !!busy}
                        onClick={() => run('approve', () => jobActions.approveLyrics(job.id, payload()))}>
                        {busy === 'approve' ? <span className="jd-spin is-light" /> : <CheckIcon />}Approve &amp; make music
                    </button>
                </div>
            )}
        </section>
    )
}

function LyricsReadOnly({ job }: { job: Job }) {
    if (!job.final_lyrics) return null
    return (
        <section className="jd-panel">
            <div className="jd-panel-head">
                <div>
                    <div className="jd-eyebrow">Approved lyrics</div>
                    <h2 className="jd-h3">{job.final_title}</h2>
                </div>
                {job.lyrics_approved_by && (
                    <span className="jd-hint">
                        by {job.lyrics_approved_by}{job.lyrics_approved_at && ` · ${formatDate(job.lyrics_approved_at)}`}
                    </span>
                )}
            </div>
            {job.final_style && <div className="jd-chip">{job.final_style}</div>}
            <div className="jd-copybox jd-pre">{job.final_lyrics}</div>
        </section>
    )
}

/* ------------------------------------------------------------------ */
/* Takes                                                               */
/* ------------------------------------------------------------------ */

function TakePicker({ job, can, busy, run, compact }: PanelProps & { compact?: boolean }) {
    const gen = job.music[job.music.length - 1]
    const clips = gen?.clips ?? []
    const player = usePlayer()

    if (!gen) {
        return (
            <section className="jd-panel">
                <h2 className="jd-h2">No takes yet.</h2>
            </section>
        )
    }

    return (
        <section className={compact ? 'jd-takes-compact' : 'jd-panel'}>
            {!compact && (
                <div className="jd-panel-head">
                    <div>
                        <div className="jd-eyebrow">Side A · Takes</div>
                        <h2 className="jd-h2">Pick a take</h2>
                    </div>
                    <span className="jd-hint">
                        Generation {gen.no}{job.music.length > 1 ? ` of ${job.music.length}` : ''} · {gen.provider_type.replace('_', ' ')}
                    </span>
                </div>
            )}

            {clips.some((c) => !c.audio_url) && (
                <p className="jd-hint">Audio preview needs <code>R2_PUBLIC_BASE_URL</code> on the server.</p>
            )}

            <div className="jd-take-grid">
                {clips.map((clip) => (
                    <TakeCard key={clip.id} clip={clip} player={player}
                        selected={job.selected_clip_id === clip.id}
                        canSelect={can('select_clip')}
                        busy={busy === `select-${clip.id}`}
                        disabled={!!busy}
                        onSelect={() => run(`select-${clip.id}`, () => jobActions.selectClip(job.id, clip.id))} />
                ))}
            </div>

            {!compact && (
                <div className="jd-actions">
                    <span className="jd-hint jd-grow">Not happy with either? Make new takes from the same lyrics.</span>
                    {can('regenerate_music') && (
                        <button type="button" className="jd-btn is-ghost" disabled={!!busy}
                            onClick={() => run('remusic', () => jobActions.regenerateMusic(job.id))}>
                            {busy === 'remusic' ? <span className="jd-spin" /> : <RefreshIcon />}New takes
                        </button>
                    )}
                    {can('confirm_take') && (
                        <button type="button" className="jd-btn is-dark" disabled={!job.selected_clip_id || !!busy}
                            onClick={() => run('confirm', () => jobActions.confirmTake(job.id), player.stop)}>
                            {busy === 'confirm' && <span className="jd-spin is-light" />}Confirm take
                        </button>
                    )}
                </div>
            )}
        </section>
    )
}

function TakeCard({ clip, player, selected, canSelect, busy, disabled, onSelect }: {
    clip: Clip
    player: Player
    selected: boolean
    canSelect: boolean
    busy: boolean
    disabled: boolean
    onSelect: () => void
}) {
    const playing = player.current === clip.id
    const progress = playing ? player.progress : 0
    const bars = useMemo(() => waveform(clip.id), [clip.id])
    const ready = clip.status === 'complete'

    return (
        <article className={`jd-take${selected ? ' is-selected' : ''}`}>
            <div className="jd-take-head">
                <button type="button" className="jd-play" disabled={!clip.audio_url}
                    aria-label={`${playing ? 'Pause' : 'Play'} take ${clip.label}`}
                    onClick={() => clip.audio_url && player.toggle(clip.id, clip.audio_url)}>
                    {playing ? <PauseIcon /> : <PlayIcon />}
                </button>
                <div className="jd-take-text">
                    <div className="jd-take-name">Take {clip.label}</div>
                    <div className="jd-mono">
                        {formatDuration(clip.duration_sec)}{clip.file_size ? ` · ${formatBytes(clip.file_size)}` : ''}{!ready ? ` · ${clip.status}` : ''}
                    </div>
                </div>
                {playing && <span className="jd-eq" aria-hidden="true"><i /><i /><i /><i /></span>}
            </div>
            <div className="jd-wave" aria-hidden="true">
                {bars.map((h, i) => <i key={i} style={{ height: `${h}%` }} className={i / bars.length < progress ? 'is-on' : ''} />)}
            </div>
            {clip.admin_note && <p className="jd-hint">{clip.admin_note}</p>}
            {canSelect && (
                <button type="button" className={`jd-btn ${selected ? 'is-dark is-static' : 'is-light'}`}
                    disabled={disabled || !ready || selected} onClick={onSelect}>
                    {busy ? <span className="jd-spin" /> : selected && <CheckIcon />}
                    {selected ? 'Selected' : 'Choose this take'}
                </button>
            )}
        </article>
    )
}

/* ------------------------------------------------------------------ */
/* Hand-off                                                            */
/* ------------------------------------------------------------------ */

function Handoff({ job, can, busy, run }: PanelProps) {
    const [changing, setChanging] = useState(false)
    const clip = job.music.flatMap((g) => g.clips).find((c) => c.id === job.selected_clip_id)
    const link = clip?.audio_url ?? clip?.r2_key ?? ''
    const done = job.status === 'done'
    const player = usePlayer()

    return (
        <section className="jd-panel">
            <div className="jd-panel-head">
                <div>
                    <div className="jd-eyebrow">Side A · Hand-off</div>
                    <h2 className="jd-h2">{done ? 'Delivered to the CRM' : 'Copy to HIS CRM'}</h2>
                </div>
                <span className="jd-hint">{done ? 'Read only' : 'Copy each block in order'}</span>
            </div>

            {clip && (
                <div className="jd-final">
                    <button type="button" className="jd-play is-inverse" disabled={!clip.audio_url}
                        aria-label={`${player.current === clip.id ? 'Pause' : 'Play'} take ${clip.label}`}
                        onClick={() => clip.audio_url && player.toggle(clip.id, clip.audio_url)}>
                        {player.current === clip.id ? <PauseIcon /> : <PlayIcon />}
                    </button>
                    <div className="jd-grow">
                        <div className="jd-final-name">Take {clip.label} · selected</div>
                        <div className="jd-mono is-inverse">
                            {formatDuration(clip.duration_sec)} · {clip.mime_type ?? 'audio'}{clip.file_size ? ` · ${formatBytes(clip.file_size)}` : ''}
                        </div>
                    </div>
                    {can('select_clip') && !done && (
                        <button type="button" className="jd-btn is-sm is-glass" onClick={() => setChanging((v) => !v)}>
                            {changing ? 'Close' : 'Change take'}
                        </button>
                    )}
                </div>
            )}

            {changing && <TakePicker job={job} can={can} busy={busy} run={run} compact />}

            <CopyBlock label="01 · Audio link" text={link} mono
                hint={clip?.audio_url ? undefined : 'R2 key only. Set R2_PUBLIC_BASE_URL to get a public link.'} />
            <CopyBlock label="02 · Song title" text={job.final_title ?? ''} />
            <CopyBlock label="03 · Lyrics" text={job.final_lyrics ?? ''} pre />

            <div className="jd-actions">
                {done ? (
                    <>
                        <span className="jd-grow">
                            Marked done{job.done_by && <> by <b>{job.done_by}</b></>}{job.done_at && ` · ${formatDate(job.done_at)}`}
                        </span>
                        {can('reopen') && (
                            <button type="button" className="jd-btn is-ghost" disabled={!!busy} onClick={() => run('reopen', () => jobActions.reopen(job.id))}>
                                {busy === 'reopen' && <span className="jd-spin" />}Reopen job
                            </button>
                        )}
                    </>
                ) : (
                    <>
                        <span className="jd-hint jd-grow">Paste the link and lyrics into order #{job.order.order_number} in the CRM, then mark it done.</span>
                        {can('regenerate_music') && (
                            <button type="button" className="jd-btn is-ghost" disabled={!!busy} onClick={() => run('remusic', () => jobActions.regenerateMusic(job.id))}>
                                {busy === 'remusic' && <span className="jd-spin" />}New takes
                            </button>
                        )}
                        {can('mark_done') && (
                            <button type="button" className="jd-btn is-dark" disabled={!!busy} onClick={() => run('done', () => jobActions.markDone(job.id), player.stop)}>
                                {busy === 'done' ? <span className="jd-spin is-light" /> : <CheckIcon />}Copied to CRM
                            </button>
                        )}
                    </>
                )}
            </div>
        </section>
    )
}

function CopyBlock({ label, text, hint, mono, pre }: { label: string; text: string; hint?: string; mono?: boolean; pre?: boolean }) {
    const [copied, setCopied] = useState(false)
    useEffect(() => {
        if (!copied) return
        const t = setTimeout(() => setCopied(false), 1600)
        return () => clearTimeout(t)
    }, [copied])

    return (
        <div className="jd-copy">
            <div className="jd-copy-head">
                <span className="jd-eyebrow">{label}</span>
                <button type="button" className="jd-btn is-sm is-light" disabled={!text}
                    onClick={async () => setCopied(await copyText(text))}>
                    {copied && <CheckIcon />}{copied ? 'Copied' : 'Copy'}
                </button>
            </div>
            <div className={`jd-copybox${mono ? ' is-mono' : ''}${pre ? ' jd-pre' : ''}`}>{text || '—'}</div>
            {hint && <span className="jd-hint">{hint}</span>}
        </div>
    )
}

/* ------------------------------------------------------------------ */
/* Failed / waiting                                                    */
/* ------------------------------------------------------------------ */

function FailedPanel({ job, can, busy, run }: PanelProps) {
    const lyricsOk = job.lyrics_status === 'approved'
    return (
        <section className="jd-panel is-failed">
            <div className="jd-failed-head">
                <span className="jd-failed-icon"><AlertIcon /></span>
                <div>
                    <div className="jd-eyebrow">Side A · Skipped a beat</div>
                    <h2 className="jd-h2">This job stopped at {job.error_step ?? 'an unknown step'}.</h2>
                    <p className="jd-muted">
                        Retried {job.retry_count} time{job.retry_count === 1 ? '' : 's'}. Fix the cause (for example, refresh the Suno cookie in Music providers), then retry.
                    </p>
                </div>
            </div>
            {job.error_message && <pre className="jd-error">{job.error_message}</pre>}
            <dl className="jd-kv">
                <dt>Lyrics</dt>
                <dd>{lyricsOk ? 'Approved, kept when retrying' : 'Not approved yet'}</dd>
                <dt>Retry will</dt>
                <dd>{lyricsOk && job.error_step !== 'generate_lyrics' ? 'Generate music again' : 'Write the lyrics again'}</dd>
            </dl>
            <div className="jd-actions">
                <span className="jd-grow" />
                {can('regenerate_lyrics') && (
                    <button type="button" className="jd-btn is-light" disabled={!!busy} onClick={() => run('regenerate', () => jobActions.regenerateLyrics(job.id))}>
                        {busy === 'regenerate' && <span className="jd-spin" />}Rewrite lyrics
                    </button>
                )}
                {can('retry') && (
                    <button type="button" className="jd-btn is-dark" disabled={!!busy} onClick={() => run('retry', () => jobActions.retry(job.id))}>
                        {busy === 'retry' ? <span className="jd-spin is-light" /> : <RefreshIcon />}Retry this step
                    </button>
                )}
            </div>
        </section>
    )
}

function WaitingPanel({ eyebrow, title, text }: { eyebrow: string; title: string; text: string }) {
    return (
        <section className="jd-panel jd-waiting" aria-live="polite">
            <Disc spinning size={64} />
            <div>
                <div className="jd-eyebrow">{eyebrow}</div>
                <h2 className="jd-h2">{title}</h2>
                <p className="jd-muted">{text}</p>
            </div>
        </section>
    )
}

/* ------------------------------------------------------------------ */
/* Aside                                                               */
/* ------------------------------------------------------------------ */

const STORY_LABELS: Record<string, string> = {
    tnm_recipient_name: 'Recipient',
    tnm_sender_name: 'From',
    tnm_relationship: 'Relationship',
    tnm_occasion: 'Occasion',
    tnm_genre: 'Genre',
    tnm_voice: 'Voice',
    tnm_mood: 'Mood',
    tnm_must_include: 'Must include',
}

function OrderCard({ job }: { job: Job }) {
    const o = job.order
    const story = o.story as Record<string, unknown>
    const text = str(story.tnm_story)
    const extra = Object.entries(story).filter(([k, v]) => k !== 'tnm_story' && str(v))

    return (
        <section className="jd-panel is-tight">
            <div className="jd-panel-head">
                <span className="jd-eyebrow">Order</span>
                <a className="jd-ext" href={o.wp_admin_url} target="_blank" rel="noreferrer">Open in WordPress ↗</a>
            </div>
            <dl className="jd-kv">
                <dt>Customer</dt>
                <dd>{o.customer_name ?? '—'}{o.customer_email && <><br /><span className="jd-hint">{o.customer_email}</span></>}</dd>
                <dt>Package</dt>
                <dd>{o.package_name ?? (o.delivery_option === '1_day' ? '1-day' : '3-day')}</dd>
                <dt>Paid</dt>
                <dd>{formatDate(o.paid_at)}</dd>
                <dt>Due</dt>
                <dd><b>{formatDate(job.due_at)}</b></dd>
                {extra.map(([k, v]) => (
                    <Row key={k} label={STORY_LABELS[k] ?? prettify(k)}>{str(v)}</Row>
                ))}
            </dl>
            {text && (
                <div className="jd-field">
                    <span className="jd-label">Customer's story</span>
                    <p className="jd-story">{text}</p>
                </div>
            )}
        </section>
    )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
    return (
        <>
            <dt>{label}</dt>
            <dd>{children}</dd>
        </>
    )
}

function Timeline({ job }: { job: Job }) {
    const [all, setAll] = useState(false)
    const events = all ? job.events : job.events.slice(0, 8)
    return (
        <section className="jd-panel is-tight">
            <span className="jd-eyebrow">Activity</span>
            {events.length === 0 ? (
                <p className="jd-hint">No activity yet.</p>
            ) : (
                <ol className="jd-events">
                    {events.map((e) => (
                        <li key={e.id} className={`jd-event is-${e.level}`}>
                            <span className="jd-event-dot" aria-hidden="true" />
                            <div>
                                <div className="jd-event-msg">{e.message}</div>
                                <div className="jd-hint">
                                    {e.actor_name ?? e.step} · <time dateTime={e.created_at} title={formatDate(e.created_at)}>{ago(e.created_at)}</time>
                                </div>
                            </div>
                        </li>
                    ))}
                </ol>
            )}
            {job.events.length > 8 && (
                <button type="button" className="jd-link-btn" onClick={() => setAll((v) => !v)}>
                    {all ? 'Show less' : `Show all ${job.events.length}`}
                </button>
            )}
        </section>
    )
}

/* ------------------------------------------------------------------ */
/* Pieces                                                              */
/* ------------------------------------------------------------------ */

type PanelProps = { job: Job; can: (a: JobAction) => boolean; busy: string | null; run: Run }

function Stepper({ status, errorStep }: { status: JobStatus; errorStep: string | null }) {
    let current = STEP_INDEX[status]
    const failed = status === 'failed'
    if (failed) current = errorStep && /music|suno|upload/i.test(errorStep) ? 3 : 1
    if (status === 'cancelled') current = -1

    return (
        <ol className="jd-steps" aria-label="Progress">
            {STEPS.map((label, i) => {
                const done = status === 'done' || i < current
                const cur = i === current && status !== 'done'
                const cls = cur ? (failed ? 'is-error' : 'is-current') : done ? 'is-done' : ''
                return (
                    <li key={label} className={`jd-step ${cls}`} aria-current={cur ? 'step' : undefined}>
                        <span className="jd-step-n">{String(i + 1).padStart(2, '0')}</span>
                        {done && !cur && <CheckIcon />}
                        {cur && failed && <AlertIcon />}
                        <span className="jd-step-label">{label}</span>
                    </li>
                )
            })}
        </ol>
    )
}

function BackLink() {
    return (
        <Link to="/jobs" className="jd-back">
            <svg {...ic} width={16} height={16} strokeWidth={2}><path d="M19 12H5M11 18l-6-6 6-6" /></svg>
            Jobs
        </Link>
    )
}

function Disc({ spinning, size = 88 }: { spinning?: boolean; size?: number }) {
    return (
        <svg className={`jd-disc${spinning ? ' is-spinning' : ''}`} width={size} height={size} viewBox="0 0 88 88" aria-hidden="true">
            <circle cx="44" cy="44" r="43" fill="#141414" />
            <circle cx="44" cy="44" r="34" fill="none" stroke="rgba(255,255,255,.08)" />
            <circle cx="44" cy="44" r="27" fill="none" stroke="rgba(255,255,255,.07)" />
            <circle cx="44" cy="44" r="16" fill="#F2F2EF" />
            <circle cx="54" cy="44" r="1.6" fill="#141414" />
            <circle cx="44" cy="44" r="2" fill="#141414" />
        </svg>
    )
}

function JobDetailSkeleton() {
    return (
        <div className="jd" role="status" aria-label="Loading job">
            <Skeleton width={70} height={14} radius={4} />
            <div className="jd-head">
                <div className="jd-head-main">
                    <Skeleton circle width={88} />
                    <div className="jd-head-text" style={{ flex: 1 }}>
                        <Skeleton width={260} height={11} radius={4} />
                        <Skeleton width="min(420px, 80%)" height={42} radius={12} />
                        <Skeleton width={240} height={14} radius={4} />
                    </div>
                </div>
                <div className="jd-head-side">
                    <Skeleton width={130} height={30} radius={999} />
                    <Skeleton width={180} height={14} radius={4} />
                </div>
            </div>
            <Skeleton height={54} radius={999} />
            <div className="jd-grid">
                <div className="jd-col">
                    <section className="jd-panel">
                        <Skeleton width={200} height={28} radius={8} />
                        <div className="jd-fields">
                            <Skeleton height={48} radius={16} />
                            <Skeleton height={48} radius={16} />
                        </div>
                        <Skeleton height={360} radius={16} />
                        <div className="jd-actions">
                            <span className="jd-grow" />
                            <Skeleton width={130} height={46} radius={999} />
                            <Skeleton width={190} height={46} radius={999} />
                        </div>
                    </section>
                </div>
                <aside className="jd-col jd-aside">
                    <section className="jd-panel is-tight">
                        {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} width={i % 2 ? '70%' : '90%'} height={13} radius={4} />)}
                        <Skeleton height={90} radius={16} />
                    </section>
                    <section className="jd-panel is-tight">
                        {Array.from({ length: 4 }, (_, i) => (
                            <div key={i} style={{ display: 'flex', gap: 12 }}>
                                <Skeleton circle width={9} />
                                <div style={{ flex: 1, display: 'grid', gap: 6 }}>
                                    <Skeleton width="80%" height={13} radius={4} />
                                    <Skeleton width="50%" height={10} radius={4} />
                                </div>
                            </div>
                        ))}
                    </section>
                </aside>
            </div>
        </div>
    )
}

/* ------------------------------------------------------------------ */
/* Audio                                                               */
/* ------------------------------------------------------------------ */

type Player = { current: number | null; progress: number; toggle: (id: number, url: string) => void; stop: () => void }

function usePlayer(): Player {
    const audio = useRef<HTMLAudioElement | null>(null)
    const [current, setCurrent] = useState<number | null>(null)
    const [progress, setProgress] = useState(0)

    const stop = () => {
        audio.current?.pause()
        setCurrent(null)
        setProgress(0)
    }

    useEffect(() => () => audio.current?.pause(), [])

    const toggle = (id: number, url: string) => {
        if (!audio.current) {
            audio.current = new Audio()
            audio.current.addEventListener('timeupdate', () => {
                const a = audio.current!
                setProgress(a.duration ? a.currentTime / a.duration : 0)
            })
            audio.current.addEventListener('ended', () => {
                setCurrent(null)
                setProgress(0)
            })
        }
        const a = audio.current
        if (current === id) return stop()
        a.src = url
        setProgress(0)
        a.play().then(() => setCurrent(id)).catch(() => setCurrent(null))
    }

    return { current, progress, toggle, stop }
}

function waveform(seed: number) {
    return Array.from({ length: 56 }, (_, i) =>
        18 + Math.round(72 * Math.abs(Math.sin(i * 0.5 + seed) * Math.cos(i * 0.13 + seed / 3))),
    )
}

/* ------------------------------------------------------------------ */

function errorText(err: unknown) {
    if (isAxiosError(err)) {
        const detail = err.response?.data?.detail
        if (typeof detail === 'string') return detail
        if (Array.isArray(detail)) return detail.map((d) => d.msg).join(', ')
        return err.message
    }
    return 'Something went wrong.'
}

function str(v: unknown): string {
    if (v == null) return ''
    if (Array.isArray(v)) return v.filter(Boolean).join(', ')
    if (typeof v === 'object') return ''
    return String(v).trim()
}

function prettify(key: string) {
    const k = key.replace(/^tnm_/, '').replace(/_/g, ' ')
    return k.charAt(0).toUpperCase() + k.slice(1)
}

const ic = {
    viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
    strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true,
}

function CheckIcon() {
    return <svg {...ic} width={14} height={14} strokeWidth={2.6}><path d="M5 12l5 5L20 7" /></svg>
}
function AlertIcon() {
    return <svg {...ic} width={14} height={14} strokeWidth={2.4}><path d="M12 9v4M12 17h.01" /><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /></svg>
}
function ClockIcon() {
    return <svg {...ic} width={15} height={15} strokeWidth={2.2}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>
}
function RefreshIcon() {
    return <svg {...ic} width={15} height={15} strokeWidth={2}><path d="M21 12a9 9 0 1 1-3-6.7L21 8" /><path d="M21 3v5h-5" /></svg>
}
function PlayIcon() {
    return <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5.5v13a1 1 0 0 0 1.5.9l10.4-6.5a1 1 0 0 0 0-1.8L9.5 4.6A1 1 0 0 0 8 5.5z" /></svg>
}
function PauseIcon() {
    return <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></svg>
}