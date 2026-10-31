import type { ReactNode } from 'react'

interface Props {
  kind: 'loading' | 'empty' | 'error'
  title: string
  children?: ReactNode
  onRetry?: () => void
}

export function StatusMessage({ kind, title, children, onRetry }: Props) {
  return (
    <div className={`status status--${kind}`} role={kind === 'error' ? 'alert' : 'status'} aria-live="polite">
      {kind === 'loading' && <span className="spinner" aria-hidden="true" />}
      <div>
        <p className="status__title">{title}</p>
        {children && <div className="status__body">{children}</div>}
        {onRetry && (
          <button type="button" className="button button--secondary" onClick={onRetry}>
            Try again
          </button>
        )}
      </div>
    </div>
  )
}
