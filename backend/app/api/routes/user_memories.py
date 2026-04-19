from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.user_memory import (
    UserMemoryCreate,
    UserMemoryListData,
    UserMemoryRead,
    UserMemoryUpdate,
)
from app.services.user_memory_service import user_memory_service

router = APIRouter(prefix="/user-memories", tags=["user-memories"])


@router.post(
    "",
    response_model=ApiResponse[UserMemoryRead],
    status_code=status.HTTP_201_CREATED,
)
def create_user_memory(
    payload: UserMemoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    memory = user_memory_service.create_for_user(db, current_user.id, payload)
    return success_response(
        data=UserMemoryRead.model_validate(memory),
        message="user memory created",
    )


@router.get(
    "",
    response_model=ApiResponse[UserMemoryListData],
)
def list_user_memories(
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    memories = user_memory_service.list_for_user(
        db=db,
        user_id=current_user.id,
        include_archived=include_archived,
    )
    return success_response(
        data=UserMemoryListData(
            items=[UserMemoryRead.model_validate(item) for item in memories]
        ),
        message="success",
    )


@router.get(
    "/{memory_id}",
    response_model=ApiResponse[UserMemoryRead],
)
def get_user_memory(
    memory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    memory = user_memory_service.get_or_raise(db, current_user.id, memory_id)
    return success_response(
        data=UserMemoryRead.model_validate(memory),
        message="success",
    )


@router.put(
    "/{memory_id}",
    response_model=ApiResponse[UserMemoryRead],
)
def update_user_memory(
    memory_id: int,
    payload: UserMemoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    memory = user_memory_service.update_for_user(
        db=db,
        user_id=current_user.id,
        memory_id=memory_id,
        payload=payload,
    )
    return success_response(
        data=UserMemoryRead.model_validate(memory),
        message="user memory updated",
    )


@router.delete(
    "/{memory_id}",
    response_model=ApiResponse[None],
)
def delete_user_memory(
    memory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    user_memory_service.delete_for_user(db, current_user.id, memory_id)
    return success_response(message="user memory deleted")
