import axios from 'axios'

export const api = axios.create({ baseURL: '/api', withCredentials: true })

let onUnauthorized: (() => void) | null = null
export const setUnauthorizedHandler = (fn: () => void) => { onUnauthorized = fn }

api.interceptors.response.use(
    (res) => res,
    (err) => {
        const url: string = err.config?.url ?? ''
        if (err.response?.status === 401 && !url.startsWith('/auth/')) onUnauthorized?.()
        return Promise.reject(err)
    },
)