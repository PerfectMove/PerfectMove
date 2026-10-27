from fastapi.testclient import TestClient

from app.db import make_session_factory
from app.feedback import fallback_feedback
from app.main import create_app

from .synthetic import side_squat


def make_client(extractor):
    app = create_app(
        session_factory=make_session_factory("sqlite://"),
        pose_extractor=extractor,
        feedback_fn=lambda report: (fallback_feedback(report), "rules"),
    )
    return TestClient(app)


def upload(client, exercise="squat"):
    return client.post("/analyses", files={"video": ("a.mp4", b"fake", "video/mp4")}, data={"exercise": exercise})


def test_full_flow():
    client = make_client(lambda path: side_squat())
    created = upload(client)
    assert created.status_code == 202
    body = client.get(f"/analyses/{created.json()['id']}").json()
    assert body["status"] == "done"
    assert body["result"]["report"]["rep_count"] == 3
    assert body["result"]["feedback_source"] == "rules"
    assert "What went well" in body["result"]["feedback"]


def test_unusable_video_reports_friendly_error():
    def bad(path):
        raise ValueError("Could not open the video file")

    client = make_client(bad)
    body = client.get(f"/analyses/{upload(client).json()['id']}").json()
    assert body["status"] == "failed"
    assert body["error"] == "Could not open the video file"


def test_unknown_exercise_and_missing_analysis():
    client = make_client(lambda p: side_squat())
    assert upload(client, "burpee").status_code == 422
    assert client.get("/analyses/nope").status_code == 404


def test_exercise_list():
    client = make_client(lambda p: side_squat())
    assert client.get("/exercises").json()[0]["id"] == "squat"
