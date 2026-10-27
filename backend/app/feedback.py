"""Turn a rule-based report into plain-language coaching notes.

Claude writes the notes when an API key is configured. The numbers always come
from the rule engine; Claude only explains them. Without a key (or if the call
fails) a deterministic summary is used so the app keeps working.
"""

from __future__ import annotations

import logging
import os

import anthropic

from .schemas import ExerciseReport, Status

logger = logging.getLogger(__name__)

MODEL = os.environ.get("PERFECTMOVE_FEEDBACK_MODEL", "claude-opus-5-5")

SYSTEM = """You are a friendly, precise strength coach reviewing an exercise video that was \
analyzed by a pose-estimation program. You get its measurements as JSON.

Write short feedback for the athlete:
- Start with one sentence on the overall result.
- Then a "What went well" list and a "What to fix" list, most important fix first.
- For each fix give one concrete cue they can use on the next set.
- Only use facts from the JSON. Do not invent measurements or diagnose injuries. If the \
camera view limited what could be checked, say so briefly.
- Plain text with simple "-" bullets, under 180 words."""


def fallback_feedback(report: ExerciseReport) -> str:
    good = [c for c in report.checks if c.status == Status.PASS]
    bad = [c for c in report.checks if c.status != Status.PASS]
    lines = [f"You did {report.rep_count} rep(s) and scored {report.score}/100."]
    if good:
        lines += ["", "What went well:"] + [f"- {c.title}: {c.detail}" for c in good]
    if bad:
        lines += ["", "What to fix:"] + [f"- {c.title}: {c.detail} {c.tip}" for c in bad]
    lines += [""] + [f"Note: {n}" for n in report.notes]
    return "\n".join(lines).strip()


def generate_feedback(report: ExerciseReport) -> tuple[str, str]:
    """Returns (text, source) where source is 'claude' or 'rules'."""
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return fallback_feedback(report), "rules"
    try:
        client = anthropic.Anthropic()
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": report.model_dump_json(indent=2)}],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("model declined the request")
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if not text:
            raise RuntimeError("empty response")
        return text, "claude"
    except Exception:  # feedback is best-effort; never fail an analysis because of it
        logger.exception("Claude feedback failed; using rule-based summary")
        return fallback_feedback(report), "rules"
