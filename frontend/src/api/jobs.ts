import { api } from './client'

export type StatusGroup = 'all' | 'review' | 'pick' | 'progress' | 'ready' | 'done' | 'failed' | 'overdue'
export type JobSort = 'due' | 'updated' | 'created'

export type JobStatus =
    | 'queued'
    | 'generating_lyrics'
    | 'lyrics_ready'
    | 'lyrics_approved'
    | 'generating_music'
    | 'uploading'
    | 'music_ready'
    | 'ready'
    | 'done'
    | 'failed'
    | 'cancelled'

export type Job = {
    id: number
    order_id: number
    order_number: string
    wp_order_id: number
    site_slug: string
    site_name: string
    customer_name: string | null
    customer_email: string | null
    package_name: string | null
    delivery_option: '1_day' | '3_day'
    job_type: 'initial' | 'revision_lyrics' | 'revision_music'
    revision_no: number
    status: JobStatus
    status_group: StatusGroup
    title: string | null
    priority: number
    due_at: string
    is_overdue: boolean
    error_step: string | null
    error_message: string | null
    created_at: string
    updated_at: string
}

export type JobsResponse = {
    items: Job[]
    total: number
    page: number
    page_size: number
    counts: Record<StatusGroup, number>
}

export type JobsParams = {
    status?: StatusGroup
    site?: string
    q?: string
    sort?: JobSort
    page?: number
    page_size?: number
}

export async function fetchJobs(params: JobsParams): Promise<JobsResponse> {
    const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== ''))
    const { data } = await api.get<JobsResponse>('/jobs', { params: clean })
    return data
}