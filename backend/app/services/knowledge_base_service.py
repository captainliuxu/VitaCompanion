from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exception import BusinessException
from app.core.timezone import now_beijing
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate


class KnowledgeBaseService:
    def create_for_user(
        self,
        db: Session,
        user_id: int,
        payload: KnowledgeBaseCreate,
    ) -> KnowledgeBase:
        name = payload.name.strip()
        if not name:
            raise BusinessException(
                code=40091,
                message="knowledge base name cannot be empty",
                status_code=400,
            )

        item = KnowledgeBase(
            name=name,
            description=payload.description,
            status="active",
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def list_for_user(
        self,
        db: Session,
        user_id: int,
        include_archived: bool = False,
    ) -> list[KnowledgeBase]:
        stmt = select(KnowledgeBase)
        if not include_archived:
            stmt = stmt.where(KnowledgeBase.status == "active")

        stmt = stmt.order_by(KnowledgeBase.updated_at.desc(), KnowledgeBase.id.desc())
        return list(db.scalars(stmt).all())

    def get_or_raise(
        self,
        db: Session,
        user_id: int,
        knowledge_base_id: int,
    ) -> KnowledgeBase:
        item = db.scalar(
            select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
        )
        if not item:
            raise BusinessException(
                code=40491,
                message="knowledge base not found",
                status_code=404,
            )
        return item

    def get_default_active(self, db: Session) -> KnowledgeBase | None:
        return db.scalar(
            select(KnowledgeBase)
            .where(KnowledgeBase.status == "active")
            .order_by(KnowledgeBase.id.asc())
        )

    def update_for_user(
        self,
        db: Session,
        user_id: int,
        knowledge_base_id: int,
        payload: KnowledgeBaseUpdate,
    ) -> KnowledgeBase:
        item = self.get_or_raise(db, user_id, knowledge_base_id)
        update_data = payload.model_dump(exclude_unset=True)

        if "name" in update_data and update_data["name"] is not None:
            name = update_data["name"].strip()
            if not name:
                raise BusinessException(
                    code=40091,
                    message="knowledge base name cannot be empty",
                    status_code=400,
                )
            item.name = name

        if "description" in update_data:
            item.description = update_data["description"]

        if "status" in update_data and update_data["status"] is not None:
            item.status = update_data["status"].value

        item.updated_at = now_beijing()
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def delete_for_user(
        self,
        db: Session,
        user_id: int,
        knowledge_base_id: int,
    ) -> None:
        item = self.get_or_raise(db, user_id, knowledge_base_id)
        db.execute(
            delete(KnowledgeChunk).where(
                KnowledgeChunk.knowledge_base_id == knowledge_base_id
            )
        )
        db.execute(
            delete(KnowledgeDocument).where(
                KnowledgeDocument.knowledge_base_id == knowledge_base_id
            )
        )
        db.delete(item)
        db.commit()


knowledge_base_service = KnowledgeBaseService()
