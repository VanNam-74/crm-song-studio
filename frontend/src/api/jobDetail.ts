import { api } from './client'
import type { JobStatus } from './jobs'

export type JobAction =
    | 'save_lyrics'
    | 'approve_lyrics'
    | 'regenerate_lyrics'
    | 'select_clip'
    | 'confirm_take'
    | 'regenerate_music'
    | 'mark_done'
    | 'reopen'
    | 'retry'
    | 'cancel'

export type GenerationStatus = 'pending' | 'complete' | 'failed'

export type LyricDraft = {
    id: number
    no: number
    status: GenerationStatus
    model: string
    title: string | null
    style: string | null
    lyrics: string | null
    note: string | null
    input_tokens: number | null
    output_tokens: number | null
    error_message: string | null
    created_at: string
}

export type Clip = {
    id: number
    label: string
    status: GenerationStatus
    duration_sec: string | number | null
    audio_url: string | null
    r2_key: string | null
    file_size: number | null
    mime_type: string | null
    admin_note: string | null
    is_selected: boolean
}

export type MusicGeneration = {
    id: number
    no: number
    provider_type: string
    status: GenerationStatus
    poll_count: number
    error_message: string | null
    submitted_at: string
    completed_at: string | null
    clips: Clip[]
}

export type JobEvent = {
    id: number
    level: 'info' | 'warning' | 'error'
    step: string
    message: string
    actor_name: string | null
    created_at: string
}

export type JobDetail = {
    id: number
    revision_no: number
    job_type: 'initial' | 'revision_lyrics' | 'revision_music'
    parent_job_id: number | null
    customer_feedback: string | null
    status: JobStatus
    priority: number
    due_at: string
    is_overdue: boolean
    error_step: string | null
    error_message: string | null
    retry_count: number
    final_title: string | null
    final_style: string | null
    final_lyrics: string | null
    lyrics_status: 'draft' | 'edited' | 'approved' | null
    lyrics_approved_by: string | null
    lyrics_approved_at: string | null
    selected_clip_id: number | null
    done_at: string | null
    done_by: string | null
    created_at: string
    updated_at: string
    site: {
        id: number
        slug: string
        name: string
        base_url: string
        require_lyric_approval: boolean
        require_clip_selection: boolean
    }
    order: {
        id: number
        wp_order_id: number
        order_number: string
        customer_name: string | null
        customer_email: string | null
        package_name: string | null
        delivery_option: '1_day' | '3_day'
        paid_at: string
        status: 'active' | 'done' | 'cancelled'
        wp_admin_url: string
        story: Record<string, unknown>
    }
    drafts: LyricDraft[]
    music: MusicGeneration[]
    events: JobEvent[]
    actions: JobAction[]
}

export type LyricsInput = { title: string; style: string | null; lyrics: string }

export async function fetchJob(id: number): Promise<JobDetail> {
    const { data } = await api.get<JobDetail>(`/jobs/${id}`)
    return data
}

const post = async (id: number, path: string, body?: unknown) =>
    (await api.post<JobDetail>(`/jobs/${id}/${path}`, body)).data

export const jobActions = {
    saveLyrics: async (id: number, body: LyricsInput) => (await api.patch<JobDetail>(`/jobs/${id}/lyrics`, body)).data,
    approveLyrics: (id: number, body?: LyricsInput) => post(id, 'approve-lyrics', body),
    regenerateLyrics: (id: number, note?: string) => post(id, 'regenerate-lyrics', { note: note || null }),
    selectClip: (id: number, clipId: number) => post(id, 'select-clip', { clip_id: clipId }),
    confirmTake: (id: number) => post(id, 'confirm-take'),
    regenerateMusic: (id: number) => post(id, 'regenerate-music'),
    markDone: (id: number) => post(id, 'mark-done'),
    reopen: (id: number) => post(id, 'reopen'),
    retry: (id: number) => post(id, 'retry'),
    cancel: (id: number) => post(id, 'cancel'),
}