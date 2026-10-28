import { useState, type FormEvent } from 'react';
import { api, ApiError } from '../../lib/api';
import { Link } from '../../lib/router';
import { useAction, useAsync } from '../../lib/useAsync';
import type { ClinicalProvenance, ReferralStatus, RiskAssessment, SyntheticFinding } from '../../lib/types';
import { RiskResult } from '../components/RiskResult';
import { carrierLabel, carrierTone, formatDate, formatPercent, inheritanceLabel, referralTone, statusLabel, triggerLabel } from '../labels';
import { Badge, Banner, Button, Empty, ErrorNote, Field, Loading, PageHeader, Panel } from '../ui';

const STATUS_ORDER: ReferralStatus[] = ['PENDING', 'SCHEDULED', 'COMPLETED', 'CANCELLED'];

export function ReferralsPage() {
  const referrals = useAsync(() => api.listReferrals(), []);
  const [filter, setFilter] = useState<'open' | 'all'>('open');

  const items =
    referrals.status === 'success'
      ? referrals.data.filter((r) => filter === 'all' || r.status === 'PENDING' || r.status === 'SCHEDULED')
      : [];

  return (
    <>
      <PageHeader eyebrow="Counsellor portal" title={<>Assigned <em>referrals.</em></>}>
        Referrals assigned to you. Open one to review the screening record, add session notes and update its status.
      </PageHeader>
      <div className="chip-row tabs" role="tablist">
        {(['open', 'all'] as const).map((f) => (
          <button key={f} type="button" role="tab" aria-selected={filter === f} className="chip" onClick={() => setFilter(f)}>
            {f === 'open' ? 'Open' : 'All'}
          </button>
        ))}
      </div>
      {referrals.status === 'loading' && <Loading label="Loading referrals" />}
      {referrals.status === 'error' && <ErrorNote error={referrals.error} onRetry={referrals.reload} />}
      {referrals.status === 'success' &&
        (items.length === 0 ? (
          <Empty title={filter === 'open' ? 'No open referrals' : 'No referrals assigned'} />
        ) : (
          <ul className="case-list">
            {items.map((r) => (
              <li key={r.id}>
                <Link to={`/app/referrals/${r.id}`} className="case-card">
                  <div>
                    <p className="eyebrow">
                      {r.case_code} · referral #{r.id}
                    </p>
                    <h2 className="case-card-title">{triggerLabel(r.reason_code)}</h2>
                    <p className="muted small">
                      Participant #{r.participant_user_id} · updated {formatDate(r.updated_at)}
                    </p>
                  </div>
                  <div className="case-card-meta">
                    <Badge tone={referralTone(r.status)}>{statusLabel(r.status)}</Badge>
                    <span className="muted small">{r.urgency_level.toLowerCase()}</span>
                    <span className="muted small">{r.notes.length} notes</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        ))}
    </>
  );
}

function CaseFindingReview({ caseId, finding }: { caseId: number; finding: SyntheticFinding }) {
  const [result, setResult] = useState<RiskAssessment | null>(null);
  const action = useAction(() => api.assessCase(caseId, { condition_code: finding.condition_code }));
  return (
    <li className="finding">
      <div className="finding-head">
        <div>
          <h3 className="finding-title">{finding.condition_name}</h3>
          <p className="muted small">
            {finding.condition_code} · {inheritanceLabel(finding.inheritance_mode)} · {finding.classification_state}
          </p>
        </div>
        <div className="finding-badges">
          <Badge tone={carrierTone(finding.carrier_state)}>{carrierLabel(finding.carrier_state)}</Badge>
          <Badge tone={finding.reviewed_flag ? 'teal' : 'warn'}>{finding.reviewed_flag ? 'Reviewed' : 'Unreviewed'}</Badge>
        </div>
      </div>
      {finding.summary_text && <p className="finding-summary">{finding.summary_text}</p>}
      <div className="assess-row">
        <Button variant="ghost" size="sm" pending={action.pending} onClick={async () => setResult((await action.run()) ?? null)}>
          Run engine on this finding
        </Button>
      </div>
      {action.error && <ErrorNote error={action.error} />}
      {result && (
        <div className="finding-result">
          <RiskResult assessment={result} readOnly />
        </div>
      )}
    </li>
  );
}

export function ReferralDetailPage({ referralId }: { referralId: number }) {
  const referral = useAsync(() => api.getReferral(referralId), [referralId]);
  const caseId = referral.status === 'success' ? referral.data.case_id : null;
  const caseDetail = useAsync(() => (caseId ? api.getCase(caseId) : Promise.resolve(null)), [caseId]);
  const [note, setNote] = useState('');
  const addNote = useAction(() => api.addReferralNote(referralId, note.trim()));
  const setStatus = useAction((s: ReferralStatus) => api.updateReferralStatus(referralId, s));

  if (referral.status === 'loading') return <Loading label="Loading referral" />;
  if (referral.status === 'error')
    return (
      <>
        <Link to="/app/referrals" className="back-link">← Referrals</Link>
        <ErrorNote error={referral.error} onRetry={referral.reload} />
      </>
    );
  const r = referral.data;

  const submitNote = async (e: FormEvent) => {
    e.preventDefault();
    if (await addNote.run()) {
      setNote('');
      referral.reload();
    }
  };

  return (
    <>
      <Link to="/app/referrals" className="back-link">← Referrals</Link>
      <PageHeader eyebrow={`${r.case_code} · referral #${r.id}`} title={triggerLabel(r.reason_code)}>
        <Badge tone={referralTone(r.status)}>{statusLabel(r.status)}</Badge> {r.urgency_level.toLowerCase()} · participant #
        {r.participant_user_id} · requested {formatDate(r.created_at)}
      </PageHeader>

      <div className="split">
        <div className="stack">
          <Panel title="Screening record">
            {caseDetail.status === 'loading' && <Loading label="Loading record" />}
            {caseDetail.status === 'error' && <ErrorNote error={caseDetail.error} onRetry={caseDetail.reload} />}
            {caseDetail.status === 'success' && caseDetail.data && (
              <>
                <p className="muted small">
                  {caseDetail.data.screening_scope_label} · {caseDetail.data.source_reviewed ? 'source reviewed' : 'source not reviewed'}
                </p>
                <ul className="finding-list">
                  {caseDetail.data.findings.map((f) => (
                    <CaseFindingReview key={f.id} caseId={caseDetail.data!.id} finding={f} />
                  ))}
                </ul>
              </>
            )}
          </Panel>
        </div>

        <aside className="stack">
          <Panel title="Status">
            <div className="chip-row">
              {STATUS_ORDER.map((s) => (
                <Button
                  key={s}
                  size="sm"
                  variant={r.status === s ? 'primary' : 'ghost'}
                  disabled={r.status === s}
                  pending={setStatus.pending}
                  onClick={async () => (await setStatus.run(s)) && referral.reload()}
                >
                  {statusLabel(s)}
                </Button>
              ))}
            </div>
            {setStatus.error && <ErrorNote error={setStatus.error} />}
          </Panel>

          <Panel title="Session notes">
            {r.notes.length === 0 ? (
              <p className="muted">No notes yet.</p>
            ) : (
              <ul className="notes">
                {r.notes.map((n) => (
                  <li key={n.id}>
                    <p>{n.note_text}</p>
                    <p className="muted small">
                      {n.author_name} · {formatDate(n.created_at)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
            <form className="share-form" onSubmit={submitNote}>
              <Field label="Add a note">
                <textarea rows={3} minLength={2} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} />
              </Field>
              {addNote.error && <ErrorNote error={addNote.error} />}
              <Button type="submit" size="sm" pending={addNote.pending} disabled={note.trim().length < 2}>
                Save note
              </Button>
            </form>
          </Panel>
          <p className="muted small">{r.service_disclaimer}</p>
        </aside>
      </div>
    </>
  );
}

export function ProvenancePage() {
  const [caseId, setCaseId] = useState('');
  const [conditionCode, setConditionCode] = useState('HBB_BETA_THAL');
  const [percent, setPercent] = useState('');
  const [source, setSource] = useState('');
  const [notes, setNotes] = useState('');
  const [saved, setSaved] = useState<ClinicalProvenance[]>([]);

  const r = Number(percent) / 100;
  const validR = percent !== '' && r > 0 && r < 1;
  const action = useAction(() =>
    api.recordProvenance({
      case_id: Number(caseId),
      condition_code: conditionCode.trim(),
      residual_carrier_probability: r,
      clinical_source_reference: source.trim(),
      notes: notes.trim() || null,
    }),
  );

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const rec = await action.run();
    if (rec) {
      setSaved((s) => [rec, ...s]);
      setPercent('');
      setNotes('');
    }
  };

  const forbidden = action.error instanceof ApiError && action.error.code === 'FORBIDDEN';

  return (
    <>
      <PageHeader eyebrow="Clinician tool" title={<>Residual risk <em>records.</em></>}>
        Record a reviewed residual carrier probability for a participant who screened negative. The risk engine only uses
        a residual risk that has a record here, so couples see a figure only after clinician sign-off.
      </PageHeader>
      <div className="split">
        <Panel title="New record">
          <form className="share-form" onSubmit={submit}>
            <div className="field-row">
              <Field label="Screening record ID" hint="Numeric case ID of the negative-screening partner.">
                <input inputMode="numeric" pattern="[0-9]*" required value={caseId} onChange={(e) => setCaseId(e.target.value.replace(/\D/g, ''))} />
              </Field>
              <Field label="Condition code">
                <input required value={conditionCode} onChange={(e) => setConditionCode(e.target.value)} />
              </Field>
            </div>
            <Field label="Residual carrier probability (%)" hint="Between 0 and 100, exclusive. For example 1 for 1 in 100.">
              <input type="number" step="any" min="0" max="100" required value={percent} onChange={(e) => setPercent(e.target.value)} />
            </Field>
            <Field label="Laboratory source reference" hint="Panel and detection rate the figure comes from.">
              <input required value={source} onChange={(e) => setSource(e.target.value)} />
            </Field>
            <Field label="Notes (optional)">
              <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
            </Field>
            {action.error && <ErrorNote error={action.error} />}
            {forbidden && (
              <p className="muted small">
                You can only record residual risk for cases you are assigned to, or for a partner of a participant you are
                assigned to who has shared their record.
              </p>
            )}
            <Button type="submit" pending={action.pending} disabled={!caseId || !conditionCode.trim() || !validR || !source.trim()}>
              Save record
            </Button>
          </form>
        </Panel>
        <Panel title="Saved this session">
          {saved.length === 0 ? (
            <p className="muted">Records you save appear here. The API has no endpoint to list existing records.</p>
          ) : (
            <ul className="grant-list">
              {saved.map((s) => (
                <li key={s.id} className="grant">
                  <div className="grant-main">
                    <div>
                      <p className="grant-who">
                        Record #{s.case_id} · {s.condition_code}
                      </p>
                      <p className="muted small">
                        r = {formatPercent(s.residual_carrier_probability)} · {s.clinical_source_reference} · reviewed{' '}
                        {formatDate(s.reviewed_at)}
                      </p>
                    </div>
                    <Badge tone={s.is_active ? 'teal' : 'muted'}>{s.is_active ? 'Active' : 'Inactive'}</Badge>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <Banner tone="info" title="How this is used">
            <p>
              When a carrier and a partner who screened negative assess jointly, the engine looks up this record. The client
              cannot supply or override the figure.
            </p>
          </Banner>
        </Panel>
      </div>
    </>
  );
}
