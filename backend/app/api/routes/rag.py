from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.rag import RagRetrieveDebugData, RagRetrieveDebugRequest
from app.services.rag_service import rag_service

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post(
    "/retrieve-debug",
    response_model=ApiResponse[RagRetrieveDebugData],
)
def retrieve_debug(
    payload: RagRetrieveDebugRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    items = rag_service.retrieve(
        db=db,
        user_id=current_user.id,
        knowledge_base_id=payload.knowledge_base_id,
        query=payload.query,
        top_k=payload.top_k,
    )
    return success_response(
        data=RagRetrieveDebugData(
            knowledge_base_id=payload.knowledge_base_id,
            query=payload.query,
            items=items,
        ),
        message="rag retrieve debug success",
    )
