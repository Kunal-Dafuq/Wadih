import type {
  CaseExplanation,
  CaseRiskAssessmentRequest,
  ClinicalProvenance,
  ClinicalProvenanceCreateRequest,
  ConsentGrant,
  ConsentGrantCreateRequest,
  CurrentUser,
  EscalationRequest,
  EscalationResult,
  KnowledgeCheckResult,
  KnowledgeCheckSubmission,
  ReferralCreateRequest,
  ReferralStatus,
  ReferralTask,
  RiskAssessment,
  RiskAssessmentRequest,
  ScreeningCaseDetail,
  ScreeningCaseListItem,
  SharedCaseSummary,
  SharingInvitationRequest,
  CounsellorNote,
  TokenResponse,
} from './types';

/**
 * Base URL for the Wadih API. Empty by default so requests go to `/api/v1/...`
 * on the same origin (the Vite dev server proxies `/api` to the backend).
 */
const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? '';

/** Error codes from the standard error envelope in API_CONTRACT_NIHARIKA.md §3. */
export type ApiErrorCode =
  | 'UNAUTHENTICATED'
  | 'FORBIDDEN'
  | 'CONSENT_REQUIRED'
  | 'NEEDS_CLINICIAN_REVIEW'
  | 'NOT_FOUND'
  | 'VALIDATION_ERROR'
  | 'INTERNAL_ERROR'
  | 'NETWORK_ERROR';

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: ApiErrorCode | string,
    message: string,
    public requestId?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

let token: string | null = null;
let onUnauthenticated: (() => void) | null = null;

export function setToken(value: string | null) {
  token = value;
}

/** Called when any request returns 401, so the session can be cleared. */
export function setUnauthenticatedHandler(fn: (() => void) | null) {
  onUnauthenticated = fn;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'The Wadih service could not be reached. Check that the backend is running.');
  }

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!res.ok) {
    const envelope = (data as { error?: { code?: string; message?: string; request_id?: string } } | null)?.error;
    const err = new ApiError(
      res.status,
      envelope?.code ?? (res.status === 401 ? 'UNAUTHENTICATED' : 'INTERNAL_ERROR'),
      envelope?.message ?? `Request failed (${res.status}).`,
      envelope?.request_id ?? res.headers.get('X-Request-ID') ?? undefined,
    );
    if (res.status === 401 && onUnauthenticated && path !== '/auth/login') onUnauthenticated();
    throw err;
  }
  return data as T;
}

const enc = encodeURIComponent;

export const api = {
  // Auth
  login: (email: string, password: string) => request<TokenResponse>('POST', '/auth/login', { email, password }),
  demoSession: (persona: string) => request<TokenResponse>('POST', '/auth/demo-session', { persona }),
  logout: () => request<{ message: string }>('POST', '/auth/logout'),
  me: () => request<CurrentUser>('GET', '/me'),

  // Cases & education
  listCases: () => request<ScreeningCaseListItem[]>('GET', '/cases'),
  getCase: (id: number) => request<ScreeningCaseDetail>('GET', `/cases/${enc(id)}`),
  getExplanation: (id: number) => request<CaseExplanation>('GET', `/cases/${enc(id)}/explanation`),
  submitKnowledgeCheck: (id: number, body: KnowledgeCheckSubmission) =>
    request<KnowledgeCheckResult>('POST', `/cases/${enc(id)}/knowledge-check`, body),

  // Risk engine (POST body keeps clinical parameters out of URLs and logs)
  assessCase: (caseId: number, body: CaseRiskAssessmentRequest) =>
    request<RiskAssessment>('POST', `/risk/cases/${enc(caseId)}/assess`, body),
  assessScenario: (body: RiskAssessmentRequest) => request<RiskAssessment>('POST', '/risk/assess', body),

  // Consent & sharing
  listConsents: () => request<ConsentGrant[]>('GET', '/consents'),
  createConsent: (body: ConsentGrantCreateRequest) => request<ConsentGrant>('POST', '/consents', body),
  approveConsent: (id: number) => request<ConsentGrant>('POST', `/consents/${enc(id)}/approve`),
  revokeConsent: (id: number) => request<ConsentGrant>('POST', `/consents/${enc(id)}/revoke`),
  createSharingRequest: (body: SharingInvitationRequest) => request<ConsentGrant>('POST', '/sharing/requests', body),
  getSharedCase: (caseId: number) => request<SharedCaseSummary>('GET', `/sharing/shared-cases/${enc(caseId)}`),

  // Counselling & referrals
  checkEscalation: (caseId: number) => request<string[]>('GET', `/counselling/escalations/check/${enc(caseId)}`),
  escalate: (body: EscalationRequest) => request<EscalationResult>('POST', '/counselling/escalations', body),
  listReferrals: () => request<ReferralTask[]>('GET', '/referrals'),
  getReferral: (id: number) => request<ReferralTask>('GET', `/referrals/${enc(id)}`),
  createReferral: (body: ReferralCreateRequest) => request<ReferralTask>('POST', '/referrals', body),
  updateReferralStatus: (id: number, status: ReferralStatus) =>
    request<ReferralTask>('PATCH', `/referrals/${enc(id)}/status`, { status }),
  addReferralNote: (id: number, note_text: string) =>
    request<CounsellorNote>('POST', `/referrals/${enc(id)}/notes`, { note_text }),

  // Clinician-only
  recordProvenance: (body: ClinicalProvenanceCreateRequest) =>
    request<ClinicalProvenance>('POST', '/clinical/provenance', body),
};
