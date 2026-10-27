import numpy as np
import pytest

from app.analysis.squat import AnalysisError, analyze_squat, find_reps
from app.schemas import Status

from .synthetic import FPS, front_squat, side_squat


def status(report, check_id):
    return next(c.status for c in report.checks if c.id == check_id)


def test_find_reps_counts_and_orders():
    h = np.concatenate([np.ones(10), np.linspace(1, 0.5, 8), np.linspace(0.5, 1, 8), np.ones(5)] * 2)
    reps = find_reps(h)
    assert len(reps) == 2
    for start, bottom, end in reps:
        assert start < bottom < end


def test_good_side_squat_passes():
    r = analyze_squat(side_squat())
    assert r.camera_view == "side"
    assert r.rep_count == 3
    assert r.score >= 90, [(c.id, c.status, c.detail) for c in r.checks]
    assert all(c.status == Status.PASS for c in r.checks)


def test_shallow_squat_fails_depth():
    r = analyze_squat(side_squat(depth=0.55))
    assert status(r, "depth") == Status.FAIL
    assert r.score < 80


def test_forward_lean_flagged():
    r = analyze_squat(side_squat(lean_deg=75))
    assert status(r, "torso_lean") != Status.PASS


def test_heel_lift_flagged():
    r = analyze_squat(side_squat(heel_lift=0.12))
    assert status(r, "heels") != Status.PASS


def test_dropping_too_fast_flagged():
    r = analyze_squat(side_squat(down_s=0.3))
    assert status(r, "tempo") != Status.PASS


def test_good_front_squat_passes():
    r = analyze_squat(front_squat())
    assert r.camera_view == "front"
    assert r.rep_count == 3
    assert all(c.status == Status.PASS for c in r.checks), [(c.id, c.detail) for c in r.checks]


def test_knee_valgus_flagged_in_front_view():
    r = analyze_squat(front_squat(valgus=1.0))
    assert status(r, "knee_tracking") != Status.PASS


def test_weight_shift_flagged_in_front_view():
    r = analyze_squat(front_squat(shift=1.0))
    assert status(r, "weight_shift") != Status.PASS


def test_rep_timing_is_reported():
    r = analyze_squat(side_squat(n_reps=2, down_s=2.0))
    assert 1.5 < r.reps[0].metrics["descent_s"] < 2.6
    assert r.reps[0].start_s < r.reps[0].bottom_s < r.reps[0].end_s


def test_standing_still_has_no_reps():
    seq = side_squat(n_reps=0)
    seq = type(seq)(times=np.arange(60) / FPS, landmarks=np.repeat(seq.landmarks[:1], 60, axis=0),
                    width=1000, height=1000)
    with pytest.raises(AnalysisError, match="any squat reps"):
        analyze_squat(seq)


def test_person_missing_raises():
    seq = side_squat()
    seq.landmarks[:] = np.nan
    with pytest.raises(AnalysisError, match="see you"):
        analyze_squat(seq)
