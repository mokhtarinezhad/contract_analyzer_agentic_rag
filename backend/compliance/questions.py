"""
Re-exports from eao_questions.py for backward compatibility.

The active question bank is now the ESA (Employment Standards Act of Ontario)
question bank defined in eao_questions.py.
"""

from backend.compliance.eao_questions import (  # noqa: F401
    SubCriterion,
    ESAComplianceQuestion as ComplianceQuestion,
    ESA_COMPLIANCE_QUESTIONS as COMPLIANCE_QUESTIONS,
    get_question_by_id,
    get_all_question_ids,
    get_all_questions,
    get_always_applicable_questions,
    get_conditional_questions,
)
