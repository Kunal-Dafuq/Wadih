import { useState } from 'react';
import { api, ApiError } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { Link } from '../../lib/router';
import { useAsync } from '../../lib/useAsync';
import type { ConsentGrant, RiskAssessment, SyntheticFinding } from '../../lib/types';
import { RiskResult } from '../components/RiskResult';
import { carrierLabel, carrierTone, effectiveConsentStatus, inheritanceLabel, triggerLabel } from '../labels';
import { Badge, Banner, Button, ErrorNote, Field, Loading, PageHeader, Panel } from '../ui';

/** Partner cases the caller can include: unexpired, granted consents *to* the caller that are bound to a case. */
function linkedPartnerCases(grants: ConsentGrant[], myId: number) {
  const byCase = new Map<number, ConsentGrant>();
  for (const g of grants) {
    if (g.grantee_user_id !== myId || effectiveConsentStatus(g) !== 'GRANTED' || g.case_id == null) continue;
    // One entry per shared record; keep the grant that lasts longest (no expiry counts as longest).
    const prev = byCase.get(g.case_id);
    const lasts = (x: ConsentGrant) => (x.expires_at ? Date.parse(x.expires_at) : Infinity);
    if (!prev || lasts(g) > lasts(prev)) byCase.set(g.case_id, g);
  }
  return [...byCase.values()];
}

function FindingAssessment({ caseId, finding, partners }: { caseId: number; finding: SyntheticFinding; partners: ConsentGrant[] }) {
  const [partnerCaseId, setPartnerCaseId] = useState<string>('');
  const [result, setResult] = useState<{ data: RiskAssessment; joint: boolean } | null>(null);
  const [notScreened, setNotScreened] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const run = async () => {
    setPending(true);
    setError(null);
    setNotScreened(null);
    const partner = partnerCaseId ? Number(partnerCaseId) : null;
    try {
      if (partner != null) {
        // The grant may have expired since the page loaded; the risk engine itself does not check expiry.
        const grant = partners.find((g) => g.case_id === partner);
        if (!grant || effectiveConsentStatus(grant) !== 'GRANTED') {
          throw new ApiError(403, 'CONSENT_REQUIRED', 'Your partner’s consent for this record is no longer active.');
        }
        // Re-read the partner's record on every run (not cached), so the server re-checks consent,
        // revocation and expiry. The engine also treats a condition missing from the partner's record
        // as a negative screen, so confirm the partner was actually screened for it.
        const shared = await api.getSharedCase(partner);
        if (!shared.findings.some((f) => f.condition_code === finding.condition_code)) {
          setResult(null);
          setNotScreened(shared.owner_display_name);
          return;
        }
      }
      const data = await api.assessCase(caseId, { condition_code: finding.condition_code, partner_case_id: partner });
      setResult({ data, joint: partner != null });
    } catch (e) {
      setResult(null);
      setError(e instanceof ApiError ? e : new ApiError(0, 'INTERNAL_ERROR', 'Assessment failed.'));
    } finally {
      setPending(false);
    }
  };

  return (
    <li className="finding">
      <div className="finding-head">
        <div>
          <h3 className="finding-title">{finding.condition_name}</h3>
          <p className="muted small">
            {finding.condition_code} · {inheritanceLabel(finding.inheritance_mode)}
          </p>
        </div>
        <div className="finding-badges">
          <Badge tone={carrierTone(finding.carrier_state)}>{carrierLabel(finding.carrier_state)}</Badge>
          {!finding.reviewed_flag && <Badge tone="warn">Awaiting review</Badge>}
        </div>
      </div>
      {finding.summary_text && <p className="finding-summary">{finding.summary_text}</p>}

      <div className="assess-row">
        {partners.length > 0 && (
          <Field label="Assess with">
            <select value={partnerCaseId} onChange={(e) => setPartnerCaseId(e.target.value)}>
              <option value="">My result only</option>
              {partners.map((g) => (
                <option key={g.id} value={g.case_id!}>
                  {g.granter_name} (shared record #{g.case_id})
                </option>
              ))}
            </select>
          </Field>
        )}
        <Button variant="ghost" size="sm" onClick={run} pending={pending}>
          {result ? 'Re-run assessment' : 'See what this means'}
        </Button>
      </div>

      {notScreened && (
        <Banner tone="info" title="A joint assessment isn’t possible for this condition">
          <p>
            {notScreened}’s shared record doesn’t include a {finding.condition_name} result, so a couple-level assessment
            would not be meaningful. Partner screening for this condition would be needed first.
          </p>
        </Banner>
      )}
      {error && <ErrorNote error={error} />}
      {error?.code === 'CONSENT_REQUIRED' && (
        <p className="muted small">
          Your partner’s consent is no longer active. <Link to="/app/sharing" className="text-link">Check sharing</Link>.
        </p>
      )}
      {result && (
        <div className="finding-result">
          <RiskResult assessment={result.data} caseId={caseId} joint={result.joint} />
        </div>
      )}
    </li>
  );
}

export function CaseDetailPage({ caseId }: { caseId: number }) {
  const { user } = useAuth();
  const detail = useAsync(() => api.getCase(caseId), [caseId]);
  const grants = useAsync(() => api.listConsents(), []);
  const triggers = useAsync(() => api.checkEscalation(caseId), [caseId]);

  if (detail.status === 'loading') return <Loading label="Loading result" />;
  if (detail.status === 'error')
    return (
      <>
        <Link to="/app/results" className="back-link">← All results</Link>
        <ErrorNote error={detail.error} onRetry={detail.reload} />
      </>
    );

  const c = detail.data;
  const partners = grants.status === 'success' && user ? linkedPartnerCases(grants.data, user.id) : [];

  return (
    <>
      <Link to="/app/results" className="back-link">← All results</Link>
      <PageHeader eyebrow={c.synthetic_case_code} title={c.screening_scope_label}>
        {c.source_reviewed ? 'Reviewed by a clinician.' : 'Not yet clinician reviewed.'} Choose a condition to see an
        explanation and per-pregnancy probabilities where they can be calculated.
      </PageHeader>

      {triggers.status === 'success' && triggers.data.length > 0 && (
        <Banner
          tone="amber"
          title="Some findings should be reviewed by a counsellor"
          actions={
            <Link to="/app/counselling" className="btn btn-primary btn-sm">
              Go to counselling
            </Link>
          }
        >
          <p>{triggers.data.map(triggerLabel).join(' · ')}</p>
        </Banner>
      )}

      <div className="split">
        <Panel title="Conditions screened">
          <ul className="finding-list">
            {c.findings.map((f) => (
              <FindingAssessment key={f.id} caseId={c.id} finding={f} partners={partners} />
            ))}
          </ul>
          {grants.status === 'success' && partners.length === 0 && (
            <p className="muted small panel-foot">
              To see couple-level results, your partner needs to share a screening record with you.{' '}
              <Link to="/app/sharing" className="text-link">Manage sharing</Link>
            </p>
          )}
        </Panel>

        <aside className="stack">
          <Panel title="Understand your result">
            <p className="muted">
              Read a clinician-approved explanation, then check your understanding with three short questions.
            </p>
            <Link to={`/app/results/${c.id}/learn`} className="btn btn-primary btn-sm">
              Explanation & check
            </Link>
          </Panel>
          <p className="muted small">{c.educational_disclaimer}</p>
        </aside>
      </div>
    </>
  );
}
