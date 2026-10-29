import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { Link } from '../../lib/router';
import { useAction, useAsync } from '../../lib/useAsync';
import type { ConsentGrant, ConsentScope } from '../../lib/types';
import { consentTone, effectiveConsentStatus, formatDate, scopeDetail, scopeLabel, statusLabel } from '../labels';
import { Badge, Banner, Button, Empty, ErrorNote, Field, Loading, PageHeader, Panel } from '../ui';

const SCOPES: ConsentScope[] = ['carrier_status_only', 'summary_only', 'full_report'];
// Backend defaults (schemas/consent.py); the purpose is the only one the platform currently supports.
const PURPOSE = 'preconception_carrier_screening';
const TERMS_VERSION = 'v1.0';

function ShareForm({ onCreated }: { onCreated: (g: ConsentGrant) => void }) {
  const cases = useAsync(() => api.listCases(), []);
  const [email, setEmail] = useState('');
  const [caseId, setCaseId] = useState('');
  const [scope, setScope] = useState<ConsentScope>('summary_only');
  const [mode, setMode] = useState<'invite' | 'grant'>('invite');
  const [expiry, setExpiry] = useState('30');

  const action = useAction(async () => {
    const case_id = caseId ? Number(caseId) : null;
    if (mode === 'invite') {
      return api.createSharingRequest({ partner_email: email.trim(), scope, purpose: PURPOSE, case_id });
    }
    return api.createConsent({
      grantee_email: email.trim(),
      scope,
      purpose: PURPOSE,
      case_id,
      terms_version: TERMS_VERSION,
      expires_in_days: expiry ? Number(expiry) : null,
    });
  });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const g = await action.run();
    if (g) {
      onCreated(g);
      setEmail('');
    }
  };

  // Default to the first owned case once loaded.
  const firstCase = cases.status === 'success' ? cases.data[0]?.id : undefined;
  useEffect(() => {
    if (firstCase != null) setCaseId((v) => v || String(firstCase));
  }, [firstCase]);

  return (
    <form onSubmit={submit} className="share-form">
      <Field label="Partner’s email" hint="Your partner needs a Wadih account with this email.">
        <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </Field>

      <Field label="Record to share">
        <select value={caseId} onChange={(e) => setCaseId(e.target.value)} disabled={cases.status !== 'success'}>
          {cases.status === 'success' &&
            cases.data.map((c) => (
              <option key={c.id} value={c.id}>
                {c.synthetic_case_code} — {c.screening_scope_label}
              </option>
            ))}
        </select>
      </Field>
      {cases.status === 'error' && <ErrorNote error={cases.error} onRetry={cases.reload} />}

      <fieldset className="field">
        <legend className="field-label">What they can see</legend>
        <div className="scope-options">
          {SCOPES.map((s) => (
            <label key={s} className="option" data-checked={scope === s || undefined}>
              <input type="radio" name="scope" value={s} checked={scope === s} onChange={() => setScope(s)} />
              <span>
                <strong>{scopeLabel(s)}</strong>
                <small>{scopeDetail(s)}</small>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="field">
        <legend className="field-label">How to share</legend>
        <div className="scope-options two">
          <label className="option" data-checked={mode === 'invite' || undefined}>
            <input type="radio" name="mode" checked={mode === 'invite'} onChange={() => setMode('invite')} />
            <span>
              <strong>Send an invitation</strong>
              <small>Creates a pending request. Nothing is shared until you confirm it below.</small>
            </span>
          </label>
          <label className="option" data-checked={mode === 'grant' || undefined}>
            <input type="radio" name="mode" checked={mode === 'grant'} onChange={() => setMode('grant')} />
            <span>
              <strong>Grant access now</strong>
              <small>Your partner can see the record straight away, until it expires or you revoke it.</small>
            </span>
          </label>
        </div>
      </fieldset>

      {mode === 'grant' && (
        <Field label="Access expires">
          <select value={expiry} onChange={(e) => setExpiry(e.target.value)}>
            <option value="7">After 7 days</option>
            <option value="30">After 30 days</option>
            <option value="90">After 90 days</option>
            <option value="">Never (until revoked)</option>
          </select>
        </Field>
      )}

      {action.error && <ErrorNote error={action.error} />}
      <Button type="submit" pending={action.pending} disabled={!email || !caseId}>
        {mode === 'invite' ? 'Create invitation' : 'Grant access'}
      </Button>
      <p className="muted small">You can revoke access at any time. Revoking blocks your partner’s access immediately.</p>
    </form>
  );
}

function GrantRow({ g, outgoing, onChange }: { g: ConsentGrant; outgoing: boolean; onChange: () => void }) {
  const approve = useAction(() => api.approveConsent(g.id));
  const revoke = useAction(() => api.revokeConsent(g.id));
  const [confirmRevoke, setConfirmRevoke] = useState(false);
  const status = effectiveConsentStatus(g);
  const live = status === 'PENDING' || status === 'GRANTED';

  return (
    <li className="grant">
      <div className="grant-main">
        <div>
          <p className="grant-who">{outgoing ? `To ${g.grantee_name}` : `From ${g.granter_name}`}</p>
          <p className="muted small">
            {scopeLabel(g.scope)}
            {g.case_id != null && <> · record #{g.case_id}</>} · created {formatDate(g.created_at)}
            {g.expires_at && (
              <>
                {' '}
                · {status === 'EXPIRED' ? 'expired' : 'expires'} {formatDate(g.expires_at)}
              </>
            )}
            {g.revoked_at && <> · revoked {formatDate(g.revoked_at)}</>}
          </p>
        </div>
        <Badge tone={consentTone(status)}>{statusLabel(status)}</Badge>
      </div>

      <div className="grant-actions">
        {outgoing && status === 'PENDING' && (
          <Button size="sm" pending={approve.pending} onClick={async () => (await approve.run()) && onChange()}>
            Confirm sharing
          </Button>
        )}
        {outgoing && live && !confirmRevoke && (
          <Button variant="quiet" size="sm" onClick={() => setConfirmRevoke(true)}>
            Revoke
          </Button>
        )}
        {outgoing && live && confirmRevoke && (
          <span className="confirm">
            Revoke {g.grantee_name}’s access?
            <Button
              variant="danger"
              size="sm"
              pending={revoke.pending}
              onClick={async () => {
                if (await revoke.run()) {
                  setConfirmRevoke(false);
                  onChange();
                }
              }}
            >
              Yes, revoke
            </Button>
            <Button variant="quiet" size="sm" onClick={() => setConfirmRevoke(false)}>
              Cancel
            </Button>
          </span>
        )}
        {!outgoing && status === 'GRANTED' && g.case_id != null && (
          <Link to={`/app/shared/${g.case_id}`} className="btn btn-ghost btn-sm">
            View shared results
          </Link>
        )}
        {!outgoing && status === 'PENDING' && (
          <span className="muted small">Waiting for {g.granter_name} to confirm.</span>
        )}
      </div>
      {approve.error && <ErrorNote error={approve.error} />}
      {revoke.error && <ErrorNote error={revoke.error} />}
    </li>
  );
}

export function SharingPage() {
  const { user } = useAuth();
  const grants = useAsync(() => api.listConsents(), []);
  const [notice, setNotice] = useState<ConsentGrant | null>(null);

  const outgoing = grants.status === 'success' ? grants.data.filter((g) => g.granter_user_id === user?.id) : [];
  const incoming = grants.status === 'success' ? grants.data.filter((g) => g.grantee_user_id === user?.id) : [];

  return (
    <>
      <PageHeader eyebrow="Consent" title={<>Partner <em>sharing.</em></>}>
        Decide who can see your screening record, how much they can see, and for how long. When your partner shares their
        record with you, you can assess results together.
      </PageHeader>

      <div className="split">
        <Panel title="Share your results">
          {notice && (
            <Banner tone="teal" title={notice.status === 'PENDING' ? 'Invitation created' : 'Access granted'}>
              <p>
                {notice.status === 'PENDING'
                  ? `Nothing is shared with ${notice.grantee_name} until you confirm the invitation under “Shared by you”.`
                  : `${notice.grantee_name} can now see your record (${scopeLabel(notice.scope).toLowerCase()}).`}
              </p>
            </Banner>
          )}
          <ShareForm
            onCreated={(g) => {
              setNotice(g);
              grants.reload();
            }}
          />
        </Panel>

        <div className="stack">
          {grants.status === 'loading' && <Loading label="Loading consent records" />}
          {grants.status === 'error' && <ErrorNote error={grants.error} onRetry={grants.reload} />}
          {grants.status === 'success' && (
            <>
              <Panel title="Shared by you">
                {outgoing.length === 0 ? (
                  <Empty title="You haven’t shared anything" />
                ) : (
                  <ul className="grant-list">
                    {outgoing.map((g) => (
                      <GrantRow
                        key={g.id}
                        g={g}
                        outgoing
                        onChange={() => {
                          setNotice(null);
                          grants.reload();
                        }}
                      />
                    ))}
                  </ul>
                )}
              </Panel>
              <Panel title="Shared with you">
                {incoming.length === 0 ? (
                  <Empty title="Nothing shared with you yet">Ask your partner to share their screening record.</Empty>
                ) : (
                  <ul className="grant-list">
                    {incoming.map((g) => (
                      <GrantRow key={g.id} g={g} outgoing={false} onChange={grants.reload} />
                    ))}
                  </ul>
                )}
                {incoming.some((g) => effectiveConsentStatus(g) === 'GRANTED' && g.case_id != null) && (
                  <p className="muted small panel-foot">
                    Open one of your <Link to="/app/results" className="text-link">results</Link> and choose your partner
                    under “Assess with” to see a joint assessment.
                  </p>
                )}
              </Panel>
            </>
          )}
        </div>
      </div>
    </>
  );
}
