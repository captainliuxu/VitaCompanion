from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.schemas.chat import (
    ChatAssistantActionData,
    ChatSendData,
    ChatSendRequest,
)
from app.schemas.common import ApiResponse
from app.services.chat_service import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])

STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post(
    "/send",
    response_model=ApiResponse[ChatSendData],
)
def send_chat_message(
    payload: ChatSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = chat_service.send_message(
        db=db,
        user_id=current_user.id,
        payload=payload,
    )
    return success_response(
        data=result,
        message="chat reply generated",
    )


@router.post("/send-stream")
def send_chat_message_stream(
    payload: ChatSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    stream = chat_service.send_message_stream(
        db=db,
        user_id=current_user.id,
        payload=payload,
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers=STREAM_HEADERS,
    )


@router.post(
    "/messages/{assistant_message_id}/cancel",
    response_model=ApiResponse[ChatAssistantActionData],
)
def cancel_chat_message(
    assistant_message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = chat_service.cancel_message(
        db=db,
        user_id=current_user.id,
        assistant_message_id=assistant_message_id,
    )
    return success_response(
        data=result,
        message="assistant message cancelled",
    )


@router.post(
    "/messages/{assistant_message_id}/regenerate",
    response_model=ApiResponse[ChatSendData],
)
def regenerate_chat_message(
    assistant_message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = chat_service.regenerate_message(
        db=db,
        user_id=current_user.id,
        assistant_message_id=assistant_message_id,
    )
    return success_response(
        data=result,
        message="chat reply regenerated",
    )


@router.post("/messages/{assistant_message_id}/regenerate-stream")
def regenerate_chat_message_stream(
    assistant_message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    stream = chat_service.regenerate_message_stream(
        db=db,
        user_id=current_user.id,
        assistant_message_id=assistant_message_id,
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers=STREAM_HEADERS,
    )
