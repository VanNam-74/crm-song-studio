import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import './ConfirmDialog.css'

type ConfirmDialogProps = {
    open: boolean
    title: string
    description?: ReactNode
    eyebrow?: string
    confirmLabel?: string
    cancelLabel?: string
    busyLabel?: string
    onConfirm: () => Promise<void> | void
    onClose: () => void
}

export function ConfirmDialog({
    open,
    title,
    description,
    eyebrow = 'Side A · Pause',
    confirmLabel = 'Xác nhận',
    cancelLabel = 'Huỷ',
    busyLabel = 'Đang xử lý…',
    onConfirm,
    onClose,
}: ConfirmDialogProps) {
    const ref = useRef<HTMLDialogElement>(null)
    const [busy, setBusy] = useState(false)
    const titleId = useId()
    const descId = useId()

    useEffect(() => {
        const dialog = ref.current
        if (!dialog) return
        if (open && !dialog.open) dialog.showModal()
        if (!open && dialog.open) dialog.close()
    }, [open])

    useEffect(() => {
        if (!open) setBusy(false)
    }, [open])

    const handleConfirm = async () => {
        setBusy(true)
        try {
            await onConfirm()
        } finally {
            setBusy(false)
        }
    }

    return (
        <dialog
            ref={ref}
            className={`cd${busy ? ' is-busy' : ''}`}
            aria-labelledby={titleId}
            aria-describedby={description ? descId : undefined}
            onCancel={(e) => {
                e.preventDefault()
                if (!busy) onClose()
            }}
            onClick={(e) => {
                if (e.target === ref.current && !busy) onClose()
            }}
        >
            <div className="cd-card">
                <svg className="cd-disc" width="64" height="64" viewBox="0 0 64 64" aria-hidden="true">
                    <circle cx="32" cy="32" r="31" fill="#141414" />
                    <circle cx="32" cy="32" r="25" fill="none" stroke="rgba(255,255,255,.08)" />
                    <circle cx="32" cy="32" r="19" fill="none" stroke="rgba(255,255,255,.06)" />
                    <circle cx="32" cy="32" r="12" fill="#F2F2EF" />
                    <rect x="27.5" y="26.5" width="3.2" height="11" rx="1" fill="#141414" />
                    <rect x="33.3" y="26.5" width="3.2" height="11" rx="1" fill="#141414" />
                </svg>

                <div className="cd-eyebrow">{eyebrow}</div>
                <h2 id={titleId} className="cd-title">{title}</h2>
                {description && <p id={descId} className="cd-text">{description}</p>}

                <div className="cd-actions">
                    <button type="button" className="cd-btn cd-btn-secondary" onClick={onClose} disabled={busy} autoFocus>
                        {cancelLabel}
                    </button>
                    <button type="button" className="cd-btn cd-btn-primary" onClick={handleConfirm} disabled={busy} aria-busy={busy}>
                        {busy ? (
                            <>
                                <span className="cd-eq" aria-hidden="true"><i /><i /><i /><i /></span>
                                {busyLabel}
                            </>
                        ) : (
                            confirmLabel
                        )}
                    </button>
                </div>
            </div>
        </dialog>
    )
}

export default ConfirmDialog