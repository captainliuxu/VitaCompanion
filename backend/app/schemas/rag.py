from pydantic import BaseModel, Field


class RagCitation(BaseModel):
    source_index: int
    chunk_id: int
    document_id: int
    knowledge_base_id: int
    title: str
    file_name: str
    content_preview: str
    score: float
    chunk_index: int


class RagRetrieveDebugRequest(BaseModel):
    knowledge_base_id: int = Field(..., ge=1)
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class RagRetrieveDebugData(BaseModel):
    knowledge_base_id: int
    query: str
    items: list[RagCitation]
