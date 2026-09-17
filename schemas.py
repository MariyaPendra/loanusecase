"""Response models returned by the API."""

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ApplicationData(BaseModel):
    """Fields the LLM extracts from the loan application PDF."""

    applicant_name: Optional[str] = None
    age: Optional[Any] = None
    monthly_income: Optional[Any] = None
    loan_amount: Optional[Any] = None
    loan_purpose: Optional[str] = None
    co_applicant: Optional[Any] = None
    employment: Optional[Any] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    income_proof_present: Optional[bool] = None


class Assessment(BaseModel):
    risk_level: str = Field(..., examples=["LOW", "MEDIUM", "HIGH"])
    recommendation: str
    reason: str


class DocumentMeta(BaseModel):
    filename: str
    pages: int
    characters_extracted: int


class AnalysisResponse(BaseModel):
    """The structured brief handed to the relationship officer."""

    document: DocumentMeta
    application_data: ApplicationData
    summary: str
    risk_flags: List[str]
    assessment: Assessment


class ErrorResponse(BaseModel):
    detail: str
