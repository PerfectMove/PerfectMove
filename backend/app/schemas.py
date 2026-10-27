from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Status(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class Check(BaseModel):
    id: str
    title: str
    status: Status
    detail: str = Field(description="What we measured, in plain language")
    tip: str | None = Field(default=None, description="How to fix it, when not passing")
    reps_affected: list[int] = Field(default_factory=list, description="1-based rep numbers")


class Rep(BaseModel):
    number: int
    start_s: float
    bottom_s: float
    end_s: float
    metrics: dict[str, float]


class ExerciseReport(BaseModel):
    exercise: str
    camera_view: Literal["side", "front"]
    rep_count: int
    score: int = Field(ge=0, le=100)
    checks: list[Check]
    reps: list[Rep]
    notes: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    report: ExerciseReport
    feedback: str
    feedback_source: Literal["claude", "rules"]


class AnalysisState(str, Enum):
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class AnalysisOut(BaseModel):
    id: str
    exercise: str
    status: AnalysisState
    created_at: datetime
    result: AnalysisResult | None = None
    error: str | None = None


class ExerciseInfo(BaseModel):
    id: str
    name: str
    filming_tips: list[str]
