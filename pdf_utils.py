"""
PDF text extraction.

The notebook read a PDF from disk by path. Here the file arrives as bytes
from an HTTP upload, so PyMuPDF opens it from a memory stream instead.
"""

from typing import Tuple

import pymupdf

from config import settings


class PDFExtractionError(Exception):
    """Raised when the PDF cannot be read or contains no selectable text."""


def extract_text_from_bytes(file_bytes: bytes) -> Tuple[str, int]:
    """
    Return (text, page_count) for an uploaded PDF.

    Raises PDFExtractionError for corrupt files, oversized documents,
    or scanned image-only PDFs with no extractable text.
    """
    try:
        document = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise PDFExtractionError(
            f"The file could not be opened as a PDF: {exc}"
        ) from exc

    try:
        page_count = document.page_count

        if page_count > settings.MAX_PAGES:
            raise PDFExtractionError(
                f"This document has {page_count} pages. "
                f"The limit is {settings.MAX_PAGES}."
            )

        pages = []
        for page_number, page in enumerate(document):
            pages.append(
                f"\n--- PAGE {page_number + 1} ---\n{page.get_text()}"
            )

        text = "\n".join(pages)
    finally:
        document.close()

    if not text.strip():
        raise PDFExtractionError(
            "No text found in this PDF. It is likely a scanned image, "
            "which needs OCR before it can be read."
        )

    return text, page_count
