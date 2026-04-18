from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exception import BusinessException
from app.core.timezone import now_beijing
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.message import MessageCreate
from app.services.conversation_service import conversation_service


class MessageService:
    FINAL_STATUSES = {"completed", "failed", "cancelled"}
    VALID_STATUSES = {"draft", "streaming", "completed", "failed", "cancelled"}
    MUTABLE_STATUSES = {"draft", "streaming"}

    def list_for_conversation(
        self,
        db: Session,
        user_id: int,
        conversation_id: int,
    ) -> list[Message]:
        conversation_service.get_or_raise(db, user_id, conversation_id)

        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        return list(db.scalars(stmt).all())

    def get_recent_for_conversation(
        self,
        db: Session,
        user_id: int,
        conversation_id: int,
        limit: int = 10,
        completed_only: bool = False,
    ) -> list[Message]:
        conversation_service.get_or_raise(db, user_id, conversation_id)

        stmt = select(Message).where(Message.conversation_id == conversation_id)
        if completed_only:
            stmt = stmt.where(Message.status == "completed")

        stmt = (
            stmt.order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        items = list(db.scalars(stmt).all())
        items.reverse()
        return items

    def get_recent_completed_for_conversation(
        self,
        db: Session,
        user_id: int,
        conversation_id: int,
        limit: int = 10,
    ) -> list[Message]:
        return self.get_recent_for_conversation(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
            limit=limit,
            completed_only=True,
        )

    def get_history_until_message(
        self,
        db: Session,
        user_id: int,
        conversation_id: int,
        end_message_id: int,
        limit: int = 30,
    ) -> list[Message]:
        conversation_service.get_or_raise(db, user_id, conversation_id)

        stmt = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.id <= end_message_id,
                Message.status == "completed",
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        items = list(db.scalars(stmt).all())
        items.reverse()
        return items

    def create_for_conversation(
        self,
        db: Session,
        user_id: int,
        conversation_id: int,
        role: str,
        content: str,
        message_type: str = "text",
        status: str = "completed",
        reply_to_message_id: int | None = None,
        prompt_version: str | None = None,
        error_code: int | None = None,
        error_message: str | None = None,
    ) -> Message:
        conversation = conversation_service.get_or_raise(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
        )

        cleaned_message_type = message_type.strip()
        if not cleaned_message_type:
            raise BusinessException(
                code=40042,
                message="message_type cannot be empty",
                status_code=400,
            )

        normalized_status = status.strip().lower()
        if normalized_status not in self.VALID_STATUSES:
            raise BusinessException(
                code=40043,
                message=f"invalid message status: {status}",
                status_code=400,
            )

        cleaned_content = content.strip()
        if not cleaned_content:
            if not (role == "assistant" and normalized_status in {"draft", "streaming"}):
                raise BusinessException(
                    code=40041,
                    message="content cannot be empty",
                    status_code=400,
                )

        if reply_to_message_id is not None:
            reply_to_message = db.get(Message, reply_to_message_id)
            if not reply_to_message or reply_to_message.conversation_id != conversation_id:
                raise BusinessException(
                    code=40441,
                    message="reply_to_message not found in this conversation",
                    status_code=404,
                )

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=cleaned_content,
            message_type=cleaned_message_type,
            status=normalized_status,
            reply_to_message_id=reply_to_message_id,
            prompt_version=(prompt_version or None),
            error_code=error_code,
            error_message=(error_message or None),
        )
        db.add(message)

        conversation.updated_at = now_beijing()
        db.add(conversation)

        db.commit()
        db.refresh(message)
        return message

    def create_assistant_draft(
        self,
        db: Session,
        user_id: int,
        conversation_id: int,
        reply_to_message_id: int,
        prompt_version: str,
    ) -> Message:
        return self.create_for_conversation(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
            role="assistant",
            content="",
            message_type="text",
            status="draft",
            reply_to_message_id=reply_to_message_id,
            prompt_version=prompt_version,
        )

    def get_or_raise_for_user(
        self,
        db: Session,
        user_id: int,
        message_id: int,
    ) -> Message:
        stmt = (
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Message.id == message_id,
                Conversation.user_id == user_id,
            )
        )
        message = db.scalar(stmt)
        if not message:
            raise BusinessException(
                code=40441,
                message="message not found",
                status_code=404,
            )
        return message

    def get_assistant_or_raise_for_user(
        self,
        db: Session,
        user_id: int,
        assistant_message_id: int,
    ) -> Message:
        message = self.get_or_raise_for_user(
            db=db,
            user_id=user_id,
            message_id=assistant_message_id,
        )
        if message.role != "assistant":
            raise BusinessException(
                code=40044,
                message="target message is not assistant role",
                status_code=400,
            )
        return message

    def append_stream_token(
        self,
        db: Session,
        user_id: int,
        assistant_message_id: int,
        token: str,
    ) -> Message:
        message = self.get_assistant_or_raise_for_user(
            db=db,
            user_id=user_id,
            assistant_message_id=assistant_message_id,
        )

        if message.status == "cancelled":
            return message
        if message.status not in self.MUTABLE_STATUSES:
            raise BusinessException(
                code=40941,
                message=f"message status {message.status} cannot append token",
                status_code=409,
            )

        if message.status == "draft":
            message.status = "streaming"

        if token:
            message.content = f"{message.content}{token}"

        message.updated_at = now_beijing()
        message.error_code = None
        message.error_message = None
        db.add(message)
        self._touch_conversation(db, message.conversation_id)
        db.commit()
        db.refresh(message)
        return message

    def mark_assistant_completed(
        self,
        db: Session,
        user_id: int,
        assistant_message_id: int,
        final_content: str | None = None,
    ) -> Message:
        message = self.get_assistant_or_raise_for_user(
            db=db,
            user_id=user_id,
            assistant_message_id=assistant_message_id,
        )

        if message.status == "cancelled":
            return message
        if message.status not in self.MUTABLE_STATUSES and message.status != "completed":
            raise BusinessException(
                code=40942,
                message=f"message status {message.status} cannot complete",
                status_code=409,
            )

        if final_content is not None:
            cleaned = final_content.strip()
            if not cleaned:
                raise BusinessException(
                    code=40045,
                    message="final assistant content cannot be empty",
                    status_code=400,
                )
            message.content = cleaned

        message.status = "completed"
        message.error_code = None
        message.error_message = None
        message.updated_at = now_beijing()
        db.add(message)
        self._touch_conversation(db, message.conversation_id)
        db.commit()
        db.refresh(message)
        return message

    def mark_assistant_failed(
        self,
        db: Session,
        user_id: int,
        assistant_message_id: int,
        error_code: int,
        error_message: str,
    ) -> Message:
        message = self.get_assistant_or_raise_for_user(
            db=db,
            user_id=user_id,
            assistant_message_id=assistant_message_id,
        )

        if message.status == "cancelled":
            return message
        if message.status not in self.MUTABLE_STATUSES and message.status != "failed":
            raise BusinessException(
                code=40943,
                message=f"message status {message.status} cannot fail",
                status_code=409,
            )

        message.status = "failed"
        message.error_code = error_code
        message.error_message = error_message[:500]
        message.updated_at = now_beijing()
        db.add(message)
        self._touch_conversation(db, message.conversation_id)
        db.commit()
        db.refresh(message)
        return message

    def cancel_assistant_message(
        self,
        db: Session,
        user_id: int,
        assistant_message_id: int,
    ) -> Message:
        message = self.get_assistant_or_raise_for_user(
            db=db,
            user_id=user_id,
            assistant_message_id=assistant_message_id,
        )

        if message.status == "cancelled":
            return message
        if message.status not in self.MUTABLE_STATUSES:
            raise BusinessException(
                code=40944,
                message=f"message status {message.status} cannot be cancelled",
                status_code=409,
            )

        message.status = "cancelled"
        message.error_code = None
        message.error_message = None
        message.updated_at = now_beijing()
        db.add(message)
        self._touch_conversation(db, message.conversation_id)
        db.commit()
        db.refresh(message)
        return message

    def is_assistant_cancelled(
        self,
        db: Session,
        user_id: int,
        assistant_message_id: int,
    ) -> bool:
        message = self.get_assistant_or_raise_for_user(
            db=db,
            user_id=user_id,
            assistant_message_id=assistant_message_id,
        )
        return message.status == "cancelled"

    def create_debug_for_conversation(
        self,
        db: Session,
        user_id: int,
        conversation_id: int,
        payload: MessageCreate,
    ) -> Message:
        return self.create_for_conversation(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
            role=payload.role.value,
            content=payload.content,
            message_type=payload.message_type,
            status="completed",
        )

    def _touch_conversation(
        self,
        db: Session,
        conversation_id: int,
    ) -> None:
        conversation = db.get(Conversation, conversation_id)
        if conversation:
            conversation.updated_at = now_beijing()
            db.add(conversation)


message_service = MessageService()
