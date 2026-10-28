/** Plain-language labels for backend enum values. Unknown values fall back to a readable form. */

const humanize = (v: string) =>
  v
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/^\w/, (c) => c.toUpperCase());

const CARRIER: Record<string, string> = {
  CARRIER_DETECTED: 'Carrier detected',
  NO_VARIANT_DETECTED: 'No variant detected',
  UNCERTAIN_SIGNIFICANCE: 'Uncertain significance',
  POSITIVE_AFFECTED: 'Affected',
  NOT_PERFORMED: 'Not performed',
  INCONCLUSIVE: 'Inconclusive',
};

const INHERITANCE: Record<string, string> = {
  AUTOSOMAL_RECESSIVE: 'Autosomal recessive',
  AUTOSOMAL_DOMINANT: 'Autosomal dominant',
  X_LINKED_RECESSIVE: 'X-linked recessive',
  X_LINKED_DOMINANT: 'X-linked dominant',
  MITOCHONDRIAL: 'Mitochondrial',
  MULTIFACTORIAL: 'Multifactorial',
  UNKNOWN: 'Unknown',
};

const SCOPE: Record<string, { label: string; detail: string }> = {
  carrier_status_only: {
    label: 'Carrier status only',
    detail: 'Shows only whether a carrier state was detected for each condition. Summaries are hidden.',
  },
  summary_only: {
    label: 'Summary',
    detail: 'Shows carrier summaries and condition education.',
  },
  full_report: {
    label: 'Full report',
    detail: 'Shows the complete synthetic screening report.',
  },
  owner_full: { label: 'Your own record', detail: 'You own this record.' },
};

const TRIGGER: Record<string, string> = {
  VARIANT_OF_UNCERTAIN_SIGNIFICANCE: 'Variant of uncertain significance',
  UNSUPPORTED_INHERITANCE_PATTERN: 'Inheritance pattern not modelled',
  DUAL_CARRIER_AUTOSOMAL_RECESSIVE: 'Both partners are carriers',
  AFFECTED_PARTNER_CLINICAL_REVIEW: 'Affected partner — clinical review',
  INCOMPLETE_OR_CONFLICTING_FINDINGS: 'Incomplete or conflicting findings',
  CLINICIAN_REVIEW_REQUIRED: 'Clinician review required',
  CARRIER_RESULT_CONSULT: 'Carrier result consultation',
};

export const carrierLabel = (v: string) => CARRIER[v] ?? humanize(v);
export const inheritanceLabel = (v: string) => INHERITANCE[v] ?? humanize(v);
export const scopeLabel = (v: string) => SCOPE[v]?.label ?? humanize(v);
export const scopeDetail = (v: string) => SCOPE[v]?.detail ?? '';
export const triggerLabel = (v: string) => TRIGGER[v] ?? TRIGGER[v.replace(/^CLINICAL_/, '')] ?? humanize(v);
export const statusLabel = (v: string) => humanize(v);

/** Tone used for badges. */
export function carrierTone(v: string): 'amber' | 'teal' | 'warn' | 'muted' {
  if (v === 'CARRIER_DETECTED' || v === 'POSITIVE_AFFECTED') return 'amber';
  if (v === 'NO_VARIANT_DETECTED') return 'teal';
  if (v === 'UNCERTAIN_SIGNIFICANCE' || v === 'INCONCLUSIVE') return 'warn';
  return 'muted';
}

export function consentTone(v: string): 'teal' | 'warn' | 'muted' {
  if (v === 'GRANTED') return 'teal';
  if (v === 'PENDING') return 'warn';
  return 'muted';
}

export function referralTone(v: string): 'teal' | 'warn' | 'amber' | 'muted' {
  if (v === 'PENDING') return 'warn';
  if (v === 'SCHEDULED') return 'amber';
  if (v === 'COMPLETED') return 'teal';
  return 'muted';
}

/**
 * Maps the risk engine's `referral_reason` to a trigger accepted by
 * POST /counselling/escalations (backend EscalationService.SUPPORTED_ESCALATION_REASONS).
 */
export function escalationTriggerFor(referralReason: string | null) {
  switch (referralReason) {
    case 'VARIANT_OF_UNCERTAIN_SIGNIFICANCE':
    case 'UNSUPPORTED_INHERITANCE_PATTERN':
    case 'DUAL_CARRIER_AUTOSOMAL_RECESSIVE':
    case 'AFFECTED_PARTNER_CLINICAL_REVIEW':
    case 'INCOMPLETE_OR_CONFLICTING_FINDINGS':
    case 'CLINICIAN_REVIEW_REQUIRED':
      return referralReason;
    case 'LAB_FINDINGS_INSUFFICIENT':
    case 'UNRESOLVED_FINDING_COMBINATION':
      return 'INCOMPLETE_OR_CONFLICTING_FINDINGS';
    default:
      // REPORT_REVIEW_PENDING, UNVERIFIED_RESIDUAL_RISK_PROVENANCE, or none.
      return 'CLINICIAN_REVIEW_REQUIRED';
  }
}

/** Parses backend timestamps, which are UTC but sometimes sent without a zone suffix. */
export function parseUtc(iso: string) {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
}

/**
 * The backend only flips a grant to EXPIRED when a shared record is read, so a
 * GRANTED grant past its `expires_at` is treated as expired in the UI.
 */
export function effectiveConsentStatus(g: { status: string; expires_at: string | null }) {
  if (g.status === 'GRANTED' && g.expires_at && parseUtc(g.expires_at).getTime() <= Date.now()) return 'EXPIRED';
  return g.status;
}

export function formatDate(iso: string | null | undefined) {
  if (!iso) return '—';
  const d = parseUtc(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function formatPercent(p: number) {
  const v = p * 100;
  if (v === 0) return '0%';
  if (v < 1) return `${v.toFixed(2)}%`;
  return `${Number.isInteger(v) ? v.toFixed(0) : v.toFixed(2)}%`;
}
