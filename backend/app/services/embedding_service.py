from __future__ import annotations

import hashlib
import math
import re


class EmbeddingService:
    MODEL_NAME = "local-hash-embedding-v2"
    DIMENSIONS = 256

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.DIMENSIONS
        tokens = self._tokenize(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.DIMENSIONS
            vector[index] += 1.0

        norm = math.sqrt(sum(item * item for item in vector))
        if norm == 0:
            return vector
        return [round(item / norm, 8) for item in vector]

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
