"""Vectorized geometry helpers. All inputs are (frames, 2) pixel arrays."""

from __future__ import annotations

import numpy as np


def joint_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Angle ABC in degrees at vertex B, per frame."""
    ba = a - b
    bc = c - b
    cos = np.sum(ba * bc, axis=-1) / (np.linalg.norm(ba, axis=-1) * np.linalg.norm(bc, axis=-1))
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))


def angle_from_vertical(top: np.ndarray, bottom: np.ndarray) -> np.ndarray:
    """Angle in degrees between the segment bottom->top and straight up."""
    d = top - bottom
    # Image y grows downward, so "up" is -y.
    return np.degrees(np.arctan2(np.abs(d[..., 0]), -d[..., 1]))


def distance(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.linalg.norm(a - b, axis=-1)


def interpolate_gaps(values: np.ndarray) -> np.ndarray:
    """Fill NaNs by linear interpolation (edges take the nearest valid value)."""
    values = np.asarray(values, dtype=float).copy()
    valid = ~np.isnan(values)
    if valid.sum() == 0:
        return values
    idx = np.arange(len(values))
    values[~valid] = np.interp(idx[~valid], idx[valid], values[valid])
    return values


def smooth(values: np.ndarray, window: int = 5) -> np.ndarray:
    """Centered moving average over a gap-filled series."""
    values = interpolate_gaps(values)
    if window <= 1 or len(values) < window:
        return values
    pad = window // 2
    padded = np.pad(values, pad, mode="edge")
    kernel = np.ones(window) / window
    return np.convolve(padded, kernel, mode="valid")[: len(values)]
