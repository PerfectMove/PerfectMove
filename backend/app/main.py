from __future__ import annotations

import logging
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, sessionmaker

from . import config
from .analysis.registry import EXERCISES
from .analysis.squat import AnalysisError
from .db import Analysis, make_session_factory
from .feedback import generate_feedback
from .pose import PoseSequence, extract_pose
from .schemas import AnalysisOut, AnalysisResult, AnalysisState, ExerciseInfo

logger = logging.getLogger(__name__)

PoseExtractor = Callable[[Path], PoseSequence]


def _default_extractor(video: Path) -> PoseSequence:
    return extract_pose(video, config.MODEL_PATH)


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    pose_extractor: PoseExtractor = _default_extractor,
    feedback_fn=generate_feedback,
) -> FastAPI:
    app = FastAPI(title="PerfectMove API")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    sessions = session_factory or make_session_factory()

    def db():
        with sessions() as s:
            yield s

    def run_analysis(analysis_id: str, video: Path) -> None:
        with sessions() as s:
            row = s.get(Analysis, analysis_id)
            try:
                seq = pose_extractor(video)
                report = EXERCISES[row.exercise].analyze(seq)
                text, source = feedback_fn(report)
                row.result_json = AnalysisResult(
                    report=report, feedback=text, feedback_source=source
                ).model_dump_json()
                row.state = AnalysisState.DONE.value
            except (AnalysisError, ValueError) as e:
                row.state, row.error = AnalysisState.FAILED.value, str(e)
            except Exception:
                logger.exception("Analysis %s crashed", analysis_id)
                row.state = AnalysisState.FAILED.value
                row.error = "Something went wrong while analyzing the video. Please try again."
            finally:
                s.commit()
                video.unlink(missing_ok=True)  # raw footage is not kept

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/exercises", response_model=list[ExerciseInfo])
    def exercises():
        return [ExerciseInfo(id=e.id, name=e.name, filming_tips=e.filming_tips) for e in EXERCISES.values()]

    @app.post("/analyses", response_model=AnalysisOut, status_code=202)
    async def create_analysis(
        background: BackgroundTasks,
        video: UploadFile = File(...),
        exercise: str = Form("squat"),
        s: Session = Depends(db),
    ):
        if exercise not in EXERCISES:
            raise HTTPException(422, f"Unknown exercise '{exercise}'")
        suffix = Path(video.filename or "").suffix or ".mp4"
        limit = config.MAX_UPLOAD_MB * 1024 * 1024
        size = 0
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            while chunk := await video.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    Path(tmp.name).unlink(missing_ok=True)
                    raise HTTPException(413, f"Video is larger than {config.MAX_UPLOAD_MB} MB")
                tmp.write(chunk)
        row = Analysis(id=uuid.uuid4().hex, exercise=exercise)
        s.add(row)
        s.commit()
        background.add_task(run_analysis, row.id, Path(tmp.name))
        return row.to_out()

    @app.get("/analyses/{analysis_id}", response_model=AnalysisOut)
    def get_analysis(analysis_id: str, s: Session = Depends(db)):
        row = s.get(Analysis, analysis_id)
        if not row:
            raise HTTPException(404, "Analysis not found")
        return row.to_out()

    return app


def app_factory() -> FastAPI:
    return create_app()
