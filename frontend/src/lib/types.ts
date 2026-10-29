/**
 * Response/request shapes mirrored from the backend Pydantic schemas
 * (backend/app/schemas/*.py on feature/niharika-advanced-backend) and
 * docs/API_CONTRACT_NIHARIKA.md. Keep field names identical to the API.
 */

export type Role = 'patient' | 'counsellor' | 'admin';

export interface CurrentUser {
  id: number;
  email: string;
  role: Role | string;
  is_active: boolean;
  display_name: string | null;
  preferred_language: string;
  literacy_mode: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: CurrentUser;
}

// ---------------------------------------------------------------- cases

export interface SyntheticFinding {
  id: number;
  condition_code: string;
  condition_name: string;
  carrier_state: string;
  inheritance_mode: string;
  classification_state: string;
  reviewed_flag: boolean;
  summary_text: string | null;
}

export interface ScreeningCaseListItem {
  id: number;
  synthetic_case_code: string;
  status: string;
  screening_scope_label: string;
  source_reviewed: boolean;
  findings_count: number;
  created_at: string;
}

export interface ScreeningCaseDetail {
  id: number;
  synthetic_case_code: string;
  status: string;
  screening_scope_label: string;
  source_reviewed: boolean;
  created_at: string;
  findings: SyntheticFinding[];
  educational_disclaimer: string;
}

// ------------------------------------------------------------ education

export interface TeachBackOption {
  option_id: string;
  text: string;
}

export interface TeachBackQuestion {
  question_id: number;
  prompt: string;
  options: TeachBackOption[];
}

export interface ConditionGuideItem {
  condition_code: string;
  condition_name: string;
  carrier_state: string;
  inheritance_mode: string;
  educational_summary: string;
}

export interface CaseExplanation {
  case_id: number;
  case_code: string;
  title: string;
  overview_body: string;
  key_takeaways: string[];
  condition_guides: ConditionGuideItem[];
  limitations_disclaimer: string;
  approved_by_role: string;
  content_version: string;
  teach_back_questions: TeachBackQuestion[];
}

export interface KnowledgeCheckSubmission {
  answers: { question_id: number; selected_option_id: string }[];
}

export interface KnowledgeCheckResult {
  score: number;
  total_questions: number;
  passed: boolean;
  attempt_count: number;
  evaluations: { question_id: number; selected_option_id: string; is_correct: boolean; explanation: string }[];
  feedback_message: string;
  completed_at: string;
}

// ----------------------------------------------------------------- risk

export const INHERITANCE_PATTERNS = [
  'AUTOSOMAL_RECESSIVE',
  'AUTOSOMAL_DOMINANT',
  'X_LINKED_RECESSIVE',
  'X_LINKED_DOMINANT',
  'MITOCHONDRIAL',
  'MULTIFACTORIAL',
  'UNKNOWN',
] as const;
export type InheritancePattern = (typeof INHERITANCE_PATTERNS)[number];

export const SCREENING_INTERPRETATIONS = [
  'CARRIER_DETECTED',
  'NO_VARIANT_DETECTED',
  'UNCERTAIN_SIGNIFICANCE',
  'POSITIVE_AFFECTED',
  'NOT_PERFORMED',
  'INCONCLUSIVE',
] as const;
export type ScreeningInterpretation = (typeof SCREENING_INTERPRETATIONS)[number];

export type AssessmentStatus =
  | 'EDUCATIONAL_RESULT'
  | 'REVIEW_REQUIRED'
  | 'INSUFFICIENT_DATA'
  | 'UNSUPPORTED_INHERITANCE_PATTERN';

export interface RiskEstimate {
  affected_probability: number | null;
  carrier_probability: number | null;
  unaffected_non_carrier_probability: number | null;
  residual_carrier_probability_used: number | null;
  summary_label: string;
  recurrence_note: string;
}

export interface RiskAssessment {
  case_id: string | null;
  condition: string;
  condition_code: string;
  gene: string | null;
  inheritance_pattern: InheritancePattern;
  assessment_status: AssessmentStatus;
  risk_estimate: RiskEstimate | null;
  residual_risk_source: string | null;
  explanation: string;
  limitations: string[];
  assumptions: string[];
  requires_genetic_counselor: boolean;
  referral_reason: string | null;
  rule_version: string;
  is_educational_simulation?: boolean;
  is_case_linked_assessment?: boolean;
  is_authoritative_clinical_record?: boolean;
  is_synthetic_sandbox?: boolean;
  clinician_confirmed_provenance?: boolean;
  disclaimer: string;
}

export interface CaseRiskAssessmentRequest {
  condition_code: string;
  partner_case_id?: number | null;
}

export interface RiskAssessmentRequest {
  case_id?: string | null;
  condition_code: string;
  condition_name: string;
  gene_symbol?: string | null;
  inheritance_pattern: InheritancePattern;
  partner_1_finding: ScreeningInterpretation;
  partner_2_finding?: ScreeningInterpretation | null;
  findings_sufficient?: boolean;
  is_clinician_reviewed?: boolean;
}

// -------------------------------------------------------------- consent

export type ConsentScope = 'carrier_status_only' | 'summary_only' | 'full_report';
export type ConsentStatus = 'PENDING' | 'GRANTED' | 'REVOKED' | 'EXPIRED';

export interface ConsentGrant {
  id: number;
  granter_user_id: number;
  granter_name: string;
  grantee_user_id: number;
  grantee_name: string;
  scope: ConsentScope | string;
  status: ConsentStatus | string;
  purpose: string | null;
  terms_version: string | null;
  case_id: number | null;
  created_at: string;
  expires_at: string | null;
  revoked_at: string | null;
}

export interface ConsentGrantCreateRequest {
  grantee_email: string;
  scope: ConsentScope;
  purpose: string;
  case_id: number | null;
  terms_version: string;
  expires_in_days: number | null;
}

export interface SharingInvitationRequest {
  partner_email: string;
  scope: ConsentScope;
  purpose: string;
  case_id: number | null;
}

export interface SharedFinding {
  condition_code: string;
  condition_name: string;
  carrier_state: string;
  inheritance_mode: string;
  classification_state: string | null;
  reviewed_flag: boolean | null;
  summary_text: string | null;
}

export interface SharedCaseSummary {
  case_id: number;
  synthetic_case_code: string;
  granted_scope: string;
  owner_display_name: string;
  status: string;
  findings: SharedFinding[];
  privacy_notice: string;
}

// ---------------------------------------------------- counselling/referral

export const ESCALATION_TRIGGERS = [
  'VARIANT_OF_UNCERTAIN_SIGNIFICANCE',
  'UNSUPPORTED_INHERITANCE_PATTERN',
  'DUAL_CARRIER_AUTOSOMAL_RECESSIVE',
  'AFFECTED_PARTNER_CLINICAL_REVIEW',
  'INCOMPLETE_OR_CONFLICTING_FINDINGS',
  'CLINICIAN_REVIEW_REQUIRED',
] as const;
export type EscalationTrigger = (typeof ESCALATION_TRIGGERS)[number];

export type UrgencyLevel = 'ROUTINE' | 'PRIORITY' | 'URGENT';

export interface EscalationRequest {
  case_id: number;
  trigger_reason: EscalationTrigger;
  urgency_level: UrgencyLevel;
  clinical_rationale?: string | null;
}

export interface EscalationResult {
  referral_id: number;
  case_id: number;
  synthetic_case_code: string;
  participant_user_id: number;
  status: string;
  urgency_level: string;
  trigger_reason: string;
  assigned_counsellor_name: string | null;
  guidance_note: string;
  created_at: string;
}

export type ReferralStatus = 'PENDING' | 'SCHEDULED' | 'COMPLETED' | 'CANCELLED';

export interface CounsellorNote {
  id: number;
  referral_id: number;
  author_user_id: number;
  author_name: string;
  note_text: string;
  created_at: string;
}

export interface ReferralTask {
  id: number;
  participant_user_id: number;
  case_id: number;
  case_code: string;
  assigned_counsellor_id: number | null;
  assigned_counsellor_name: string | null;
  reason_code: string;
  status: ReferralStatus | string;
  urgency_level: string;
  created_at: string;
  updated_at: string;
  notes: CounsellorNote[];
  service_disclaimer: string;
}

export interface ReferralCreateRequest {
  case_id: number;
  reason_code: string;
  urgency_level: UrgencyLevel;
}

export interface ClinicalProvenanceCreateRequest {
  case_id: number;
  condition_code: string;
  residual_carrier_probability: number;
  clinical_source_reference: string;
  notes?: string | null;
}

export interface ClinicalProvenance {
  id: number;
  case_id: number;
  condition_code: string;
  residual_carrier_probability: number;
  clinical_source_reference: string;
  reviewing_clinician_id: number;
  notes: string | null;
  is_active: boolean;
  reviewed_at: string;
  created_at: string;
}
