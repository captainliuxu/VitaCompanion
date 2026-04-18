from __future__ import annotations

import json
from collections.abc import Iterator

import httpx

from app.core.config import settings
from app.core.exception import BusinessException


class LLMService:
    REQUEST_TIMEOUT_SECONDS = 60.0

    def chat(self, messages: list[dict[str, str]]) -> str:
        self._validate_settings()

        try:
            with httpx.Client(timeout=self.REQUEST_TIMEOUT_SECONDS) as client:
                response = client.post(
                    self._build_url(),
                    headers=self._build_headers(),
                    json=self._build_payload(messages=messages, stream=False),
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise BusinessException(
                code=50241,
                message=f"llm request failed: {detail}",
                status_code=502,
            )
        except httpx.HTTPError as exc:
            raise BusinessException(
                code=50242,
                message=f"llm request error: {exc}",
                status_code=502,
            )

        content = self._extract_chat_content(response.json())
        cleaned_content = content.strip()
        if not cleaned_content:
            raise BusinessException(
                code=50244,
                message="llm returned empty content",
                status_code=502,
            )
        return cleaned_content

    def stream_chat(self, messages: list[dict[str, str]]) -> Iterator[str]:
        self._validate_settings()
        has_token = False

        try:
            with httpx.Client(timeout=self.REQUEST_TIMEOUT_SECONDS) as client:
                with client.stream(
                    "POST",
                    self._build_url(),
                    headers=self._build_headers(),
                    json=self._build_payload(messages=messages, stream=True),
                ) as response:
                    response.raise_for_status()

                    for raw_line in response.iter_lines():
                        line = self._normalize_stream_line(raw_line)
                        if not line:
                            continue
                        if line == "[DONE]":
                            break

                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        token = self._extract_stream_token(payload)
                        if token:
                            has_token = True
                            yield token
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise BusinessException(
                code=50241,
                message=f"llm request failed: {detail}",
                status_code=502,
            )
        except httpx.HTTPError as exc:
            raise BusinessException(
                code=50242,
                message=f"llm request error: {exc}",
                status_code=502,
            )

        if not has_token:
            raise BusinessException(
                code=50245,
                message="llm returned empty stream",
                status_code=502,
            )

    def _build_url(self) -> str:
        return settings.LLM_BASE_URL.rstrip("/") + "/chat/completions"

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.LLM_API_KEY}",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        messages: list[dict[str, str]],
        stream: bool,
    ) -> dict[str, object]:
        return {
            "model": settings.LLM_MODEL_NAME,
            "messages": messages,
            "temperature": 0.7,
            "stream": stream,
        }

    def _validate_settings(self) -> None:
        if not settings.LLM_API_KEY:
            raise BusinessException(
                code=50041,
                message="LLM_API_KEY is not configured",
                status_code=500,
            )
        if not settings.LLM_BASE_URL:
            raise BusinessException(
                code=50042,
                message="LLM_BASE_URL is not configured",
                status_code=500,
            )
        if not settings.LLM_MODEL_NAME:
            raise BusinessException(
                code=50043,
                message="LLM_MODEL_NAME is not configured",
                status_code=500,
            )

    def _extract_chat_content(self, payload: object) -> str:
        try:
            return str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError):
            raise BusinessException(
                code=50243,
                message="invalid llm response format",
                status_code=502,
            )

    def _normalize_stream_line(self, raw_line: str | bytes | None) -> str:
        if raw_line is None:
            return ""

        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        text = line.strip()
        if not text:
            return ""

        if text.startswith("data:"):
            return text[5:].strip()
        return text

    def _extract_stream_token(self, payload: object) -> str:
        try:
            choice = payload["choices"][0]
        except (KeyError, IndexError, TypeError):
            return ""

        delta = choice.get("delta") if isinstance(choice, dict) else None
        if isinstance(delta, dict):
            content = delta.get("content")
            if content:
                return str(content)

        if isinstance(choice, dict):
            message = choice.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if content:
                    return str(content)

            text = choice.get("text")
            if text:
                return str(text)

        return ""


llm_service = LLMService()
