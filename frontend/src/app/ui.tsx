import type { ButtonHTMLAttributes, ReactNode } from 'react';
import type { ApiError } from '../lib/api';

export function PageHeader({ eyebrow, title, children }: { eyebrow?: string; title: ReactNode; children?: ReactNode }) {
  return (
    <header className="page-head">
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h1 className="page-title">{title}</h1>
      {children && <div className="page-lede">{children}</div>}
    </header>
  );
}

export function Panel({ title, aside, children, className = '' }: { title?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`panel ${className}`}>
      {(title || aside) && (
        <div className="panel-head">
          {title && <h2 className="panel-title">{title}</h2>}
          {aside}
        </div>
      )}
      {children}
    </section>
  );
}

export function Badge({ tone = 'muted', children }: { tone?: 'amber' | 'teal' | 'warn' | 'muted' | 'danger'; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function Button({
  variant = 'primary',
  size,
  pending,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' | 'quiet' | 'danger'; size?: 'sm'; pending?: boolean }) {
  return (
    <button
      className={`btn btn-${variant}${size === 'sm' ? ' btn-sm' : ''}`}
      disabled={pending || rest.disabled}
      aria-busy={pending || undefined}
      {...rest}
    >
      {pending && <span className="spinner" aria-hidden="true" />}
      {children}
    </button>
  );
}

export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" aria-hidden="true" />
      {label}…
    </div>
  );
}

export function Banner({ tone, title, children, actions }: { tone: 'amber' | 'teal' | 'info' | 'danger'; title: ReactNode; children?: ReactNode; actions?: ReactNode }) {
  return (
    <div className={`banner banner-${tone}`} role={tone === 'danger' ? 'alert' : 'status'}>
      <div>
        <p className="banner-title">{title}</p>
        {children && <div className="banner-body">{children}</div>}
      </div>
      {actions && <div className="banner-actions">{actions}</div>}
    </div>
  );
}

const ERROR_TITLES: Record<string, string> = {
  CONSENT_REQUIRED: 'Consent required',
  FORBIDDEN: 'Not permitted',
  NOT_FOUND: 'Not found',
  VALIDATION_ERROR: 'Please check the details',
  NEEDS_CLINICIAN_REVIEW: 'Clinician review needed',
  NETWORK_ERROR: 'Service unavailable',
  UNAUTHENTICATED: 'Signed out',
};

/** Renders the backend's error envelope (code + message + request id). */
export function ErrorNote({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <Banner
      tone="danger"
      title={ERROR_TITLES[error.code] ?? 'Something went wrong'}
      actions={
        onRetry && (
          <Button variant="ghost" size="sm" onClick={onRetry}>
            Try again
          </Button>
        )
      }
    >
      <p>{error.message}</p>
      {error.requestId && <p className="request-id">Reference: {error.requestId}</p>}
    </Banner>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <p className="empty-title">{title}</p>
      {children && <div className="empty-body">{children}</div>}
    </div>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}
