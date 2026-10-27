"""Synthetic keypoint generators so the rules can be tested without video."""

from __future__ import annotations

import numpy as np

from app.pose import LM, NUM_LANDMARKS, PoseSequence

FPS = 15
L = 250.0  # thigh and shank length in px


def _profile(n_reps: int, down_s: float, up_s: float, hold_s: float = 1.0) -> np.ndarray:
    """Squat depth fraction d(t) in [0, 1] sampled at FPS."""
    parts = [np.zeros(int(hold_s * FPS))]
    for _ in range(n_reps):
        down = np.linspace(0, np.pi, max(2, int(down_s * FPS)))
        up = np.linspace(np.pi, 2 * np.pi, max(2, int(up_s * FPS)))
        parts += [(1 - np.cos(down)) / 2, (1 - np.cos(up)) / 2, np.zeros(int(hold_s * FPS))]
    return np.concatenate(parts)


def _sequence(frames: list[np.ndarray]) -> PoseSequence:
    return PoseSequence(
        times=np.arange(len(frames)) / FPS,
        landmarks=np.stack(frames),
        width=1000,
        height=1000,
    )


def side_squat(n_reps=3, depth=1.0, down_s=1.5, up_s=1.2, lean_deg=30.0, heel_lift=0.0,
               lockout_knee_bend=0.0) -> PoseSequence:
    frames = []
    for d in _profile(n_reps, down_s, up_s) * depth:
        hip = np.array([500.0 - 150 * d, 900 - (500 - 280 * d)])
        if lockout_knee_bend and d == 0:
            hip = np.array([500.0 - 40, 900 - 480.0])
        ankle = np.array([500.0, 900.0])
        u = hip - ankle
        dist = np.linalg.norm(u)
        u = u / dist
        h = np.sqrt(max(L**2 - (dist / 2) ** 2, 0))
        perp = np.array([-u[1], u[0]]) * np.sign(-u[1] * 0 + 1)
        if perp[0] < 0:
            perp = -perp
        knee = ankle + u * dist / 2 + perp * h
        lean = np.radians(lean_deg * (0.3 + 0.7 * d))
        shoulder = hip + 300 * np.array([np.sin(lean), -np.cos(lean)])
        heel = ankle + np.array([-40.0, 30.0 - heel_lift * 500 * d])
        pts = np.zeros((NUM_LANDMARKS, 3))
        pts[:, 2] = 0.99
        for side in ("LEFT", "RIGHT"):
            pts[LM[f"{side}_SHOULDER"], :2] = shoulder
            pts[LM[f"{side}_HIP"], :2] = hip
            pts[LM[f"{side}_KNEE"], :2] = knee
            pts[LM[f"{side}_ANKLE"], :2] = ankle
            pts[LM[f"{side}_HEEL"], :2] = heel
            pts[LM[f"{side}_FOOT_INDEX"], :2] = ankle + [60, 30]
        pts[LM.NOSE, :2] = shoulder + [10, -60]
        frames.append(pts)
    return _sequence(frames)


def front_squat(n_reps=3, depth=1.0, down_s=1.5, up_s=1.2, valgus=0.0, shift=0.0) -> PoseSequence:
    frames = []
    for d in _profile(n_reps, down_s, up_s) * depth:
        cx = 500.0 + shift * 120 * d
        hip_y = 400 + 262 * d
        knee_half = 70 - valgus * 45 * d + 20 * d * (1 - valgus)
        pts = np.zeros((NUM_LANDMARKS, 3))
        pts[:, 2] = 0.99
        for sign, side in ((-1, "LEFT"), (1, "RIGHT")):
            pts[LM[f"{side}_SHOULDER"], :2] = [cx + sign * 100, hip_y - 300]
            pts[LM[f"{side}_HIP"], :2] = [cx + sign * 60, hip_y]
            pts[LM[f"{side}_KNEE"], :2] = [500 + sign * knee_half, 650]
            pts[LM[f"{side}_ANKLE"], :2] = [500 + sign * 80, 900]
            pts[LM[f"{side}_HEEL"], :2] = [500 + sign * 80, 920]
            pts[LM[f"{side}_FOOT_INDEX"], :2] = [500 + sign * 90, 930]
        pts[LM.NOSE, :2] = [cx, hip_y - 380]
        frames.append(pts)
    return _sequence(frames)
