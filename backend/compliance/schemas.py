"""
Pydantic v2 output schemas for compliance analysis results.
Every agent output and API response is validated against these models.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class ComplianceState(str, Enum):
    FULLY_COMPLIANT = "Fully Compliant"
    PARTIALLY_COMPLIANT = "Partially Compliant"
    NON_COMPLIANT = "Non-Compliant"
    UNABLE_TO_DETERMINE = "Unable to Determine"


class EvaluatorVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PASS_WITH_FLAGS = "PASS_WITH_FLAGS"


# ─────────────────────────────────────────────
# Sub-models
# ─────────────────────────────────────────────

class RelevantQuote(BaseModel):
    text: str = Field(..., description="Verbatim text extracted from the contract")
    section_reference: str = Field(..., description="Section or exhibit reference, e.g. 'Section 6.6'")
    page_number: Optional[int] = Field(None, description="Page number in the source PDF")

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Quote text cannot be empty")
        return v.strip()


class SubCriterionResult(BaseModel):
    criterion_id: str
    description: str
    found: bool = Field(..., description="Whether evidence was found for this sub-criterion")
    evidence_summary: str = Field(..., description="Brief summary of evidence or lack thereof")


class EvaluatorAssessment(BaseModel):
    verdict: EvaluatorVerdict
    issues: List[str] = Field(default_factory=list)
    hallucination_flags: List[str] = Field(
        default_factory=list,
        description="Quotes that could not be verified against source chunks",
    )
    confidence_adjustment: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description="Adjustment applied to confidence score by evaluator",
    )
    critique: str = Field(default="", description="Evaluator's free-text critique")


class ProcessingMetadata(BaseModel):
    trace_id: str
    total_duration_ms: float
    pdf_parse_duration_ms: float
    embedding_duration_ms: float
    retrieval_duration_ms: float
    llm_duration_ms: float
    evaluation_duration_ms: float
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    retry_count: int = 0
    model_used: str
    chunks_retrieved_per_question: int = 0


# ─────────────────────────────────────────────
# Core compliance result
# ─────────────────────────────────────────────

class ComplianceResult(BaseModel):
    question_id: int = Field(..., ge=1, le=5)
    question_title: str
    compliance_question: str = Field(..., description="Full question text from the spec")
    compliance_state: ComplianceState
    confidence: float = Field(..., ge=0.0, le=1.0, description="Calibrated confidence 0–1")
    relevant_quotes: List[RelevantQuote] = Field(default_factory=list)
    rationale: str = Field(..., description="Reasoning referencing specific contract language")
    sub_criteria_results: List[SubCriterionResult] = Field(default_factory=list)
    evaluator_assessment: Optional[EvaluatorAssessment] = None
    retry_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def confidence_matches_state(self) -> "ComplianceResult":
        if self.compliance_state == ComplianceState.FULLY_COMPLIANT and self.confidence < 0.5:
            raise ValueError(
                "Fully Compliant state requires confidence >= 0.5"
            )
        return self

    @property
    def confidence_pct(self) -> str:
        return f"{self.confidence * 100:.0f}%"

    @property
    def sub_criteria_coverage(self) -> float:
        if not self.sub_criteria_results:
            return 0.0
        found = sum(1 for sc in self.sub_criteria_results if sc.found)
        return found / len(self.sub_criteria_results)


# ─────────────────────────────────────────────
# Full analysis response
# ─────────────────────────────────────────────

class ContractAnalysisResponse(BaseModel):
    contract_id: str = Field(..., description="Unique ID for this analysis run")
    trace_id: str
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    filename: str
    results: List[ComplianceResult] = Field(
        ...,
        description="Exactly 5 compliance results, one per question",
    )
    processing_metadata: ProcessingMetadata

    @field_validator("results")
    @classmethod
    def must_have_five_results(cls, v: List[ComplianceResult]) -> List[ComplianceResult]:
        if len(v) != 5:
            raise ValueError(f"Expected exactly 5 compliance results, got {len(v)}")
        return v

    @property
    def overall_compliance_summary(self) -> dict:
        from collections import Counter
        counts = Counter(r.compliance_state.value for r in self.results)
        return dict(counts)

    @property
    def average_confidence(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.confidence for r in self.results) / len(self.results)


# ─────────────────────────────────────────────
# Async job tracking (for API polling)
# ─────────────────────────────────────────────

class JobStatus(str, Enum):
    PENDING     = "pending"
    PARSING_PDF = "parsing_pdf"
    CHUNKING    = "chunking"
    EMBEDDING   = "embedding"
    INDEXING    = "indexing"
    RETRIEVING  = "retrieving"
    ANALYZING   = "analyzing"
    EVALUATING  = "evaluating"
    COMPLETED   = "completed"
    FAILED      = "failed"


class AnalysisJob(BaseModel):
    job_id: str
    trace_id: str
    status: JobStatus = JobStatus.PENDING
    filename: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    progress_pct: int = Field(default=0, ge=0, le=100)
    current_step: str = ""
    error_message: Optional[str] = None
    result: Optional[ContractAnalysisResponse] = None


# ─────────────────────────────────────────────
# Chat (bonus feature)
# ─────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    contract_id: str
    message: str
    history: List[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    sources: List[RelevantQuote] = Field(default_factory=list)
    trace_id: str
