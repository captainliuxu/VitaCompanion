from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseStatus(str, Enum):
    active = "active"
    archived = "archived"


class KnowledgeDocumentStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    status: KnowledgeBaseStatus | None = None


class KnowledgeBaseRead(BaseModel):
    id: int
    name: str
    description: str | None = None
    status: KnowledgeBaseStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeBaseListData(BaseModel):
    items: list[KnowledgeBaseRead]


class KnowledgeDocumentRead(BaseModel):
    id: int
    knowledge_base_id: int
    title: str
    file_name: str
    file_path: str
    file_type: str
    content_hash: str
    status: KnowledgeDocumentStatus
    error_message: str | None = None
    chunk_count: int
    indexed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeDocumentListData(BaseModel):
    items: list[KnowledgeDocumentRead]


class KnowledgeChunkRead(BaseModel):
    id: int
    knowledge_base_id: int
    document_id: int
    chunk_index: int
    content: str
    char_count: int
    token_count: int
    embedding_model: str
    metadata_json: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeChunkListData(BaseModel):
    items: list[KnowledgeChunkRead]


class KnowledgeImportLocalRequest(BaseModel):
    source_path: str = Field(..., min_length=1, max_length=1000)
    recursive: bool = False
    chunk_size: int = Field(default=1000, ge=200, le=4000)
    chunk_overlap: int = Field(default=150, ge=0, le=1000)


class KnowledgeImportDefaultRequest(BaseModel):
    chunk_size: int = Field(default=1000, ge=200, le=4000)
    chunk_overlap: int = Field(default=150, ge=0, le=1000)


class KnowledgeImportResultData(BaseModel):
    documents: list[KnowledgeDocumentRead]
    imported_count: int
    failed_count: int


class KnowledgeRetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeRetrieveItem(BaseModel):
    chunk_id: int
    document_id: int
    knowledge_base_id: int
    title: str
    file_name: str
    content: str
    score: float
    chunk_index: int


class KnowledgeRetrieveData(BaseModel):
    items: list[KnowledgeRetrieveItem]
