"""Rule-based bodyweight squat analysis.

Works on 2D keypoints from a single phone camera. A side view gives depth,
torso lean, heel contact, lockout and tempo; a front view gives depth, knee
tracking, weight shift and tempo. The view is detected automatically.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from ..pose import LM, PoseSequence
from ..schemas import Check, ExerciseReport, Rep, Status
from .geometry import angle_from_vertical, distance, joint_angle, smooth

# Hip height relative to standing (1.0 = standing tall). A rep starts after the
# lifter was above TOP and dips below DOWN, and ends when back above TOP.
TOP = 0.93
DOWN = 0.85

MIN_PRESENT_FRACTION = 0.6
FRONT_VIEW_RATIO = 0.4

CREDIT = {Status.PASS: 1.0, Status.WARN: 0.5, Status.FAIL: 0.0}


class AnalysisError(ValueError):
    """Raised with a message that can be shown to the user."""


@dataclass
class Tracks:
    times: np.ndarray
    view: str
    hip: np.ndarray
    knee: np.ndarray
    ankle: np.ndarray
    shoulder: np.ndarray
    heel: np.ndarray
    left_knee: np.ndarray
    right_knee: np.ndarray
    left_ankle: np.ndarray
    right_ankle: np.ndarray
    left_hip: np.ndarray
    right_hip: np.ndarray


def _track(seq: PoseSequence, lm: LM, window: int) -> np.ndarray:
    p = seq.point(lm)
    return np.stack([smooth(p[:, 0], window), smooth(p[:, 1], window)], axis=1)


def _mid(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a + b) / 2


def _detect_view(seq: PoseSequence) -> str:
    ls, rs = seq.point(LM.LEFT_SHOULDER), seq.point(LM.RIGHT_SHOULDER)
    lh, rh = seq.point(LM.LEFT_HIP), seq.point(LM.RIGHT_HIP)
    widths = (np.abs(ls[:, 0] - rs[:, 0]) + np.abs(lh[:, 0] - rh[:, 0])) / 2
    torso = distance(_mid(ls, rs), _mid(lh, rh))
    ratio = np.nanmedian(widths / torso)
    return "front" if ratio > FRONT_VIEW_RATIO else "side"


def _build_tracks(seq: PoseSequence) -> Tracks:
    window = max(3, int(round(0.2 * _frame_rate(seq))) | 1)
    t = {lm: _track(seq, lm, window) for lm in LM}
    view = _detect_view(seq)

    if view == "side":
        # Use the side facing the camera: its joints are seen more confidently.
        left_vis = np.nanmean([seq.visibility(lm) for lm in (LM.LEFT_HIP, LM.LEFT_KNEE, LM.LEFT_ANKLE)])
        right_vis = np.nanmean([seq.visibility(lm) for lm in (LM.RIGHT_HIP, LM.RIGHT_KNEE, LM.RIGHT_ANKLE)])
        if left_vis >= right_vis:
            hip, knee, ankle, shoulder, heel = (
                t[LM.LEFT_HIP], t[LM.LEFT_KNEE], t[LM.LEFT_ANKLE], t[LM.LEFT_SHOULDER], t[LM.LEFT_HEEL])
        else:
            hip, knee, ankle, shoulder, heel = (
                t[LM.RIGHT_HIP], t[LM.RIGHT_KNEE], t[LM.RIGHT_ANKLE], t[LM.RIGHT_SHOULDER], t[LM.RIGHT_HEEL])
    else:
        hip = _mid(t[LM.LEFT_HIP], t[LM.RIGHT_HIP])
        knee = _mid(t[LM.LEFT_KNEE], t[LM.RIGHT_KNEE])
        ankle = _mid(t[LM.LEFT_ANKLE], t[LM.RIGHT_ANKLE])
        shoulder = _mid(t[LM.LEFT_SHOULDER], t[LM.RIGHT_SHOULDER])
        heel = _mid(t[LM.LEFT_HEEL], t[LM.RIGHT_HEEL])

    return Tracks(
        times=seq.times, view=view, hip=hip, knee=knee, ankle=ankle, shoulder=shoulder, heel=heel,
        left_knee=t[LM.LEFT_KNEE], right_knee=t[LM.RIGHT_KNEE],
        left_ankle=t[LM.LEFT_ANKLE], right_ankle=t[LM.RIGHT_ANKLE],
        left_hip=t[LM.LEFT_HIP], right_hip=t[LM.RIGHT_HIP],
    )


def _frame_rate(seq: PoseSequence) -> float:
    if len(seq) < 2:
        return 15.0
    return 1.0 / float(np.median(np.diff(seq.times)))


def find_reps(height: np.ndarray) -> list[tuple[int, int, int]]:
    """Split a normalized hip-height signal into (start, bottom, end) frame indices."""
    reps: list[tuple[int, int, int]] = []
    last_top: int | None = None
    start: int | None = None
    for i, v in enumerate(height):
        if start is None:
            if v >= TOP:
                last_top = i
            elif v < DOWN and last_top is not None:
                start = last_top
        elif v >= TOP:
            bottom = start + int(np.argmin(height[start : i + 1]))
            reps.append((start, bottom, i))
            start = None
            last_top = i
    return reps


def _grade(value: float, pass_at: float, warn_at: float, higher_is_better: bool) -> Status:
    if higher_is_better:
        return Status.PASS if value >= pass_at else Status.WARN if value >= warn_at else Status.FAIL
    return Status.PASS if value <= pass_at else Status.WARN if value <= warn_at else Status.FAIL


def _overall(statuses: list[Status]) -> Status:
    fails = sum(s == Status.FAIL for s in statuses)
    if fails and fails * 2 >= len(statuses):
        return Status.FAIL
    if any(s != Status.PASS for s in statuses):
        return Status.WARN
    return Status.PASS


@dataclass
class Rule:
    id: str
    title: str
    weight: float
    views: tuple[str, ...]
    metric: str
    pass_at: float
    warn_at: float
    higher_is_better: bool
    describe: Callable[[float], str]
    tip: str


RULES = [
    Rule(
        id="depth", title="Squat depth", weight=30, views=("side", "front"),
        metric="depth", pass_at=-0.05, warn_at=-0.25, higher_is_better=True,
        describe=lambda v: (
            "Your hips reached knee level or below." if v >= -0.05
            else f"Your hips stopped about {abs(v) * 100:.0f}% of a thigh length above your knees."
        ),
        tip="Sit down until the crease of your hips is level with or below your knees, "
            "as long as your back stays neutral.",
    ),
    Rule(
        id="torso_lean", title="Chest up", weight=20, views=("side",),
        metric="torso_lean_deg", pass_at=50, warn_at=60, higher_is_better=False,
        describe=lambda v: f"Your torso leaned up to {v:.0f}° forward from vertical.",
        tip="Keep your chest proud and brace your core. Sitting the hips back and down, "
            "rather than folding forward, keeps the torso more upright.",
    ),
    Rule(
        id="heels", title="Heels stay down", weight=15, views=("side",),
        metric="heel_lift", pass_at=0.03, warn_at=0.06, higher_is_better=False,
        describe=lambda v: (
            "Your heels stayed planted." if v <= 0.03
            else "Your heels came off the floor during the squat."
        ),
        tip="Push through your whole foot and keep your heels down. If they still lift, "
            "try a slightly wider stance with toes turned out, and work on ankle mobility.",
    ),
    Rule(
        id="lockout", title="Full lockout", weight=10, views=("side",),
        metric="top_knee_angle_deg", pass_at=160, warn_at=150, higher_is_better=True,
        describe=lambda v: f"At the top your knees opened to {v:.0f}° (180° is fully straight).",
        tip="Finish each rep by standing all the way up and squeezing your glutes.",
    ),
    Rule(
        id="knee_tracking", title="Knees track over toes", weight=25, views=("front",),
        metric="knee_ankle_width_ratio", pass_at=0.9, warn_at=0.75, higher_is_better=True,
        describe=lambda v: (
            "Your knees stayed in line with your feet." if v >= 0.9
            else f"Your knees moved inward, to {v * 100:.0f}% of your foot width at the bottom."
        ),
        tip="Push your knees out so they point the same way as your toes all the way down and up.",
    ),
    Rule(
        id="weight_shift", title="Even weight on both legs", weight=10, views=("front",),
        metric="hip_shift", pass_at=0.15, warn_at=0.3, higher_is_better=False,
        describe=lambda v: (
            "Your hips stayed centered." if v <= 0.15
            else f"Your hips shifted to one side by {v * 100:.0f}% of hip width."
        ),
        tip="Keep your weight even on both feet; check for a tight hip or ankle on the side you drift away from.",
    ),
    Rule(
        id="tempo", title="Controlled descent", weight=15, views=("side", "front"),
        metric="descent_s", pass_at=0.7, warn_at=0.45, higher_is_better=True,
        describe=lambda v: f"Lowering took about {v:.1f} s.",
        tip="Lower yourself under control, taking about 1–2 seconds on the way down, "
            "instead of dropping into the bottom.",
    ),
]


def _rep_metrics(tr: Tracks, start: int, bottom: int, end: int, next_start: int,
                 standing: np.ndarray, leg: float, thigh: float) -> dict[str, float]:
    sl = slice(start, end + 1)
    m: dict[str, float] = {
        "descent_s": float(tr.times[bottom] - tr.times[start]),
        "ascent_s": float(tr.times[end] - tr.times[bottom]),
        # Positive when the hip is below the knee (image y grows downward).
        "depth": float((tr.hip[bottom, 1] - tr.knee[bottom, 1]) / thigh),
    }
    if tr.view == "side":
        knee_angle = joint_angle(tr.hip, tr.knee, tr.ankle)
        m["min_knee_angle_deg"] = float(knee_angle[bottom])
        m["torso_lean_deg"] = float(np.max(angle_from_vertical(tr.shoulder[sl], tr.hip[sl])))
        heel_base = float(np.median(tr.heel[standing, 1]))
        m["heel_lift"] = float(max(0.0, np.max(heel_base - tr.heel[sl, 1]) / leg))
        top = slice(end, max(end + 1, next_start))
        m["top_knee_angle_deg"] = float(np.max(knee_angle[top]))
    else:
        knee_w = abs(tr.left_knee[bottom, 0] - tr.right_knee[bottom, 0])
        ankle_w = abs(tr.left_ankle[bottom, 0] - tr.right_ankle[bottom, 0])
        hip_w = float(np.median(np.abs(tr.left_hip[standing, 0] - tr.right_hip[standing, 0])))
        if ankle_w > 0.3 * hip_w:
            m["knee_ankle_width_ratio"] = float(knee_w / ankle_w)
        offset = tr.hip[:, 0] - tr.ankle[:, 0]
        m["hip_shift"] = float(abs(offset[bottom] - np.median(offset[standing])) / hip_w)
    return m


def analyze_squat(seq: PoseSequence) -> ExerciseReport:
    if len(seq) < 10:
        raise AnalysisError("The video is too short. Record at least a few full reps.")

    present = ~np.isnan(seq.landmarks[:, LM.LEFT_HIP, 0])
    if present.mean() < MIN_PRESENT_FRACTION:
        raise AnalysisError(
            "We couldn't see you clearly in most of the video. Make sure your whole body, "
            "head to feet, is in the frame and well lit."
        )

    tr = _build_tracks(seq)
    extent = tr.ankle[:, 1] - tr.hip[:, 1]
    leg = float(np.percentile(extent, 90))
    if leg <= 0:
        raise AnalysisError("We couldn't find your legs in the video. Keep your feet in the frame.")
    height = extent / leg

    reps = find_reps(height)
    if not reps:
        raise AnalysisError(
            "We didn't find any squat reps. Stand tall at the start, squat down, and stand "
            "all the way back up between reps."
        )

    standing = height >= TOP
    thigh = float(np.median(distance(tr.hip[standing], tr.knee[standing])))

    rep_models: list[Rep] = []
    for n, (start, bottom, end) in enumerate(reps):
        next_start = reps[n + 1][0] if n + 1 < len(reps) else len(height)
        metrics = _rep_metrics(tr, start, bottom, end, next_start, standing, leg, thigh)
        rep_models.append(Rep(
            number=n + 1,
            start_s=round(float(tr.times[start]), 2),
            bottom_s=round(float(tr.times[bottom]), 2),
            end_s=round(float(tr.times[end]), 2),
            metrics={k: round(v, 3) for k, v in metrics.items()},
        ))

    checks: list[Check] = []
    weighted = 0.0
    total_weight = 0.0
    for rule in RULES:
        if tr.view not in rule.views:
            continue
        values = [(r.number, r.metrics[rule.metric]) for r in rep_models if rule.metric in r.metrics]
        if not values:
            continue
        statuses = [_grade(v, rule.pass_at, rule.warn_at, rule.higher_is_better) for _, v in values]
        status = _overall(statuses)
        nums = [v for _, v in values]
        typical = float(np.median(nums))
        worst = min(nums) if rule.higher_is_better else max(nums)
        shown = worst if status != Status.PASS else typical
        checks.append(Check(
            id=rule.id,
            title=rule.title,
            status=status,
            detail=rule.describe(shown),
            tip=None if status == Status.PASS else rule.tip,
            reps_affected=[num for (num, _), s in zip(values, statuses) if s != Status.PASS],
        ))
        weighted += rule.weight * float(np.mean([CREDIT[s] for s in statuses]))
        total_weight += rule.weight

    notes: list[str] = []
    if tr.view == "side":
        notes.append("Filmed from the side. Film from the front to also check whether your knees cave in.")
    else:
        notes.append("Filmed from the front. Film from the side to also check torso lean, heels and lockout.")
    if present.mean() < 0.9:
        notes.append("You were out of view in part of the video, so some measurements may be less accurate.")

    return ExerciseReport(
        exercise="squat",
        camera_view=tr.view,
        rep_count=len(rep_models),
        score=round(100 * weighted / total_weight) if total_weight else 0,
        checks=checks,
        reps=rep_models,
        notes=notes,
    )
