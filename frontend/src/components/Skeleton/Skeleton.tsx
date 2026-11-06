import type { CSSProperties } from 'react'
import './Skeleton.css'

type SkeletonProps = {
    width?: number | string
    height?: number | string
    radius?: number | string
    circle?: boolean
    style?: CSSProperties
}

export function Skeleton({ width = '100%', height = 14, radius = 8, circle, style }: SkeletonProps) {
    return (
        <span
            className="sk"
            aria-hidden="true"
            style={{ width, height: circle ? width : height, borderRadius: circle ? '50%' : radius, ...style }}
        />
    )
}

export function SkeletonText({ lines = 3, lastWidth = '60%' }: { lines?: number; lastWidth?: string }) {
    return (
        <span className="sk-stack" aria-hidden="true">
            {Array.from({ length: lines }, (_, i) => (
                <Skeleton key={i} width={i === lines - 1 ? lastWidth : '100%'} />
            ))}
        </span>
    )
}

export function PageSkeleton({ variant = 'dashboard', label = 'Đang tải trang' }: { variant?: 'dashboard' | 'table'; label?: string }) {
    return (
        <div className="sk-page" role="status" aria-label={label}>
            <div className="sk-head">
                <Skeleton width={150} height={11} radius={4} />
                <Skeleton width="min(380px, 80%)" height={40} radius={12} />
                <Skeleton width="min(300px, 60%)" height={14} />
            </div>

            {variant === 'dashboard' ? (
                <>
                    <div className="sk-grid">
                        {Array.from({ length: 4 }, (_, i) => (
                            <div key={i} className="sk-card">
                                <Skeleton width={84} height={22} radius={999} />
                                <Skeleton width={70} height={38} radius={10} />
                                <Skeleton width="70%" height={12} />
                            </div>
                        ))}
                    </div>
                    <div className="sk-split">
                        <div className="sk-card sk-tall">
                            <Skeleton width={180} height={22} radius={8} />
                            {Array.from({ length: 4 }, (_, i) => (
                                <div key={i} className="sk-row">
                                    <Skeleton circle width={40} />
                                    <div className="sk-col">
                                        <Skeleton width="65%" height={14} />
                                        <Skeleton width="40%" height={11} />
                                    </div>
                                </div>
                            ))}
                        </div>
                        <div className="sk-card sk-tall">
                            <Skeleton width={150} height={22} radius={8} />
                            <SkeletonText lines={6} lastWidth="45%" />
                        </div>
                    </div>
                </>
            ) : (
                <div className="sk-card">
                    <div className="sk-filters">
                        {Array.from({ length: 5 }, (_, i) => <Skeleton key={i} width={i === 0 ? 220 : 110} height={40} radius={999} />)}
                    </div>
                    {Array.from({ length: 8 }, (_, i) => (
                        <div key={i} className="sk-table-row">
                            <Skeleton height={12} />
                            <div className="sk-col">
                                <Skeleton width="70%" height={14} />
                                <Skeleton width="40%" height={11} />
                            </div>
                            <Skeleton height={24} radius={999} />
                            <Skeleton height={12} />
                            <Skeleton height={34} radius={999} />
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}