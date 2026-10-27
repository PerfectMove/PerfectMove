# Build context is assembled by .github/workflows/deploy-hf.yml:
# the contents of backend/ plus this Dockerfile at the repo root.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends libegl1 libgles2 libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

# Spaces run as uid 1000
RUN useradd -m -u 1000 user
USER user
ENV PATH=/home/user/.local/bin:$PATH \
    PERFECTMOVE_DATA_DIR=/home/user/data
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user app ./app

# Fetch the pose model at build time so the first request is fast
RUN mkdir -p /home/user/data \
 && python -c "from pathlib import Path; from app.pose import ensure_model; ensure_model(Path('/home/user/data/pose_landmarker_full.task'))"

EXPOSE 7860
CMD ["uvicorn", "app.main:app_factory", "--factory", "--host", "0.0.0.0", "--port", "7860"]
