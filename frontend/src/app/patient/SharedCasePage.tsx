import { api } from '../../lib/api';
import { Link } from '../../lib/router';
import { useAsync } from '../../lib/useAsync';
import { carrierLabel, carrierTone, inheritanceLabel, scopeDetail, scopeLabel } from '../labels';
import { Badge, Banner, ErrorNote, Loading, PageHeader, Panel } from '../ui';

export function SharedCasePage({ caseId }: { caseId: number }) {
  const shared = useAsync(() => api.getSharedCase(caseId), [caseId]);

  return (
    <>
      <Link to="/app/sharing" className="back-link">← Sharing</Link>
      {shared.status === 'loading' && <Loading label="Loading shared record" />}
      {shared.status === 'error' &&
        (shared.error.code === 'CONSENT_REQUIRED' || shared.error.code === 'NOT_FOUND' ? (
          <Banner tone="amber" title={shared.error.code === 'CONSENT_REQUIRED' ? 'Access is not active' : 'Record not available'}>
            <p>{shared.error.message}</p>
            <p className="muted small">
              Access to a partner’s record depends on their active consent. They may not have confirmed it yet, or may
              have revoked it.
            </p>
          </Banner>
        ) : (
          <ErrorNote error={shared.error} onRetry={shared.reload} />
        ))}
      {shared.status === 'success' && (
        <>
          <PageHeader eyebrow={`Shared by ${shared.data.owner_display_name}`} title={shared.data.synthetic_case_code}>
            <Badge tone="teal">{scopeLabel(shared.data.granted_scope)}</Badge> {scopeDetail(shared.data.granted_scope)}
          </PageHeader>
          <Panel title="Shared findings">
            <ul className="finding-list">
              {shared.data.findings.map((f) => (
                <li key={f.condition_code} className="finding">
                  <div className="finding-head">
                    <div>
                      <h3 className="finding-title">{f.condition_name}</h3>
                      <p className="muted small">
                        {f.condition_code} · {inheritanceLabel(f.inheritance_mode)}
                      </p>
                    </div>
                    <Badge tone={carrierTone(f.carrier_state)}>{carrierLabel(f.carrier_state)}</Badge>
                  </div>
                  {f.summary_text ? (
                    <p className="finding-summary">{f.summary_text}</p>
                  ) : (
                    <p className="muted small">Summary not included in the shared scope.</p>
                  )}
                </li>
              ))}
            </ul>
          </Panel>
          <p className="muted small">{shared.data.privacy_notice}</p>
        </>
      )}
    </>
  );
}
