from __future__ import annotations

import hashlib
import math
import re

import httpx

from app.core.config import settings
from app.core.exception import BusinessException


class EmbeddingService:
    LOCAL_MODEL_NAME = "local-hash-embedding-v2"
    LOCAL_DIMENSIONS = 256
    ZHIPUAI_BATCH_SIZE = 64
    REQUEST_TIMEOUT_SECONDS = 60.0

    @property
    def provider(self) -> str:
        return settings.EMBEDDING_PROVIDER.strip().lower()

    @property
    def model_name(self) -> str:
        if self.provider in {"zhipuai", "zhipu", "glm"}:
            return settings.EMBEDDING_MODEL_NAME or "embedding-3"
        return self.LOCAL_MODEL_NAME

    def embed_text(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        provider = self.provider
        if provider in {"zhipuai", "zhipu", "glm"}:
            return self._embed_texts_zhipuai(texts)
        if provider in {"local", "local-hash", "hash"}:
            return [self._embed_text_local(text) for text in texts]

        raise BusinessException(
            code=50086,
            message=f"unsupported embedding provider: {settings.EMBEDDING_PROVIDER}",
            status_code=500,
        )

    def _embed_text_local(self, text: str) -> list[float]:
        vector = [0.0] * self.LOCAL_DIMENSIONS
        tokens = self._tokenize(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.LOCAL_DIMENSIONS
            vector[index] += 1.0

        norm = math.sqrt(sum(item * item for item in vector))
        if norm == 0:
            return vector
        return [round(item / norm, 8) for item in vector]

    def _embed_texts_zhipuai(self, texts: list[str]) -> list[list[float]]:
        api_key = settings.EMBEDDING_API_KEY or settings.LLM_API_KEY
        base_url = settings.EMBEDDING_BASE_URL or settings.LLM_BASE_URL
        model_name = self.model_name

        if not api_key:
            raise BusinessException(
                code=50087,
                message="EMBEDDING_API_KEY or LLM_API_KEY is not configured",
                status_code=500,
            )
        if not base_url:
            raise BusinessException(
                code=50088,
                message="EMBEDDING_BASE_URL or LLM_BASE_URL is not configured",
                status_code=500,
            )
        if not model_name:
            raise BusinessException(
                code=50089,
                message="EMBEDDING_MODEL_NAME is not configured",
                status_code=500,
            )

        embeddings: list[list[float]] = []
        try:
            with httpx.Client(timeout=self.REQUEST_TIMEOUT_SECONDS) as client:
                for start in range(0, len(texts), self.ZHIPUAI_BATCH_SIZE):
                    batch = [
                        self._normalize_remote_input(text)
                        for text in texts[start : start + self.ZHIPUAI_BATCH_SIZE]
                    ]
                    response = client.post(
                        self._build_embeddings_url(base_url),
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={"model": model_name, "input": batch},
                    )
                    response.raise_for_status()
                    embeddings.extend(
                        self._extract_embeddings(
                            payload=response.json(),
                            expected_count=len(batch),
                        )
                    )
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise BusinessException(
                code=50286,
                message=f"embedding request failed: {detail}",
                status_code=502,
            )
        except httpx.HTTPError as exc:
            raise BusinessException(
                code=50287,
                message=f"embedding request error: {exc}",
                status_code=502,
            )

        if len(embeddings) != len(texts):
            raise BusinessException(
                code=50288,
                message="embedding response count mismatch",
                status_code=502,
            )
        return embeddings

    def _build_embeddings_url(self, base_url: str) -> str:
        return base_url.rstrip("/") + "/embeddings"

    def _extract_embeddings(
        self,
        payload: object,
        expected_count: int,
    ) -> list[list[float]]:
        if not isinstance(payload, dict):
            raise self._invalid_response()

        data = payload.get("data")
        if not isinstance(data, list) or len(data) != expected_count:
            raise self._invalid_response()

        if all(isinstance(item, dict) and "index" in item for item in data):
            data = sorted(data, key=lambda item: int(item["index"]))

        embeddings: list[list[float]] = []
        for item in data:
            if not isinstance(item, dict):
                raise self._invalid_response()
            embedding = item.get("embedding")
            if not isinstance(embedding, list) or not embedding:
                raise self._invalid_response()
            embeddings.append([float(value) for value in embedding])
        return embeddings

    def _invalid_response(self) -> BusinessException:
        return BusinessException(
            code=50289,
            message="invalid embedding response format",
            status_code=502,
        )

    def _normalize_remote_input(self, text: str) -> str:
        cleaned = " ".join((text or "").split())
        return cleaned or " "

    def _tokenize(self, text: str) -> list[str]:
        lowered = text.lower()
        tokens: list[str] = []
        for item in re.findall(r"[\u4e00-\u9fff]+|[a-z0-9_]+", lowered):
            if re.fullmatch(r"[\u4e00-\u9fff]+", item):
                tokens.extend(item)
                tokens.extend(
                    item[index : index + 2]
                    for index in range(max(len(item) - 1, 0))
                )
                tokens.extend(
                    item[index : index + 3]
                    for index in range(max(len(item) - 2, 0))
                )
            else:
                tokens.append(item)
        return tokens


embedding_service = EmbeddingService()
