# Loan Application Summarisation & Risk Flag Agent

FastAPI service for the BFSI use case. A relationship officer uploads a loan
application PDF; the service extracts the key fields, writes a five-point
summary, flags risk signals, and returns a structured brief for human review.

No Kaggle dataset is used — the PDF comes from the user at request time.

## Files

| File | What it does |
|---|---|
| `main.py` | FastAPI app, routes, upload validation |
| `config.py` | Settings read from `.env` |
| `pdf_utils.py` | PDF text extraction from uploaded bytes |
| `llm_service.py` | Groq calls: extraction, summary, final assessment |
| `risk_rules.py` | Deterministic risk checks (no LLM) |
| `schemas.py` | Pydantic response models |
| `index.html` | Upload and review page served at `/` |
| `requirements.txt` | Dependencies |
| `.env.example` | Template for your `.env` |
| `.gitignore` | Keeps `.env` out of version control |

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

pip install -r requirements.txt

copy .env.example .env         # Windows
# cp .env.example .env         # macOS / Linux
```

Open `.env` and paste your Groq key into `GROQ_API_KEY`.

**Important:** the key from your notebook is now in a shared file, so treat it
as compromised — revoke it at https://console.groq.com/keys and generate a new
one for this project.

## Run

```bash
uvicorn main:app --reload
```

- Upload page: http://127.0.0.1:8000
- Swagger docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

## Endpoints

### `POST /api/analyze`
The main one. Multipart form field `file` — a PDF.

```bash
curl -X POST http://127.0.0.1:8000/api/analyze \
  -F "file=@Loan_Application_Text4.pdf"
```

Returns:

```json
{
  "document": { "filename": "...", "pages": 2, "characters_extracted": 3184 },
  "application_data": {
    "applicant_name": "...", "age": 34, "monthly_income": "18000",
    "loan_amount": "150000", "loan_purpose": "...", "co_applicant": "...",
    "employment": "...", "phone_number": "...", "address": "...",
    "income_proof_present": true
  },
  "summary": "- ...\n- ...",
  "risk_flags": ["Income proof is missing."],
  "assessment": {
    "risk_level": "MEDIUM",
    "recommendation": "REQUEST MORE INFORMATION",
    "reason": "..."
  }
}
```

### `POST /api/extract-text`
Text only, no model call. Use it to check whether a PDF is machine-readable
before spending an API call on it.

### `POST /api/risk-flags`
Post the extracted JSON directly to re-run the rules after an officer corrects
a field by hand.

### Error codes

| Code | Meaning |
|---|---|
| 400 | Not a PDF, or empty file |
| 413 | Larger than `MAX_FILE_SIZE_MB` |
| 422 | Corrupt PDF, too many pages, or scanned image with no text |
| 502 | Groq call failed |

## What changed from the notebook

1. **API key moved to `.env`.** It was hardcoded in cell 3.
2. **`verify=False` is now a setting, not a default.** Disabling SSL
   verification exposes your key on the network. Leave `VERIFY_SSL=true`
   unless your campus network forces otherwise.
3. **PDF read from memory, not a fixed path.** `pymupdf.open(stream=...)`
   instead of `pymupdf.open("Loan_Application_Text4.pdf")`.
4. **Bug fix in the ratio check.** `check_income_loan_ratio` returned a
   success string even when nothing was wrong, and `detect_risk_flags`
   appended any truthy value — so every application came back flagged. It now
   returns `None` when the ratio is fine.
5. **Indian number formats parse correctly.** `₹1,50,000`, `Rs 18,000`, and
   `150000` all resolve to the same number.
6. **A failed assessment degrades to `HUMAN REVIEW REQUIRED`**, never to an
   approval.

## Note on scope

The output is a decision aid, not a decision. `risk_flags` comes from fixed
rules and is reproducible; `summary` and `assessment` come from a language
model and can be wrong even when the wording sounds confident. Every
application still needs an officer to read it.
