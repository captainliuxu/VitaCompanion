from __future__ import annotations

import re


class ChunkingService:
    def split_text(
        self,
        text: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ) -> list[str]:
        cleaned = self._normalize_text(text)
        if not cleaned:
            return []

        if len(cleaned) <= chunk_size:
            return [cleaned]

        chunks: list[str] = []
        start = 0
        text_length = len(cleaned)
        overlap = min(chunk_overlap, chunk_size // 2)

        while start < text_length:
            end = min(start + chunk_size, text_length)
            if end < text_length:
                split_at = self._find_split_position(cleaned, start, end)
                if split_at > start:
                    end = split_at

            chunk = cleaned[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= text_length:
                break
            start = max(end - overlap, start + 1)

        return chunks

    def count_tokens(self, text: str) -> int:
        return len(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+", text))

    def _normalize_text(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _find_split_position(self, text: str, start: int, end: int) -> int:
        window = text[start:end]
        for separator in ("\n\n", "\n", "。", "！", "？", ". ", "; ", "；"):
            index = window.rfind(separator)
            if index >= max(80, len(window) // 2):
                return start + index + len(separator)
        return end


chunking_service = ChunkingService()
