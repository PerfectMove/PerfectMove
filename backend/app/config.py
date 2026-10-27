import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("PERFECTMOVE_DATA_DIR", "data")).resolve()
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR}/perfectmove.db")
MODEL_PATH = Path(os.environ.get("PERFECTMOVE_POSE_MODEL", DATA_DIR / "pose_landmarker_full.task"))
MAX_UPLOAD_MB = int(os.environ.get("PERFECTMOVE_MAX_UPLOAD_MB", "200"))
