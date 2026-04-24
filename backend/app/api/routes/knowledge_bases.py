from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseListData,
    KnowledgeBaseRead,
    KnowledgeBaseUpdate,
    KnowledgeChunkListData,
    KnowledgeChunkRead,
    KnowledgeDocumentListData,
    KnowledgeDocumentRead,
    KnowledgeImportDefaultRequest,
    KnowledgeImportLocalRequest,
    KnowledgeImportResultData,
    KnowledgeRetrieveData,
    KnowledgeRetrieveRequest,
)
from app.services.knowledge_base_service import knowledge_base_service
from app.services.knowledge_ingestion_service import knowledge_ingestion_service
from app.services.vector_store_service import vector_store_service

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


@router.post(
    "",
    response_model=ApiResponse[KnowledgeBaseRead],
    status_code=status.HTTP_201_CREATED,
)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    item = knowledge_base_service.create_for_user(db, current_user.id, payload)
    return success_response(
        data=KnowledgeBaseRead.model_validate(item),
        message="knowledge base created",
    )


@router.get(
    "",
    response_model=ApiResponse[KnowledgeBaseListData],
)
def list_knowledge_bases(
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    items = knowledge_base_service.list_for_user(
        db=db,
        user_id=current_user.id,
        include_archived=include_archived,
    )
    return success_response(
        data=KnowledgeBaseListData(
            items=[KnowledgeBaseRead.model_validate(item) for item in items]
        ),
        message="success",
    )


@router.get(
    "/{knowledge_base_id}",
    response_model=ApiResponse[KnowledgeBaseRead],
)
def get_knowledge_base(
    knowledge_base_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    item = knowledge_base_service.get_or_raise(
        db=db,
        user_id=current_user.id,
        knowledge_base_id=knowledge_base_id,
    )
    return success_response(
        data=KnowledgeBaseRead.model_validate(item),
        message="success",
    )


@router.put(
    "/{knowledge_base_id}",
    response_model=ApiResponse[KnowledgeBaseRead],
)
def update_knowledge_base(
    knowledge_base_id: int,
    payload: KnowledgeBaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    item = knowledge_base_service.update_for_user(
        db=db,
        user_id=current_user.id,
        knowledge_base_id=knowledge_base_id,
        payload=payload,
    )
    return success_response(
        data=KnowledgeBaseRead.model_validate(item),
        message="knowledge base updated",
    )


@router.delete(
    "/{knowledge_base_id}",
    response_model=ApiResponse[None],
)
def delete_knowledge_base(
    knowledge_base_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    knowledge_base_service.delete_for_user(
        db=db,
        user_id=current_user.id,
        knowledge_base_id=knowledge_base_id,
    )
    return success_response(message="knowledge base deleted")


@router.get(
    "/{knowledge_base_id}/documents",
    response_model=ApiResponse[KnowledgeDocumentListData],
)
def list_knowledge_documents(
    knowledge_base_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    documents = knowledge_ingestion_service.list_documents(
        db=db,
        user_id=current_user.id,
        knowledge_base_id=knowledge_base_id,
    )
    return success_response(
        data=KnowledgeDocumentListData(
            items=[KnowledgeDocumentRead.model_validate(item) for item in documents]
        ),
        message="success",
    )


@router.post(
    "/{knowledge_base_id}/documents/import-local",
    response_model=ApiResponse[KnowledgeImportResultData],
)
def import_local_documents(
    knowledge_base_id: int,
    payload: KnowledgeImportLocalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    documents = knowledge_ingestion_service.import_local_path(
        db=db,
        user_id=current_user.id,
        knowledge_base_id=knowledge_base_id,
        source_path=payload.source_path,
        recursive=payload.recursive,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
    )
    return _build_import_response(documents)


@router.post(
    "/{knowledge_base_id}/documents/import-default-sources",
    response_model=ApiResponse[KnowledgeImportResultData],
)
def import_default_documents(
    knowledge_base_id: int,
    payload: KnowledgeImportDefaultRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    payload = payload or KnowledgeImportDefaultRequest()
    documents = knowledge_ingestion_service.import_default_sources(
        db=db,
        user_id=current_user.id,
        knowledge_base_id=knowledge_base_id,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
    )
    return _build_import_response(documents)


@router.get(
    "/{knowledge_base_id}/documents/{document_id}/chunks",
    response_model=ApiResponse[KnowledgeChunkListData],
)
def list_knowledge_chunks(
    knowledge_base_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    chunks = knowledge_ingestion_service.list_chunks(
        db=db,
        user_id=current_user.id,
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
    )
    return success_response(
        data=KnowledgeChunkListData(
            items=[KnowledgeChunkRead.model_validate(item) for item in chunks]
        ),
        message="success",
    )


@router.post(
    "/{knowledge_base_id}/retrieve",
    response_model=ApiResponse[KnowledgeRetrieveData],
)
def retrieve_knowledge_chunks(
    knowledge_base_id: int,
    payload: KnowledgeRetrieveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    knowledge_base_service.get_or_raise(
        db=db,
        user_id=current_user.id,
        knowledge_base_id=knowledge_base_id,
    )
    items = vector_store_service.search(
        db=db,
        user_id=current_user.id,
        knowledge_base_id=knowledge_base_id,
        query=payload.query,
        top_k=payload.top_k,
    )
    return success_response(
        data=KnowledgeRetrieveData(items=items),
        message="success",
    )


def _build_import_response(documents):
    completed = [item for item in documents if item.status == "completed"]
    failed = [item for item in documents if item.status == "failed"]
    return success_response(
        data=KnowledgeImportResultData(
            documents=[KnowledgeDocumentRead.model_validate(item) for item in documents],
            imported_count=len(completed),
            failed_count=len(failed),
        ),
        message="documents imported",
    )
