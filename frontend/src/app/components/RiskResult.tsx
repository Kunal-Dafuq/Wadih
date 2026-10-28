import { useState } from 'react';
import { api } from '../../lib/api';
import { Link } from '../../lib/router';
import { useAction } from '../../lib/useAsync';
import type { EscalationResult, RiskAssessment, RiskEstimate } from '../../lib/types';
import { escalationTriggerFor, formatDate, formatPercent, inheritanceLabel, triggerLabel } from '../labels';
import { Badge, Banner, Button, ErrorNote } from '../ui';

const STATUS_META: Record<RiskAssessment['assessment_status'], { label: string; tone: 'teal' | 'warn' | 'amber' | 'muted' }> = {
  EDUCATIONAL_RESULT: { label: 'Educational result', tone: 'teal' },
  REVIEW_REQUIRED: { label: 'Review required', tone: 'warn' },
  INSUFFICIENT_DATA: { label: 'Insufficient data', tone: 'amber' },
  UNSUPPORTED_INHERITANCE_PATTERN: { label: 'Pattern not modelled', tone: 'muted' },
};

/** Per-pregnancy outcome bars. Only rendered when the engine returned numeric probabilities. */
function ProbabilityBars({ estimate }: { estimate: RiskEstimate }) {
  const rows = [
    { key: 'affected', label: 'Affected', value: estimate.affected_probability, cls: 'bar-affected' },
    { key: 'carrier', label: 'Carrier (unaffected)', value: estimate.carrier_probability, cls: 'bar-carrier' },
    { key: 'clear', label: 'Unaffected non-carrier', value: estimate.unaffected_non_carrier_probability, cls: 'bar-clear' },
  ].filter((r): r is typeof r & { value: number } => typeof r.value === 'number');

  if (!rows.length) return null;
  return (
    <figure className="prob">
      <figcaption className="prob-caption">{estimate.summary_label}</figcaption>
      <div className="prob-stack" aria-hidden="true">
        {rows.map((r) => (
          <span key={r.key} className={`prob-seg ${r.cls}`} style={{ flexGrow: Math.max(r.value, 0.004) }} />
        ))}
      </div>
      <dl className="prob-legend">
        {rows.map((r) => (
          <div key={r.key}>
            <dt>
              <i className={`prob-dot ${r.cls}`} aria-hidden="true" />
              {r.label}
            </dt>
            <dd>{formatPercent(r.value)}</dd>
          </div>
        ))}
      </dl>
      {estimate.residual_carrier_probability_used != null && (
        <p className="prob-note">
          Uses a clinician-verified residual carrier probability of{' '}
          {formatPercent(estimate.residual_carrier_probability_used)} for the partner who screened negative.
        </p>
      )}
      <p className="prob-note">{estimate.recurrence_note}</p>
    </figure>
  );
}

function Paragraphs({ text }: { text: string }) {
  return (
    <>
      {text.split(/\n{2,}/).map((p, i) => (
        <p key={i} className="prose-p">
          {p.split('\n').map((line, j) => (
            <span key={j}>
              {j > 0 && <br />}
              {line}
            </span>
          ))}
        </p>
      ))}
    </>
  );
}

/** One-click escalation to simulated counselling for a stored case the caller owns. */
function EscalateButton({ caseId, assessment, label }: { caseId: number; assessment: RiskAssessment; label: string }) {
  const [done, setDone] = useState<EscalationResult | null>(null);
  const trigger = escalationTriggerFor(assessment.referral_reason);
  const action = useAction(() =>
    api.escalate({
      case_id: caseId,
      trigger_reason: trigger,
      urgency_level: assessment.assessment_status === 'REVIEW_REQUIRED' ? 'PRIORITY' : 'ROUTINE',
      clinical_rationale: `Requested from ${assessment.condition} result (${assessment.assessment_status}).`,
    }),
  );

  if (done) {
    return (
      <Banner tone="teal" title="Counselling referral created">
        <p>
          {triggerLabel(done.trigger_reason)} · {done.urgency_level.toLowerCase()} · status {done.status.toLowerCase()}
          {done.assigned_counsellor_name && <> · assigned to {done.assigned_counsellor_name}</>}
        </p>
        <p>{done.guidance_note}</p>
        <p>
          <Link to="/app/counselling" className="text-link">
            View in Counselling
          </Link>{' '}
          <span className="muted">· created {formatDate(done.created_at)}</span>
        </p>
      </Banner>
    );
  }
  return (
    <div className="stack-sm">
      <Button onClick={async () => setDone((await action.run()) ?? null)} pending={action.pending}>
        {label}
      </Button>
      {action.error && <ErrorNote error={action.error} />}
    </div>
  );
}

export interface RiskResultProps {
  assessment: RiskAssessment;
  /** Owned case the result came from; enables escalation. Absent for scenario explorer results. */
  caseId?: number;
  /** Whether a partner's results were part of this assessment. */
  joint?: boolean;
  /** Hide participant-only actions (counsellor view). */
  readOnly?: boolean;
}

export function RiskResult({ assessment: a, caseId, joint, readOnly }: RiskResultProps) {
  const meta = STATUS_META[a.assessment_status];
  const canEscalate = caseId != null && !readOnly;
  const counsellingLink = !readOnly && (
    <Link to="/app/counselling" className="btn btn-ghost btn-sm">
      Go to counselling
    </Link>
  );

  return (
    <article className="risk" data-status={a.assessment_status}>
      <header className="risk-head">
        <div>
          <p className="eyebrow">
            {a.gene ? `${a.gene} · ` : ''}
            {inheritanceLabel(a.inheritance_pattern)}
          </p>
          <h3 className="risk-title">{a.condition}</h3>
        </div>
        <div className="risk-badges">
          <Badge tone={meta.tone}>{meta.label}</Badge>
          {joint && <Badge tone="muted">Joint assessment</Badge>}
        </div>
      </header>

      {/* State-specific presentation per API_CONTRACT_NIHARIKA.md §1 */}
      {a.assessment_status === 'EDUCATIONAL_RESULT' &&
        (a.risk_estimate ? (
          <ProbabilityBars estimate={a.risk_estimate} />
        ) : (
          <Banner tone="teal" title="No numeric probability shown">
            <p>
              Screening cannot rule out every variant, so Wadih does not show a zero-risk figure. Read the explanation and
              limitations below.
            </p>
          </Banner>
        ))}

      {a.assessment_status === 'REVIEW_REQUIRED' && (
        <Banner
          tone="amber"
          title="Genetic Counsellor Review Required"
          actions={canEscalate ? undefined : counsellingLink}
        >
          <p>Percentages are not shown for this result. A counsellor should review it first.</p>
          {canEscalate && <EscalateButton caseId={caseId} assessment={a} label="Request counsellor review" />}
        </Banner>
      )}

      {a.assessment_status === 'INSUFFICIENT_DATA' && (
        <Banner
          tone="info"
          title={joint ? 'A couple-level figure is not available yet' : 'Couple-level risk needs your partner’s results'}
          actions={
            !readOnly &&
            !joint && (
              <Link to="/app/sharing" className="btn btn-primary btn-sm">
                Invite partner
              </Link>
            )
          }
        >
          {joint ? (
            <>
              <p>
                A clinician-verified residual carrier probability for the partner who screened negative is needed before a
                number can be shown. A counsellor can record it after review.
              </p>
              {canEscalate && !a.requires_genetic_counselor && (
                <EscalateButton caseId={caseId} assessment={a} label="Ask a counsellor to review" />
              )}
            </>
          ) : (
            <p>Invite partner to link results for joint pre-conception assessment.</p>
          )}
        </Banner>
      )}

      {a.assessment_status === 'UNSUPPORTED_INHERITANCE_PATTERN' && (
        <Banner tone="info" title="This inheritance pattern is not modelled" actions={canEscalate ? undefined : counsellingLink}>
          <p>
            Wadih’s calculator only models autosomal recessive conditions. {inheritanceLabel(a.inheritance_pattern)}{' '}
            inheritance needs individual review by a genetics specialist.
          </p>
          {canEscalate && <EscalateButton caseId={caseId} assessment={a} label="Request counselling referral" />}
        </Banner>
      )}

      <div className="risk-body">
        <section>
          <h4 className="mini-title">What this means</h4>
          <Paragraphs text={a.explanation} />
        </section>

        {a.residual_risk_source && (
          <p className="muted small">Residual-risk source: {a.residual_risk_source}</p>
        )}

        <div className="risk-cols">
          {a.limitations.length > 0 && (
            <section>
              <h4 className="mini-title">Limitations</h4>
              <ul className="ticks">
                {a.limitations.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </section>
          )}
          {a.assumptions.length > 0 && (
            <section>
              <h4 className="mini-title">Assumptions</h4>
              <ul className="ticks">
                {a.assumptions.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </section>
          )}
        </div>

        {/* Dual carriers etc. return EDUCATIONAL_RESULT but still recommend counselling. */}
        {a.requires_genetic_counselor &&
          (a.assessment_status === 'EDUCATIONAL_RESULT' || a.assessment_status === 'INSUFFICIENT_DATA') &&
          !readOnly && (
            <div className="risk-cta">
              <p>
                Counselling is recommended
                {a.referral_reason ? <> ({triggerLabel(a.referral_reason).toLowerCase()})</> : null}.
              </p>
              {canEscalate ? (
                <EscalateButton caseId={caseId} assessment={a} label="Request counselling" />
              ) : (
                counsellingLink
              )}
            </div>
          )}
      </div>

      <footer className="risk-foot">
        <p>{a.disclaimer}</p>
        <p className="muted small">Rule set {a.rule_version}</p>
      </footer>
    </article>
  );
}
