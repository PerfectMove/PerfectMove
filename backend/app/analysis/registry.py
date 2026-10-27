"""Registry of supported exercises. Add a new exercise by adding an entry here."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..pose import PoseSequence
from ..schemas import ExerciseReport
from .squat import analyze_squat


@dataclass(frozen=True)
class Exercise:
    id: str
    name: str
    filming_tips: list[str]
    analyze: Callable[[PoseSequence], ExerciseReport]


EXERCISES: dict[str, Exercise] = {
    "squat": Exercise(
        id="squat",
        name="Bodyweight squat",
        filming_tips=[
            "Place the phone at hip height, about 2–3 m away, and keep it still.",
            "Film from the side for depth, torso and heels, or from the front for knee tracking.",
            "Keep your whole body, head to feet, in the frame with good lighting.",
            "Do 3–5 reps, standing fully tall between reps.",
        ],
        analyze=analyze_squat,
    ),
}
