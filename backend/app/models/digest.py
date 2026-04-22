from datetime import datetime
from typing import Optional
import uuid
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Digest(Base):
    __tablename__ = "digests"
    __table_args__ = {"schema": "auth"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("auth.users.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="processing")
    parameters: Mapped[dict] = mapped_column(JSONB)
    content: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    estimated_cost: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
