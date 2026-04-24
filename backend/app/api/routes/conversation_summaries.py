from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.conversation_summary import (
    ConversationSummaryGenerateRequest,
    ConversationSummaryRead,
)
from app.services.conversation_summary_service import conversation_summary_service

router = APIRouter(
    prefix="/conversations/{conversation_id}/summary",
    tags=["conversation-summaries"],
)


@router.get(
    "",
    response_model=ApiResponse[ConversationSummaryRead],
)
def get_conversation_summary(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    summary = conversation_summary_service.get_or_raise(
        db=db,
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    return success_response(
        data=ConversationSummaryRead.model_validate(summary),
        message="success",
    )


@router.post(
    "/generate",
    response_model=ApiResponse[ConversationSummaryRead],
)
def generate_conversation_summary(
    conversation_id: int,
    payload: ConversationSummaryGenerateRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    payload = payload or ConversationSummaryGenerateRequest()
    summary = conversation_summary_service.generate_for_conversation(
        db=db,
        user_id=current_user.id,
        conversation_id=conversation_id,
        max_messages=payload.max_messages,
    )
    return success_response(
        data=ConversationSummaryRead.model_validate(summary),
        message="conversation summary generated",
    )
