from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.response import success_response
from app.schemas.auth import Token, UserRegisterRequest, LoginRequest
from app.schemas.common import ApiResponse
from app.schemas.user import UserRead
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=ApiResponse[UserRead],
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    payload: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    user = auth_service.register(db, payload)
    return success_response(
        data=UserRead.model_validate(user),
        message="register success",
    )


@router.post(
    "/login",
    response_model=Token,
)
def login_user(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    return auth_service.login(db, payload.username, payload.password)