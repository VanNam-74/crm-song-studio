import { createContext, useContext, useEffect, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { api, setUnauthorizedHandler } from '../api/client'

export type Role = 'admin' | 'operator' | 'viewer'
export type User = { id: number; email: string; full_name: string | null; role: Role }

type AuthValue = {
    user: User | null
    isLoading: boolean
    login: (email: string, password: string, otp?: string) => Promise<void>
    logout: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

async function fetchMe(): Promise<User | null> {
    try {
        const { data } = await api.get<User>('/auth/me')
        return data && typeof data === 'object' && 'id' in data ? data : null
    } catch (e) {
        if (axios.isAxiosError(e) && [401, 404].includes(e.response?.status ?? 0)) return null
        throw e
    }
}

export function AuthProvider({ children }: { children: ReactNode }) {
    const qc = useQueryClient()
    const { data, isLoading } = useQuery({ queryKey: ['me'], queryFn: fetchMe, retry: false, staleTime: 5 * 60_000 })

    useEffect(() => {
        setUnauthorizedHandler(() => qc.setQueryData(['me'], null))
    }, [qc])

    const login = async (email: string, password: string, otp?: string) => {
        const { data } = await api.post<User>('/auth/login', { email, password, otp })
        qc.setQueryData(['me'], data)
    }

    const logout = async () => {
        await api.post('/auth/logout').catch(() => { })
        qc.setQueryData(['me'], null)
        qc.removeQueries({ predicate: (q) => q.queryKey[0] !== 'me' })
    }

    return (
        <AuthContext.Provider value={{ user: data ?? null, isLoading, login, logout }}>
            {children}
        </AuthContext.Provider>
    )
}

export function useAuth() {
    const ctx = useContext(AuthContext)
    if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
    return ctx
}