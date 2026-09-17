"""
Groq LLM calls: field extraction, summary generation, final assessment.

Same prompts as the notebook, wrapped in reusable functions with a single
shared client created once at import time.
"""

import json
import re
from typing import Any, Dict, List, Optional

import httpx
from groq import Groq

from config import settings


class LLMError(Exception):
    """Raised when the model call fails or returns unusable output."""


# ------------------------------------------------------------------
# Shared client (created once, reused for every request)
# ------------------------------------------------------------------

def _build_client() -> Groq:
    if not settings.GROQ_API_KEY:
        raise LLMError(
            "GROQ_API_KEY is not set. Add it to your .env file."
        )

    http_client = httpx.Client(
        verify=settings.VERIFY_SSL,
        timeout=settings.REQUEST_TIMEOUT,
    )

    return Groq(
        api_key=settings.GROQ_API_KEY,
        http_client=http_client,
        max_retries=settings.MAX_RETRIES,
    )


_client: Optional[Groq] = None


def get_client() -> Groq:
    global _client
    if _client is None:
        _client = _build_client()
    return _client


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers some models add around JSON."""
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _chat(messages: List[Dict[str, str]], temperature: float = 0) -> str:
    try:
        response = get_client().chat.completions.create(
            model=settings.MODEL,
            temperature=temperature,
            messages=messages,
        )
    except Exception as exc:
        raise LLMError(f"{type(exc).__name__}: {exc}") from exc

    content = response.choices[0].message.content

    if not content:
        raise LLMError("The model returned an empty response.")

    return content


# ------------------------------------------------------------------
# 1. Extract structured fields
# ------------------------------------------------------------------

EXTRACTION_SCHEMA = {
    "applicant_name": None,
    "age": None,
    "monthly_income": None,
    "loan_amount": None,
    "loan_purpose": None,
    "co_applicant": None,
    "employment": None,
    "phone_number": None,
    "address": None,
    "income_proof_present": None,
}


def extract_application_data(document_text: str) -> Dict[str, Any]:
    prompt = f"""
You are a loan document information extraction assistant.

Read the loan application document below.

Extract the requested information.

IMPORTANT RULES:

1. Extract information only from the document.
2. Do not invent information.
3. If information is not available, return null.
4. Calculate age from Date of Birth if Date of Birth is available.
5. Return ONLY valid JSON.
6. Do not use Markdown.
7. Do not put ``` around the JSON.

Return exactly this structure:

{json.dumps(EXTRACTION_SCHEMA, indent=4)}

LOAN APPLICATION DOCUMENT:

{document_text}
"""

    raw = _chat(
        [
            {
                "role": "system",
                "content": (
                    "You are a document information extraction assistant. "
                    "Return valid JSON only."
                ),
            },
            {"role": "user", "content": prompt},
        ]
    )

    cleaned = _strip_markdown_fences(raw)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMError(
            f"The model did not return valid JSON: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise LLMError("The model returned JSON that is not an object.")

    # Guarantee every key exists so the response shape is stable.
    return {key: data.get(key) for key in EXTRACTION_SCHEMA}


# ------------------------------------------------------------------
# 2. Plain-language summary
# ------------------------------------------------------------------

def generate_summary(
    document_text: str,
    application_data: Dict[str, Any],
) -> str:
    prompt = f"""
Create a short professional summary of this loan application.

Use ONLY information available in the document.

Do not invent facts.

Extracted information:

{json.dumps(application_data, indent=4)}

Write the summary in exactly 5 bullet points.

Each bullet point should be concise and professional.

DOCUMENT:

{document_text}
"""

    return _chat(
        [
            {
                "role": "system",
                "content": (
                    "You summarize loan applications accurately. "
                    "Use only information provided in the document. "
                    "Do not invent facts."
                ),
            },
            {"role": "user", "content": prompt},
        ]
    ).strip()


# ------------------------------------------------------------------
# 3. Final assessment
# ------------------------------------------------------------------

def generate_final_assessment(
    application_data: Dict[str, Any],
    risk_flags: List[str],
) -> Dict[str, str]:
    if not risk_flags:
        return {
            "risk_level": "LOW",
            "recommendation": "PROCEED TO HUMAN REVIEW",
            "reason": "No significant risk flags were identified.",
        }

    risk_text = "\n".join(str(flag) for flag in risk_flags)

    prompt = f"""
You are a loan assessment assistant.

Review the extracted loan application information
and the identified risk flags.

Do not invent any information.

APPLICATION DATA:
{json.dumps(application_data, indent=4)}

RISK FLAGS:
{risk_text}

Provide the final assessment in exactly this JSON format:

{{
    "risk_level": "LOW / MEDIUM / HIGH",
    "recommendation": "PROCEED TO HUMAN REVIEW / REQUEST MORE INFORMATION / HIGH RISK - HUMAN REVIEW REQUIRED",
    "reason": "Short explanation of the assessment"
}}

Return ONLY valid JSON.
Do not use Markdown.
"""

    try:
        raw = _chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a loan assessment assistant. "
                        "Return valid JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ]
        )
        result = json.loads(_strip_markdown_fences(raw))

        return {
            "risk_level": str(result.get("risk_level", "UNKNOWN")),
            "recommendation": str(
                result.get("recommendation", "HUMAN REVIEW REQUIRED")
            ),
            "reason": str(result.get("reason", "")),
        }

    except Exception as exc:
        # A failed assessment must never look like an approval.
        return {
            "risk_level": "UNKNOWN",
            "recommendation": "HUMAN REVIEW REQUIRED",
            "reason": f"Assessment could not be generated: {exc}",
        }
