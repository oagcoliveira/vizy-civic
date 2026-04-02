from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Legislature(Base):
    __tablename__ = "legislatures"
    __table_args__ = {"schema": "core"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    chamber: Mapped[str] = mapped_column(String(10))  # 'camara' or 'senado'


class Party(Base):
    __tablename__ = "parties"
    __table_args__ = {"schema": "core"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    acronym: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    ideology: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    politicians: Mapped[list["Politician"]] = relationship(back_populates="party")


class Politician(Base):
    __tablename__ = "politicians"
    __table_args__ = (
        UniqueConstraint("source", "external_id"),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(10))  # 'camara' or 'senado'
    external_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cpf: Mapped[Optional[str]] = mapped_column(String(14), nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    education: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    party_id: Mapped[Optional[int]] = mapped_column(ForeignKey("core.parties.id"), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    current_office: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    current_legislature_id: Mapped[Optional[int]] = mapped_column(ForeignKey("core.legislatures.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    party: Mapped[Optional[Party]] = relationship(back_populates="politicians")
    votes: Mapped[list["IndividualVote"]] = relationship(back_populates="politician")
    speeches: Mapped[list["Speech"]] = relationship(back_populates="politician")


class Bill(Base):
    __tablename__ = "bills"
    __table_args__ = (
        UniqueConstraint("source", "external_id"),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(10))
    external_id: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(10))  # PL, PEC, MPV, PDL
    number: Mapped[int] = mapped_column(Integer)
    year: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    short_title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_text_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author_politician_id: Mapped[Optional[int]] = mapped_column(ForeignKey("core.politicians.id"), nullable=True)
    author_label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    policy_area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    policy_tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    is_controversial: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    legislature_id: Mapped[Optional[int]] = mapped_column(ForeignKey("core.legislatures.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Votacao(Base):
    __tablename__ = "votacoes"
    __table_args__ = (
        UniqueConstraint("source", "external_id"),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(10))
    external_id: Mapped[str] = mapped_column(String(100))
    bill_id: Mapped[Optional[int]] = mapped_column(ForeignKey("core.bills.id"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    vote_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    yes_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    no_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    abstention_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    session_label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    legislature_id: Mapped[Optional[int]] = mapped_column(ForeignKey("core.legislatures.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    individual_votes: Mapped[list["IndividualVote"]] = relationship(back_populates="votacao")


class IndividualVote(Base):
    __tablename__ = "individual_votes"
    __table_args__ = (
        UniqueConstraint("votacao_id", "politician_id"),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    votacao_id: Mapped[int] = mapped_column(ForeignKey("core.votacoes.id"))
    politician_id: Mapped[int] = mapped_column(ForeignKey("core.politicians.id"))
    vote: Mapped[str] = mapped_column(String(20))  # Sim, Não, Abstenção, Obstrução, Artigo 17
    party_at_time: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    party_orientation: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    followed_orientation: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    votacao: Mapped[Votacao] = relationship(back_populates="individual_votes")
    politician: Mapped[Politician] = relationship(back_populates="votes")


class Speech(Base):
    __tablename__ = "speeches"
    __table_args__ = (
        UniqueConstraint("source", "external_id"),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(10))
    external_id: Mapped[str] = mapped_column(String(100))
    politician_id: Mapped[int] = mapped_column(ForeignKey("core.politicians.id"))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    phase: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_text_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    keywords: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    policy_tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    sentiment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    politician: Mapped[Politician] = relationship(back_populates="speeches")
