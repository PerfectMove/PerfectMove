# PerfectMove

Record an exercise, get a report of what you did right and what to fix.

The first version handles the **bodyweight squat** (filmed from the side or the front).

## How it works

1. The mobile app (Expo / React Native) records or picks a video and uploads it.
2. The backend (FastAPI) runs **MediaPipe Pose** on the frames to get body keypoints.
3. A **rule engine** (NumPy) finds each rep and measures joint angles, depth, knee tracking, heel contact and tempo, and grades each check pass / warn / fail.
4. **Claude** turns the measurements into short coaching notes. The numbers always come from the rules; Claude only explains them. Without an API key a rule-based summary is used.

Uploaded videos are deleted as soon as they are analyzed; only the report is stored.

### Squat checks

| Check | View | Rule |
|---|---|---|
| Depth | side, front | hip reaches knee level |
| Chest up | side | torso lean ≤ 50° from vertical (warn ≤ 60°) |
| Heels stay down | side | heel rise ≤ 3% of leg length |
| Full lockout | side | knee angle ≥ 160° at the top |
| Knees track over toes | front | knee width ≥ 90% of foot width at the bottom |
| Even weight | front | hip drift ≤ 15% of hip width |
| Controlled descent | both | lowering takes ≥ 0.7 s |

Thresholds live in `backend/app/analysis/squat.py` (`RULES`) and are starting points to tune with real footage.

## Run it

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # on Linux also: apt install libegl1 libgles2
export ANTHROPIC_API_KEY=...           # optional
uvicorn app.main:app_factory --factory --host 0.0.0.0 --port 8000
python -m pytest                       # tests use synthetic keypoints, no video needed
```

The pose model (~9 MB) is downloaded on first use. Data (SQLite by default; set `DATABASE_URL` for Postgres) goes in `backend/data/`.

API: `GET /exercises`, `POST /analyses` (multipart `video`, `exercise`), `GET /analyses/{id}`.

### Mobile

```bash
cd mobile
npm install
EXPO_PUBLIC_API_URL=http://<your-computer-LAN-IP>:8000 npx expo start
```

Open it in Expo Go on your phone.

### Deploy the backend to Hugging Face Spaces (free)

1. Create an account at huggingface.co, then **New Space** → SDK **Docker** (blank), hardware **CPU basic (free)**. Note the name, e.g. `yourname/perfectmove`.
2. In the Space → **Settings → Variables and secrets**, add a secret `ANTHROPIC_API_KEY` (optional; without it a rule-based summary is used).
3. Create an access token at huggingface.co/settings/tokens with **Write** permission.
4. In this GitHub repo → **Settings → Secrets and variables → Actions**: add secret `HF_TOKEN` (the token) and variable `HF_SPACE` (`yourname/perfectmove`).
5. Run the **Deploy backend to Hugging Face** workflow (or push to `main`). The first build takes a few minutes.
6. Your API is at `https://yourname-perfectmove.hf.space` (check `/health`). Start the app with `EXPO_PUBLIC_API_URL=https://yourname-perfectmove.hf.space npx expo start`.

The free Space sleeps when idle (first request wakes it up) and its disk is ephemeral, so stored reports are lost on restart.

## Adding an exercise

Write an `analyze_<exercise>(PoseSequence) -> ExerciseReport` function and register it in `backend/app/analysis/registry.py`. The app picks it up from `GET /exercises`.

## Not done yet

- Calibration against real footage (the squat thresholds are untested on video of people).
- Auth, S3 video storage, and a history screen.
- On-device pose detection (the video is uploaded for now).
