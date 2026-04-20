from __future__ import annotations

import json
from pathlib import Path

from app.core.exception import BusinessException


class DocumentLoaderService:
    SUPPORTED_EXTENSIONS = {".txt", ".md", ".json", ".pdf"}

    def load_text(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix not in self.SUPPORTED_EXTENSIONS:
            raise BusinessException(
                code=40081,
                message=f"unsupported document type: {suffix}",
                status_code=400,
            )

        if suffix in {".txt", ".md"}:
            return self._read_text(path)
        if suffix == ".json":
            return self._read_json(path)
        if suffix == ".pdf":
            return self._read_pdf(path)

        raise BusinessException(
            code=40081,
            message=f"unsupported document type: {suffix}",
            status_code=400,
        )

    def _read_text(self, path: Path) -> str:
        for encoding in ("utf-8", "utf-8-sig", "gb18030"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return path.read_text(encoding="utf-8", errors="ignore")

    def _read_json(self, path: Path) -> str:
        raw_text = self._read_text(path)
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            return raw_text
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _read_pdf(self, path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError:
            raise BusinessException(
                code=50081,
                message="pypdf is not installed",
                status_code=500,
            )

        try:
            reader = PdfReader(str(path))
            pages: list[str] = []
            nonempty_body_pages = 0
            for page in reader.pages:
                pages.append(page.extract_text() or "")
            for page_text in pages[1:]:
                if page_text.strip():
                    nonempty_body_pages += 1
        except Exception as exc:
            raise BusinessException(
                code=40082,
                message=f"failed to read pdf: {exc}",
                status_code=400,
            )

        text = "\n\n".join(page for page in pages if page.strip())
        self._validate_pdf_text_quality(
            page_count=len(pages),
            nonempty_body_pages=nonempty_body_pages,
            char_count=len(text.strip()),
        )
        return text

    def _validate_pdf_text_quality(
        self,
        page_count: int,
        nonempty_body_pages: int,
        char_count: int,
    ) -> None:
        if char_count == 0:
            raise BusinessException(
                code=40086,
                message="pdf has no extractable text; OCR may be required",
                status_code=400,
            )

        if page_count < 20:
            return

        body_page_count = max(page_count - 1, 1)
        body_text_ratio = nonempty_body_pages / body_page_count
        if char_count < 5000 or body_text_ratio < 0.2:
            raise BusinessException(
                code=40086,
                message="pdf has insufficient extractable text; OCR may be required",
                status_code=400,
            )


document_loader_service = DocumentLoaderService()
