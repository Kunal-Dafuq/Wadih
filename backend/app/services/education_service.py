from datetime import datetime, timezone
from typing import List, Dict
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.screening_case import ScreeningCase
from app.models.education import EducationalContent, EducationAssessment
from app.models.referral import ReferralTask
from app.schemas.education import (
    CaseExplanationResponse,
    TeachBackQuestion,
    TeachBackOption,
    ConditionGuideItem,
    KnowledgeCheckSubmission,
    KnowledgeCheckResultResponse,
    QuestionEvaluation,
)
from app.core.exceptions import NotFoundException, ValidationException

# Reviewed, standard teach-back questions for carrier screening comprehension
TEACH_BACK_BANK: Dict[int, Dict] = {
    1: {
        "prompt": "What does being a genetic carrier generally mean for your personal day-to-day health?",
        "options": [
            {"option_id": "A", "text": "I will develop symptoms of the genetic condition later in life."},
            {"option_id": "B", "text": "I carry one altered gene copy, but I am typically healthy and without symptoms."},
            {"option_id": "C", "text": "It means I cannot have healthy biological children."},
        ],
        "correct_option": "B",
        "explanation": "Carriers have one functional gene copy and one variant copy, generally causing no medical symptoms.",
    },
    2: {
        "prompt": "When does an autosomal recessive condition pose a 25% (1 in 4) risk to a future pregnancy?",
        "options": [
            {"option_id": "A", "text": "When only one biological parent is a carrier."},
            {"option_id": "B", "text": "When both biological parents are carriers for the SAME genetic condition."},
            {"option_id": "C", "text": "Autosomal recessive conditions never pass down to children."},
        ],
        "correct_option": "B",
        "explanation": "Autosomal recessive conditions only manifest when a child inherits altered copies from both parents.",
    },
    3: {
        "prompt": "What is the recommended next step after identifying carrier status for pre-conception planning?",
        "options": [
            {"option_id": "A", "text": "Facilitate partner carrier testing and discuss joint reproductive options with a counsellor."},
            {"option_id": "B", "text": "Schedule an immediate invasive medical procedure."},
            {"option_id": "C", "text": "Assume a future child will definitely have the condition."},
        ],
        "correct_option": "A",
        "explanation": "Partner testing and pre-conception counselling offer personalized clarity on joint reproductive risks.",
    },
}


class EducationService:
    @staticmethod
    def _validate_case_access(db: Session, case_id: int, user: User) -> ScreeningCase:
        case = db.query(ScreeningCase).filter(ScreeningCase.id == case_id).first()
        if not case:
            raise NotFoundException("Screening case not found.")

        # Check access permission
        is_owner = case.owner_user_id == user.id
        is_assigned_counsellor = False
        if user.role == UserRole.COUNSELLOR:
            is_assigned_counsellor = (
                db.query(ReferralTask)
                .filter(
                    ReferralTask.case_id == case_id,
                    ReferralTask.assigned_counsellor_id == user.id,
                )
                .first()
                is not None
            )

        if not is_owner and not is_assigned_counsellor:
            raise NotFoundException("Screening case not found.")

        return case

    @classmethod
    def get_case_explanation(
        cls, db: Session, case_id: int, user: User
    ) -> CaseExplanationResponse:
        """Retrieve reviewed educational content matching the case findings."""
        case = cls._validate_case_access(db, case_id, user)

        # Retrieve general carrier education content
        edu_content = (
            db.query(EducationalContent)
            .filter(
                EducationalContent.content_key == "AUTOSOMAL_RECESSIVE_CARRIER",
                EducationalContent.active == True,
            )
            .first()
        )

        title = edu_content.title if edu_content else "Understanding Carrier Screening"
        overview = (
            edu_content.body
            if edu_content
            else "Being a carrier means having one altered copy of a gene with no symptoms."
        )
        takeaways = (
            [line.strip() for line in edu_content.key_takeaways.split("\n") if line.strip()]
            if edu_content and edu_content.key_takeaways
            else [
                "Carriers are generally healthy.",
                "Risk occurs only if both partners carry changes in the same gene.",
                "Simulated educational demonstration.",
            ]
        )

        condition_guides = []
        for finding in case.findings:
            condition_guides.append(
                ConditionGuideItem(
                    condition_code=finding.condition_code,
                    condition_name=finding.condition_name,
                    carrier_state=finding.carrier_state,
                    inheritance_mode=finding.inheritance_mode,
                    educational_summary=finding.summary_text
                    or "Educational carrier summary reviewed by clinical team.",
                )
            )

        questions = [
            TeachBackQuestion(
                question_id=qid,
                prompt=qdata["prompt"],
                options=[TeachBackOption(**opt) for opt in qdata["options"]],
            )
            for qid, qdata in TEACH_BACK_BANK.items()
        ]

        return CaseExplanationResponse(
            case_id=case.id,
            case_code=case.synthetic_case_code,
            title=title,
            overview_body=overview,
            key_takeaways=takeaways,
            condition_guides=condition_guides,
            limitations_disclaimer=(
                "Limitations & Responsible Use: This content is educational demonstration material only. "
                "It does not provide clinical diagnostic interpretation or personalized reproductive prescriptions. "
                "Consult a licensed genetic counsellor for real-world medical care."
            ),
            approved_by_role="GENETIC_COUNSELLOR",
            content_version=edu_content.version if edu_content else "1.0",
            teach_back_questions=questions,
        )

    @classmethod
    def evaluate_knowledge_check(
        cls, db: Session, case_id: int, user: User, submission: KnowledgeCheckSubmission
    ) -> KnowledgeCheckResultResponse:
        """Evaluate participant answers, calculate score, and record assessment attempt."""
        case = cls._validate_case_access(db, case_id, user)

        evaluations: List[QuestionEvaluation] = []
        correct_count = 0

        submitted_answers = {a.question_id: a.selected_option_id.upper() for a in submission.answers}

        for qid, qdata in TEACH_BACK_BANK.items():
            selected = submitted_answers.get(qid)
            if not selected:
                raise ValidationException(f"Missing answer for question {qid}.")

            is_correct = selected == qdata["correct_option"]
            if is_correct:
                correct_count += 1

            evaluations.append(
                QuestionEvaluation(
                    question_id=qid,
                    selected_option_id=selected,
                    is_correct=is_correct,
                    explanation=qdata["explanation"],
                )
            )

        total_questions = len(TEACH_BACK_BANK)
        passed = correct_count >= 2  # passing threshold: at least 2 of 3 correct

        # Update or record assessment attempt
        existing_assessment = (
            db.query(EducationAssessment)
            .filter(
                EducationAssessment.case_id == case.id,
                EducationAssessment.user_id == user.id,
            )
            .first()
        )

        now = datetime.now(timezone.utc)
        if existing_assessment:
            existing_assessment.score = correct_count
            existing_assessment.total_questions = total_questions
            existing_assessment.passed = passed
            existing_assessment.attempt_count += 1
            existing_assessment.completed_at = now
            attempt_num = existing_assessment.attempt_count
        else:
            new_assessment = EducationAssessment(
                user_id=user.id,
                case_id=case.id,
                content_version="1.0",
                score=correct_count,
                total_questions=total_questions,
                attempt_count=1,
                passed=passed,
                completed_at=now,
            )
            db.add(new_assessment)
            attempt_num = 1

        db.commit()

        if passed:
            feedback = "Great work! You have demonstrated a clear understanding of your screening result."
        else:
            feedback = "You scored below the passing threshold. Review the explanations above or request a counselling follow-up."

        return KnowledgeCheckResultResponse(
            score=correct_count,
            total_questions=total_questions,
            passed=passed,
            attempt_count=attempt_num,
            evaluations=evaluations,
            feedback_message=feedback,
            completed_at=now,
        )
