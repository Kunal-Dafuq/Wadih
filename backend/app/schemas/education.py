from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class TeachBackOption(BaseModel):
    option_id: str
    text: str


class TeachBackQuestion(BaseModel):
    question_id: int
    prompt: str
    options: List[TeachBackOption]


class ConditionGuideItem(BaseModel):
    condition_code: str
    condition_name: str
    carrier_state: str
    inheritance_mode: str
    educational_summary: str


class CaseExplanationResponse(BaseModel):
    case_id: int
    case_code: str
    title: str
    overview_body: str
    key_takeaways: List[str]
    condition_guides: List[ConditionGuideItem]
    limitations_disclaimer: str
    approved_by_role: str
    content_version: str
    teach_back_questions: List[TeachBackQuestion]


class AnswerSubmission(BaseModel):
    question_id: int
    selected_option_id: str = Field(..., max_length=5)


class KnowledgeCheckSubmission(BaseModel):
    answers: List[AnswerSubmission] = Field(..., min_length=1)


class QuestionEvaluation(BaseModel):
    question_id: int
    selected_option_id: str
    is_correct: bool
    explanation: str


class KnowledgeCheckResultResponse(BaseModel):
    score: int
    total_questions: int
    passed: bool
    attempt_count: int
    evaluations: List[QuestionEvaluation]
    feedback_message: str
    completed_at: datetime

    model_config = ConfigDict(from_attributes=True)
