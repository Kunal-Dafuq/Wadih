import { api } from '../../lib/api';
import { Link } from '../../lib/router';
import { useAsync } from '../../lib/useAsync';
import { formatDate } from '../labels';
import { Badge, Empty, ErrorNote, Loading, PageHeader } from '../ui';

export function ResultsPage() {
  const cases = useAsync(() => api.listCases(), []);

  return (
    <>
      <PageHeader eyebrow="Your results" title={<>Screening <em>results.</em></>}>
        Synthetic carrier screening records linked to your account. Open one to see each condition, its explanation and
        what it could mean for a future pregnancy.
      </PageHeader>

      {cases.status === 'loading' && <Loading label="Loading your results" />}
      {cases.status === 'error' && <ErrorNote error={cases.error} onRetry={cases.reload} />}
      {cases.status === 'success' &&
        (cases.data.length === 0 ? (
          <Empty title="No screening results yet">Results appear here once a screening record is linked to your account.</Empty>
        ) : (
          <ul className="case-list">
            {cases.data.map((c) => (
              <li key={c.id}>
                <Link to={`/app/results/${c.id}`} className="case-card">
                  <div>
                    <p className="eyebrow">{c.synthetic_case_code}</p>
                    <h2 className="case-card-title">{c.screening_scope_label}</h2>
                    <p className="muted small">Added {formatDate(c.created_at)}</p>
                  </div>
                  <div className="case-card-meta">
                    <Badge tone={c.status === 'ready' ? 'teal' : 'muted'}>{c.status}</Badge>
                    <span className="muted small">
                      {c.findings_count} {c.findings_count === 1 ? 'condition' : 'conditions'}
                    </span>
                    {c.source_reviewed && <span className="muted small">Clinician reviewed</span>}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        ))}
    </>
  );
}
