# Wadih API Contract — Niharika's Advanced Backend
**Author:** Niharika Singh (Advanced Backend Owner)  
**Intended Consumer:** Saiesha (Frontend & UX Lead)  
**Base URL:** `/api/v1`  
**Authentication Scheme:** `Authorization: Bearer <JWT_ACCESS_TOKEN>`

---

## 1. Overview & UI State Machine

This contract outlines the endpoints, request/response models, state enums, error envelopes, and privacy boundaries for:
1. **Deterministic Genetic-Risk Engine**
2. **Granular Consent Management & Partner Sharing**
3. **Counsellor Escalations**
4. **Security Audit Log Inspection**

### Frontend UI State Handling
For risk assessment and shared case views, Saiesha's UI should account for the following response states (`assessment_status`):

| `assessment_status` | Meaning | UI Presentation Guidance |
|---|---|---|
| `EDUCATIONAL_RESULT` | Valid calculated Mendelian outcome | Display probability visualizer (e.g. 25% affected, 50% carrier, 25% non-carrier for dual carrier; or residual-only risk banner). Display visible limitations and recurrence notes. |
| `REVIEW_REQUIRED` | VUS, unreviewed finding, or affected partner | Suppress numeric percentage visualizer. Display an educational amber banner stating: *"Genetic Counsellor Review Required"*. Provide a 1-click button to escalate to simulated counselling. |
| `INSUFFICIENT_DATA` | Single carrier with untested partner or missing data | Display educational carrier card. Do not show couple-level risk. Show recommendation: *"Invite partner to link results for joint pre-conception assessment"*. |
| `UNSUPPORTED_INHERITANCE_PATTERN` | Non-recessive mode (Dominant, X-Linked, etc.) | Informational notice that deterministic calculator only models autosomal recessive conditions. Provide counselling referral action. |

---

## 2. Endpoints Contract

### 2.1 Deterministic Genetic Risk Engine

#### `POST /api/v1/risk/assess`
Calculates deterministic recurrence risk and explanations for structured partner findings.

- **Auth Required:** Yes (`Bearer <token>`)
- **Request Body (`RiskAssessmentRequest`):**
```json
{
  "case_id": "SYN-CASE-101",
  "condition_code": "HBB_BETA_THAL",
  "condition_name": "Beta Thalassemia",
  "gene_symbol": "HBB",
  "inheritance_pattern": "AUTOSOMAL_RECESSIVE",
  "partner_1_finding": "CARRIER_DETECTED",
  "partner_2_finding": "CARRIER_DETECTED",
  "partner_1_residual_carrier_probability": null,
  "partner_2_residual_carrier_probability": null,
  "findings_sufficient": true,
  "is_clinician_reviewed": true
}
```
*Enum Values:*
- `inheritance_pattern`: `"AUTOSOMAL_RECESSIVE"`, `"AUTOSOMAL_DOMINANT"`, `"X_LINKED_RECESSIVE"`, `"X_LINKED_DOMINANT"`, `"MITOCHONDRIAL"`, `"MULTIFACTORIAL"`, `"UNKNOWN"`
- `partner_1_finding` / `partner_2_finding`: `"CARRIER_DETECTED"`, `"NO_VARIANT_DETECTED"`, `"UNCERTAIN_SIGNIFICANCE"`, `"POSITIVE_AFFECTED"`, `"NOT_PERFORMED"`, `"INCONCLUSIVE"`
- `partner_1_residual_carrier_probability` / `partner_2_residual_carrier_probability` (float, optional): Validated condition-specific residual carrier probability `r` (strictly `0.0 < r < 1.0`). Must only be supplied for a partner whose finding is `NO_VARIANT_DETECTED`.

*Clinical Risk Calculation Rules:*
- **Dual Carriers (`CARRIER_DETECTED` + `CARRIER_DETECTED`):** Standard 25% affected, 50% carrier, 25% non-carrier per pregnancy.
- **Single Carrier + Confirmed Negative Partner (`CARRIER_DETECTED` + `NO_VARIANT_DETECTED`):**
  - If validated laboratory residual carrier probability `r` is provided: `P(affected child) = r × 1/4`, `P(carrier) = 0.50`, `P(unaffected non-carrier) = 0.50 - 0.25 × r`.
  - If residual carrier probability `r` is NOT provided: Returns `INSUFFICIENT_DATA` with `risk_estimate = null` (no fabricated numbers or false zero-risk claims).
- **Both Negative (`NO_VARIANT_DETECTED` + `NO_VARIANT_DETECTED`):** Returns `EDUCATIONAL_RESULT` with `risk_estimate = null` (strictly prevents false 0.0% zero-risk claims since testing panels cannot rule out rare or deep-intronic variants).

- **Response Body (`RiskAssessmentResponse`):**
```json
{
  "case_id": "SYN-CASE-101",
  "condition": "Beta Thalassemia",
  "condition_code": "HBB_BETA_THAL",
  "gene": "HBB",
  "inheritance_pattern": "AUTOSOMAL_RECESSIVE",
  "assessment_status": "EDUCATIONAL_RESULT",
  "risk_estimate": {
    "affected_probability": 0.25,
    "carrier_probability": 0.50,
    "unaffected_non_carrier_probability": 0.25,
    "residual_carrier_probability_used": null,
    "summary_label": "25% Affected, 50% Carrier, 25% Unaffected Non-Carrier per pregnancy",
    "recurrence_note": "Each pregnancy is an independent event with a 25% (1 in 4) chance of having the condition. Prior pregnancy outcomes do not influence future pregnancies."
  },
  "explanation": "Both biological parents are confirmed carriers...",
  "limitations": [
    "Carrier screening evaluates a defined panel of synthetic pathogenic variants...",
    "Calculations reflect statistical probabilities for each separate pregnancy..."
  ],
  "assumptions": [
    "Inheritance mode is confirmed Autosomal Recessive.",
    "Both reproductive partners are the biological parents of the prospective pregnancy."
  ],
  "requires_genetic_counselor": true,
  "referral_reason": "DUAL_CARRIER_AUTOSOMAL_RECESSIVE",
  "rule_version": "v1.0.0-ar-deterministic",
  "disclaimer": "Educational and demonstration assessment only..."
}
```

---

#### `POST /api/v1/risk/cases/{case_id}/assess` *(Recommended & Privacy-Hardened)*
Evaluates reproductive risk directly from stored screening findings using a validated request body.

- **Auth Required:** Yes (`Bearer <token>`)
- **Privacy Justification:**
  Clinical parameters (condition code, partner case ID, residual carrier probabilities) are submitted in the HTTP POST body rather than URL query parameters. This eliminates sensitive health data leakage into reverse-proxy logs (Nginx, ALB), browser histories, and APM logging pipelines.
- **Request Body (`CaseRiskAssessmentRequest`):**
```json
{
  "condition_code": "HBB_BETA_THAL",
  "partner_case_id": 2,
  "partner_residual_carrier_probability": 0.01
}
```
*Server-Controlled Clinical Provenance Policy:*
- **Zero Client Trust for Provenance**: A client cannot manufacture clinical provenance by setting a boolean flag or providing a free-text source string. Any client-supplied residual carrier probability is strictly verified against an authoritative, persisted `ClinicalResidualRiskRecord`.
- **Authoritative Provenance Lookup**: The server queries the database for an active `ClinicalResidualRiskRecord` matching the negative partner's case ID and condition code, signed off by an authorized genetic counsellor or clinical administrator.
- If no valid clinical record exists (or if client inputs contradict the clinician's record), the engine returns `REVIEW_REQUIRED` (`UNVERIFIED_RESIDUAL_RISK_PROVENANCE`) with `risk_estimate = null`.
- When an active clinician-reviewed record exists, the server utilizes the verified probability and laboratory source reference, returning `EDUCATIONAL_RESULT` with $P(\text{affected}) = r \times 1/4$.
- **Access Control:**
  - If `partner_case_id` is supplied, partner must have granted an active `GRANTED` consent grant to the calling user.
  - Returns `403 CONSENT_REQUIRED` if partner consent is missing, expired, or revoked.

---

#### `GET /api/v1/risk/cases/{case_id}` *(DEPRECATED - Legacy GET Compatibility)*
- **Status:** **DEPRECATED**. Preserved for backward compatibility with existing GET integrations.
- **Security Warning:** Query parameters are visible in HTTP access logs and browser histories. Clients should migrate to `POST /api/v1/risk/cases/{case_id}/assess`.
- **Provenance Gate**: The legacy GET endpoint enforces the exact same server-controlled provenance check. Client query parameters cannot bypass server-side verification.
- **Query Parameters:**
  - `condition_code` (string, required): e.g. `HBB_BETA_THAL`
  - `partner_case_id` (integer, optional): Case ID of partner's screening report.
  - `partner_residual_carrier_probability` (float, optional): Proposed residual carrier risk (requires matching server record).

---

#### `POST /api/v1/clinical/provenance` *(Clinician / Admin Only)*
Records an authoritative, clinician-reviewed residual-risk assessment for a negative-screening case finding.

- **Auth Required:** Yes (`role` must be `COUNSELLOR` or `ADMIN`; patients receive `403 FORBIDDEN`).
- **Object-Level Authorization Rules for Counsellors:**
  - An authenticated, active `COUNSELLOR` must be assigned to manage the target screening case directly (via `ReferralTask`), OR be assigned to an active referral for a partner participant who holds an active, unrevoked, unexpired `ConsentGrant` with the target case owner.
  - Unassigned counsellors or counsellors lacking an authorized couple relationship receive `403 FORBIDDEN`.
  - Administrative accounts (`ADMIN`) retain documented operational ingestion authority.
- **Request Body (`ClinicalProvenanceCreateRequest`):**
```json
{
  "case_id": 2,
  "condition_code": "HBB_BETA_THAL",
  "residual_carrier_probability": 0.01,
  "clinical_source_reference": "LabCorp Expanded Carrier Screen v3 (99% detection rate)",
  "notes": "Verified against clinician-reviewed synthetic laboratory report."
}
```
- **Response Body (`ClinicalProvenanceResponse`):**
```json
{
  "id": 1,
  "case_id": 2,
  "condition_code": "HBB_BETA_THAL",
  "residual_carrier_probability": 0.01,
  "clinical_source_reference": "LabCorp Expanded Carrier Screen v3 (99% detection rate)",
  "reviewing_clinician_id": 3,
  "notes": "Verified against clinician-reviewed synthetic laboratory report.",
  "is_active": true,
  "reviewed_at": "2026-10-28T19:30:00Z",
  "created_at": "2026-10-28T19:30:00Z"
}
```

---

### 2.2 Consent Management & Partner Sharing

#### `POST /api/v1/consents`
Directly issues a scoped consent grant to a partner.

- **Auth Required:** Yes
- **Request Body:**
```json
{
  "grantee_user_id": 2,
  "scope": "summary_only",
  "purpose": "preconception_carrier_screening",
  "case_id": 1,
  "terms_version": "v1.0",
  "expires_in_days": 30
}
```
*Allowed Scopes:*
- `"carrier_status_only"`: Redacts detailed finding summaries; reveals only whether carrier state is detected for each condition.
- `"summary_only"`: Permits high-level carrier summaries and condition education.
- `"full_report"`: Permits complete synthetic clinical report disclosure.

- **Response Body (`ConsentGrantResponse`):**
```json
{
  "id": 1,
  "granter_user_id": 1,
  "granter_name": "Patient A (Carrier)",
  "grantee_user_id": 2,
  "grantee_name": "Patient B (Partner)",
  "scope": "summary_only",
  "status": "GRANTED",
  "purpose": "preconception_carrier_screening",
  "terms_version": "v1.0",
  "case_id": 1,
  "created_at": "2026-10-28T18:30:00Z",
  "expires_at": "2026-11-27T18:30:00Z",
  "revoked_at": null
}
```

---

#### `POST /api/v1/consents/{consent_id}/revoke`
Revokes a previously granted consent. Immediately blocks all future partner reads covered by this permission.

- **Auth Required:** Yes (must be the granting participant)
- **Response:** Updated `ConsentGrantResponse` with `status: "REVOKED"` and `revoked_at` timestamp.

---

#### `POST /api/v1/sharing/requests`
Creates a partner invitation request.

- **Auth Required:** Yes
- **Request Body:**
```json
{
  "partner_email": "patient.b@wadih.demo",
  "scope": "summary_only",
  "purpose": "preconception_carrier_screening",
  "case_id": 1
}
```
- **Response:** Creates a `ConsentGrantResponse` with `status: "PENDING"`.
- *Note for Frontend:* An invitation does NOT grant immediate access to findings until approved.

---

#### `GET /api/v1/sharing/shared-cases/{case_id}`
Retrieves a partner's screening findings under active, granted consent.

- **Auth Required:** Yes (caller must be grantee of an active consent grant from the case owner)
- **Response Body (`SharedCaseSummaryResponse`):**
```json
{
  "case_id": 1,
  "synthetic_case_code": "SYN-CASE-101",
  "granted_scope": "summary_only",
  "owner_display_name": "Patient A (Carrier)",
  "status": "ready",
  "findings": [
    {
      "condition_code": "HBB_BETA_THAL",
      "condition_name": "Beta Thalassemia",
      "carrier_state": "CARRIER_DETECTED",
      "inheritance_mode": "AUTOSOMAL_RECESSIVE",
      "summary_text": "Synthetic demonstration carrier finding: Heterozygous pathogenic variant in HBB gene."
    }
  ],
  "privacy_notice": "Shared view authorized under recipient consent grant..."
}
```
- **Errors Handled:**
  - `404 NOT_FOUND`: If caller has no consent grant (privacy-preserving IDOR prevention).
  - `403 CONSENT_REQUIRED`: If consent is `PENDING`, `REVOKED`, or `EXPIRED`.

---

### 2.3 Clinical Escalation to Counselling

#### `POST /api/v1/counselling/escalations`
Creates a simulated counselling referral task for cases with VUS, dual carrier, or unreviewed findings.

- **Auth Required:** Yes (must be owner of the screening case)
- **Request Body:**
```json
{
  "case_id": 1,
  "trigger_reason": "VARIANT_OF_UNCERTAIN_SIGNIFICANCE",
  "urgency_level": "PRIORITY",
  "clinical_rationale": "Participant requests clarification regarding ambiguous finding."
}
```
*Supported Triggers:*
- `"VARIANT_OF_UNCERTAIN_SIGNIFICANCE"`
- `"UNSUPPORTED_INHERITANCE_PATTERN"`
- `"DUAL_CARRIER_AUTOSOMAL_RECESSIVE"`
- `"AFFECTED_PARTNER_CLINICAL_REVIEW"`
- `"INCOMPLETE_OR_CONFLICTING_FINDINGS"`
- `"CLINICIAN_REVIEW_REQUIRED"`

- **Response Body (`EscalationResultResponse`):**
```json
{
  "referral_id": 1,
  "case_id": 1,
  "synthetic_case_code": "SYN-CASE-101",
  "participant_user_id": 1,
  "status": "PENDING",
  "urgency_level": "PRIORITY",
  "trigger_reason": "VARIANT_OF_UNCERTAIN_SIGNIFICANCE",
  "assigned_counsellor_name": "Dr. Sarah Chen, MS CGC",
  "guidance_note": "Educational genetic counselling referral initiated...",
  "created_at": "2026-10-28T18:30:00Z"
}
```

---

### 2.4 Audit Logging & Immutability Guarantees

#### `GET /api/v1/audit/events`
- **Auth Required:** Yes (`role` must be `ADMIN` or `COUNSELLOR`)
- **Query Params:** `action`, `resource_type`, `skip`, `limit`
- **Least-Privilege Scoping:**
  - **Patients**: Denied with `403 FORBIDDEN` (and logged under `PRIVILEGED_ACCESS_ATTEMPT`).
  - **Counsellors**: Strictly scoped to events belonging to assigned screening cases, assigned referral tasks, or actions performed by the counsellor themself. Unrelated cases or general account actions performed by assigned participants are strictly filtered out.
  - **Admins**: Full platform audit visibility.
- **Audit Log Immutability & Boundaries:**
  - **Application/API Layer:** No endpoints exist to modify, update, or delete audit records.
  - **ORM Object Layer:** Enforced via SQLAlchemy lifecycle listeners (`before_update` and `before_delete`) on the `AuditLog` mapper, preventing modification or deletion of individual instances.
  - **ORM Bulk Layer:** Enforced via `SessionEvents.do_orm_execute` guard on `Session`, actively intercepting and rejecting bulk `update(AuditLog)` and `delete(AuditLog)` DML statements.
  - **Database Storage Reality:** Application and ORM layer enforcement prevents all code and services from tampering with audit records. However, physical database immutability against direct SQL execution by database administrators or superusers requires database-level privilege revocation (`REVOKE UPDATE, DELETE ON shared_audit_logs`) or cloud WORM storage (e.g. AWS CloudTrail Object Lock or GCP Audit Logs). We do not claim tamper-proof physical storage.

---

## 3. Standard Error Envelope

All API errors return the unified envelope:
```json
{
  "error": {
    "code": "CONSENT_REQUIRED",
    "message": "Access denied: Consent has been revoked by the granting participant.",
    "request_id": "req_8f10f56a"
  }
}
```
Standard codes: `UNAUTHENTICATED` (401), `FORBIDDEN` (403), `CONSENT_REQUIRED` (403), `NEEDS_CLINICIAN_REVIEW` (403), `NOT_FOUND` (404), `VALIDATION_ERROR` (422), `INTERNAL_ERROR` (500).
