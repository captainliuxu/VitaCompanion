from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.proactive import (
    ProactiveDecisionListData,
    ProactiveDecisionRead,
    ProactiveExecuteData,
    ProactiveMessageListData,
    ProactiveMessageRead,
    ProactiveWindowRead,
    ProactiveWindowUpdate,
)
from app.services.proactive_message_service import proactive_message_service
from app.services.proactive_service import proactive_service
from app.services.proactive_window_service import proactive_window_service

router = APIRouter(prefix="/proactive", tags=["proactive"])


@router.get(
    "/window",
    response_model=ApiResponse[ProactiveWindowRead],
)
def get_my_proactive_window(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    window = proactive_window_service.get_or_create_for_user(db, current_user.id)
    return success_response(
        data=ProactiveWindowRead.model_validate(window),
        message="success",
    )


@router.put(
    "/window",
    response_model=ApiResponse[ProactiveWindowRead],
)
def update_my_proactive_window(
    payload: ProactiveWindowUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    window = proactive_window_service.update_for_user(
        db=db,
        user_id=current_user.id,
        payload=payload,
    )
    return success_response(
        data=ProactiveWindowRead.model_validate(window),
        message="proactive window updated",
    )


@router.get(
    "/decisions",
    response_model=ApiResponse[ProactiveDecisionListData],
)
def list_my_proactive_decisions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    decisions = proactive_service.list_decisions_for_user(db, current_user.id)
    return success_response(
        data=ProactiveDecisionListData(
            items=[ProactiveDecisionRead.model_validate(item) for item in decisions]
        ),
        message="success",
    )


@router.get(
    "/messages",
    response_model=ApiResponse[ProactiveMessageListData],
)
def list_my_proactive_messages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    messages = proactive_message_service.list_for_user(db, current_user.id)
    return success_response(
        data=ProactiveMessageListData(
            items=[ProactiveMessageRead.model_validate(item) for item in messages]
        ),
        message="success",
    )


@router.patch(
    "/messages/{message_id}/displayed",
    response_model=ApiResponse[ProactiveMessageRead],
)
def mark_proactive_message_displayed(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    message = proactive_message_service.mark_displayed(
        db=db,
        user_id=current_user.id,
        message_id=message_id,
    )
    return success_response(
        data=ProactiveMessageRead.model_validate(message),
        message="proactive message displayed",
    )


@router.post(
    "/rules/{rule_id}/execute",
    response_model=ApiResponse[ProactiveExecuteData],
)
def execute_proactive_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = proactive_service.execute_rule_for_user(
        db=db,
        user_id=current_user.id,
        rule_id=rule_id,
    )
    return success_response(
        data=ProactiveExecuteData(
            log_id=result["log_id"],
            decision_id=result["decision_id"],
            rule_id=result["rule_id"],
            triggered=result["triggered"],
            message_created=result["message_created"],
            status=result["status"],
            reason=result["reason"],
            proactive_message=(
                ProactiveMessageRead.model_validate(result["proactive_message"])
                if result["proactive_message"]
                else None
            ),
        ),
        message="proactive rule executed",
    )
