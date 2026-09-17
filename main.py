"""
Loan Application Summarisation & Risk Flag Agent — FastAPI service.

Run:
    uvicorn main:app --reload

Then open http://127.0.0.1:8000 for the upload page,
or http://127.0.0.1:8000/docs for the interactive API docs.
"""

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import llm_service
import risk_rules
from config import settings
from pdf_utils import PDFExtractionError, extract_text_from_bytes
from schemas import AnalysisResponse

BASE_DIR = Path(__file__).parent

app = FastAPI(
    title="Loan Application Summarisation & Risk Flag Agent",
    description=(
        "Upload a loan application PDF. The service extracts key fields, "
        "writes a summary for the relationship officer, and flags risk "
        "signals for human review."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten this before any real deployment.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Pages and health
# ------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/health", tags=["system"])
def health():
    return {
        "status": "ok",
        "model": settings.MODEL,
        "groq_key_loaded": bool(settings.GROQ_API_KEY),
    }


# ------------------------------------------------------------------
# Main endpoint
# ------------------------------------------------------------------

async def _read_pdf_upload(file: UploadFile) -> bytes:
    """Validate the upload and return its bytes."""
    filename = file.filename or ""

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Upload a PDF file. Other formats are not supported.",
        )

    contents = await file.read()

    if not contents:
        raise HTTPException(
            status_code=400, detail="The uploaded file is empty."
        )

    if len(contents) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File is larger than {settings.MAX_FILE_SIZE_MB} MB. "
                "Upload a smaller document."
            ),
        )

    return contents


@app.post(
    "/api/analyze",
    response_model=AnalysisResponse,
    tags=["loan"],
    summary="Analyse a loan application PDF",
)
async def analyze_application(file: UploadFile = File(...)):
    """
    Full pipeline: PDF text -> field extraction -> summary ->
    rule-based risk flags -> final assessment.
    """
    contents = await _read_pdf_upload(file)

    # Step 1 — read the document
    try:
        document_text, page_count = extract_text_from_bytes(contents)
    except PDFExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Step 2 — extract structured fields
    try:
        application_data = llm_service.extract_application_data(document_text)
    except llm_service.LLMError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Field extraction failed. {exc}",
        ) from exc

    # Step 3 — summary for the relationship officer
    try:
        summary = llm_service.generate_summary(document_text, application_data)
    except llm_service.LLMError as exc:
        summary = f"Summary could not be generated: {exc}"

    # Step 4 — deterministic risk rules
    risk_flags = risk_rules.detect_risk_flags(application_data)

    # Step 5 — final assessment (never raises; degrades to HUMAN REVIEW)
    assessment = llm_service.generate_final_assessment(
        application_data, risk_flags
    )

    return {
        "document": {
            "filename": file.filename,
            "pages": page_count,
            "characters_extracted": len(document_text),
        },
        "application_data": application_data,
        "summary": summary,
        "risk_flags": risk_flags,
        "assessment": assessment,
    }


@app.post(
    "/api/extract-text",
    tags=["loan"],
    summary="Return raw PDF text only (no model call)",
)
async def extract_text_only(file: UploadFile = File(...)):
    """Useful for checking whether a PDF is machine-readable before spending
    a model call on it."""
    contents = await _read_pdf_upload(file)

    try:
        document_text, page_count = extract_text_from_bytes(contents)
    except PDFExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "filename": file.filename,
        "pages": page_count,
        "characters_extracted": len(document_text),
        "text": document_text,
    }


@app.post(
    "/api/risk-flags",
    tags=["loan"],
    summary="Run the risk rules on already-extracted fields",
)
async def risk_flags_only(application_data: dict):
    """Post the extracted JSON directly to re-run the rules after an officer
    corrects a field by hand."""
    return {
        "risk_flags": risk_rules.detect_risk_flags(application_data),
        "loan_to_income_ratio": risk_rules.loan_to_income_ratio(
            application_data
        ),
    }
