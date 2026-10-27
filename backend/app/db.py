from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from . import config
from .schemas import AnalysisOut, AnalysisResult, AnalysisState


class Base(DeclarativeBase):
    pass


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    exercise: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(16), default=AnalysisState.PROCESSING.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    result_json: Mapped[str | None] = mapped_column(Text, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)

    def to_out(self) -> AnalysisOut:
        return AnalysisOut(
            id=self.id,
            exercise=self.exercise,
            status=AnalysisState(self.state),
            created_at=self.created_at,
            result=AnalysisResult.model_validate(json.loads(self.result_json)) if self.result_json else None,
            error=self.error,
        )


def make_session_factory(url: str | None = None) -> sessionmaker[Session]:
    url = url or config.DATABASE_URL
    if url.startswith("sqlite"):
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool  # one shared connection, or each would see an empty database
    engine = create_engine(url, **kwargs)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
