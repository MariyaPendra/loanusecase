"""
Configuration for the Loan Application Summarisation & Risk Flag Agent.

All secrets come from environment variables (.env file).
Never hardcode the Groq API key in source code.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ---------- Groq ----------
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    # Set to "false" only if your college/office network breaks SSL.
    VERIFY_SSL: bool = os.getenv("VERIFY_SSL", "true").lower() == "true"
    REQUEST_TIMEOUT: float = float(os.getenv("REQUEST_TIMEOUT", "120"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "2"))

    # ---------- Upload rules ----------
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
    MAX_PAGES: int = int(os.getenv("MAX_PAGES", "25"))

    # ---------- Business rules ----------
    # Loan amount / monthly income above this ratio is flagged.
    MAX_LOAN_TO_INCOME_RATIO: float = float(
        os.getenv("MAX_LOAN_TO_INCOME_RATIO", "20")
    )

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


settings = Settings()
