from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(300), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    digest_frequency: Mapped[str] = mapped_column(String(20), default="weekly")
    digest_day: Mapped[str] = mapped_column(String(10), default="friday")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class PoliticianFollow(Base):
    __tablename__ = "politician_follows"
    __table_args__ = (
        UniqueConstraint("user_id", "politician_id"),
        {"schema": "auth"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("auth.users.id"))
    politician_id: Mapped[int] = mapped_column(ForeignKey("core.politicians.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BillTrack(Base):
    __tablename__ = "bill_tracks"
    __table_args__ = (
        UniqueConstraint("user_id", "bill_id"),
        {"schema": "auth"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("auth.users.id"))
    bill_id: Mapped[int] = mapped_column(ForeignKey("core.bills.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TagFollow(Base):
    __tablename__ = "tag_follows"
    __table_args__ = (
        UniqueConstraint("user_id", "tag"),
        {"schema": "auth"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("auth.users.id"))
    tag: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
