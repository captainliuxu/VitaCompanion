from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exception import BusinessException
from app.core.timezone import now_beijing
from app.models.user_memory import UserMemory
from app.schemas.user_memory import UserMemoryCreate, UserMemoryUpdate


class UserMemoryService:
    VALID_STATUSES = {"active", "archived"}

    def create_for_user(
        self,
        db: Session,
        user_id: int,
        payload: UserMemoryCreate,
    ) -> UserMemory:
        content = payload.content.strip()
        if not content:
            raise BusinessException(
                code=40071,
                message="memory content cannot be empty",
                status_code=400,
            )

        memory = UserMemory(
            user_id=user_id,
            content=content,
            memory_type=payload.memory_type.value,
            source=(payload.source.strip() if payload.source else None),
            importance=payload.importance,
            status="active",
        )
        db.add(memory)
        db.commit()
        db.refresh(memory)
        return memory

    def list_for_user(
        self,
        db: Session,
        user_id: int,
        include_archived: bool = False,
        limit: int | None = None,
    ) -> list[UserMemory]:
        stmt = select(UserMemory).where(UserMemory.user_id == user_id)
        if not include_archived:
            stmt = stmt.where(UserMemory.status == "active")

        stmt = stmt.order_by(
            UserMemory.importance.desc(),
            UserMemory.updated_at.desc(),
            UserMemory.id.desc(),
        )
        if limit is not None:
            stmt = stmt.limit(limit)

        return list(db.scalars(stmt).all())

    def get_or_raise(
        self,
        db: Session,
        user_id: int,
        memory_id: int,
    ) -> UserMemory:
        memory = db.scalar(
            select(UserMemory).where(
                UserMemory.id == memory_id,
                UserMemory.user_id == user_id,
            )
        )
        if not memory:
            raise BusinessException(
                code=40471,
                message="user memory not found",
                status_code=404,
            )
        return memory

    def update_for_user(
        self,
        db: Session,
        user_id: int,
        memory_id: int,
        payload: UserMemoryUpdate,
    ) -> UserMemory:
        memory = self.get_or_raise(db, user_id, memory_id)
        update_data = payload.model_dump(exclude_unset=True)

        if "content" in update_data and update_data["content"] is not None:
            content = update_data["content"].strip()
            if not content:
                raise BusinessException(
                    code=40071,
                    message="memory content cannot be empty",
                    status_code=400,
                )
            memory.content = content

        if "memory_type" in update_data and update_data["memory_type"] is not None:
            memory.memory_type = update_data["memory_type"].value

        if "source" in update_data:
            source = update_data["source"]
            memory.source = source.strip() if source else None

        if "importance" in update_data and update_data["importance"] is not None:
            memory.importance = update_data["importance"]

        if "status" in update_data and update_data["status"] is not None:
            memory.status = update_data["status"].value

        memory.updated_at = now_beijing()
        db.add(memory)
        db.commit()
        db.refresh(memory)
        return memory

    def delete_for_user(
        self,
        db: Session,
        user_id: int,
        memory_id: int,
    ) -> None:
        memory = self.get_or_raise(db, user_id, memory_id)
        db.delete(memory)
        db.commit()


user_memory_service = UserMemoryService()
