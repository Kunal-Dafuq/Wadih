import { useState, type FormEvent } from 'react';
import { api } from '../../lib/api';
import { useAction, useAsync } from '../../lib/useAsync';
import { ESCALATION_TRIGGERS, type EscalationTrigger, type ReferralTask, type UrgencyLevel } from '../../lib/types';
import { formatDate, referralTone, statusLabel, triggerLabel } from '../labels';
import { Badge, Banner, Button, Empty, ErrorNote, Field, Loading, PageHeader, Panel } from '../ui';

// General consultation code used by the backend seed data for carrier-result referrals.
const GENERAL_REASON = 'CARRIER_RESULT_CONSULT';

function RequestForm({ onCreated }: { onCreated: () => void }) {
  const cases = useAsync(() => api.listCases(), []);
  const [caseId, setCaseId] = useState('');
  const [reason, setReason] = useState<string>(GENERAL_REASON);
  const [urgency, setUrgency] = useState<UrgencyLevel>('ROUTINE');
  const [rationale, setRationale] = useState('');
  const [created, setCreated] = useState<string | null>(null);

  const selectedCase = caseId || (cases.status === 'success' && cases.data[0] ? String(cases.data[0].id) : '');

  const action = useAction(async () => {
    const case_id = Number(selectedCase);
    if (reason === GENERAL_REASON) {
      await api.createReferral({ case_id, reason_code: GENERAL_REASON, urgency_level: urgency });
    } else {
      await api.escalate({
        case_id,
        trigger_reason: reason as EscalationTrigger,
        urgency_level: urgency,
        clinical_rationale: rationale.trim() || null,
      });
    }
    return true;
  });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (await action.run()) {
      setCreated(triggerLabel(reason));
      setRationale('');
      onCreated();
    }
  };

  return (
    <form className="share-form" onSubmit={submit}>
      {created && (
        <Banner tone="teal" title="Request sent">
          <p>{created} — it now appears in your referrals.</p>
        </Banner>
      )}
      <Field label="About which record">
        <select value={selectedCase} onChange={(e) => setCaseId(e.target.value)} disabled={cases.status !== 'success'}>
          {cases.status === 'success' &&
            cases.data.map((c) => (
              <option key={c.id} value={c.id}>
                {c.synthetic_case_code} — {c.screening_scope_label}
              </option>
            ))}
        </select>
      </Field>
      {cases.status === 'error' && <ErrorNote error={cases.error} onRetry={cases.reload} />}
      <Field label="Reason">
        <select value={reason} onChange={(e) => setReason(e.target.value)}>
          <option value={GENERAL_REASON}>{triggerLabel(GENERAL_REASON)}</option>
          {ESCALATION_TRIGGERS.map((t) => (
            <option key={t} value={t}>
              {triggerLabel(t)}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Urgency">
        <select value={urgency} onChange={(e) => setUrgency(e.target.value as UrgencyLevel)}>
          <option value="ROUTINE">Routine</option>
          <option value="PRIORITY">Priority</option>
          <option value="URGENT">Urgent</option>
        </select>
      </Field>
      {reason !== GENERAL_REASON && (
        <Field label="Anything the counsellor should know (optional)">
          <textarea rows={3} maxLength={1000} value={rationale} onChange={(e) => setRationale(e.target.value)} />
        </Field>
      )}
      {action.error && <ErrorNote error={action.error} />}
      <Button type="submit" pending={action.pending} disabled={!selectedCase}>
        Request counselling
      </Button>
    </form>
  );
}

function ReferralCard({ r, onChange }: { r: ReferralTask; onChange: () => void }) {
  const cancel = useAction(() => api.updateReferralStatus(r.id, 'CANCELLED'));
  const [confirm, setConfirm] = useState(false);
  const open = r.status === 'PENDING' || r.status === 'SCHEDULED';

  return (
    <li className="referral">
      <div className="grant-main">
        <div>
          <p className="grant-who">{triggerLabel(r.reason_code)}</p>
          <p className="muted small">
            {r.case_code} · {r.urgency_level.toLowerCase()} · requested {formatDate(r.created_at)}
            {r.assigned_counsellor_name && <> · {r.assigned_counsellor_name}</>}
          </p>
        </div>
        <Badge tone={referralTone(r.status)}>{statusLabel(r.status)}</Badge>
      </div>
      {r.notes.length > 0 && (
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
      {open && (
        <div className="grant-actions">
          {!confirm ? (
            <Button variant="quiet" size="sm" onClick={() => setConfirm(true)}>
              Cancel request
            </Button>
          ) : (
            <span className="confirm">
              Cancel this referral?
              <Button variant="danger" size="sm" pending={cancel.pending} onClick={async () => (await cancel.run()) && onChange()}>
                Yes, cancel
              </Button>
              <Button variant="quiet" size="sm" onClick={() => setConfirm(false)}>
                Keep
              </Button>
            </span>
          )}
        </div>
      )}
      {cancel.error && <ErrorNote error={cancel.error} />}
    </li>
  );
}

export function CounsellingPage() {
  const referrals = useAsync(() => api.listReferrals(), []);

  return (
    <>
      <PageHeader eyebrow="Counselling" title={<>Talk it through with <em>a counsellor.</em></>}>
        Request a simulated genetic counselling referral and follow its progress. No real appointments are booked.
      </PageHeader>
      <div className="split">
        <Panel title="Your referrals">
          {referrals.status === 'loading' && <Loading label="Loading referrals" />}
          {referrals.status === 'error' && <ErrorNote error={referrals.error} onRetry={referrals.reload} />}
          {referrals.status === 'success' &&
            (referrals.data.length === 0 ? (
              <Empty title="No referrals yet">Request one from a result or with the form.</Empty>
            ) : (
              <>
                <ul className="grant-list">
                  {referrals.data.map((r) => (
                    <ReferralCard key={r.id} r={r} onChange={referrals.reload} />
                  ))}
                </ul>
                <p className="muted small panel-foot">{referrals.data[0].service_disclaimer}</p>
              </>
            ))}
        </Panel>
        <Panel title="Request counselling">
          <RequestForm onCreated={referrals.reload} />
        </Panel>
      </div>
    </>
  );
}
