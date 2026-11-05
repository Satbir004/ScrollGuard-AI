"""
Hand-to-phone proximity metric.

proximity = 1 - min(dist_from_any_hand_landmark_to_phone_center) / phone_diagonal

  1.0 → landmark exactly at phone center (hand touching phone)
  0.0 → landmark one phone-diagonal away (clearly not holding)

Capped at [0.0, 1.0]. Higher = more likely to be holding the phone.

Phase 6 will use this to distinguish PHONE_ON_DESK from PHONE_PICKED_UP.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np

from .detector import Detection
from .hand_detector import HandInfo


def _phone_center_and_diagonal(det: Detection) -> tuple[float, float, float]:
    cx = (det.x1 + det.x2) / 2.0
    cy = (det.y1 + det.y2) / 2.0
    w = det.x2 - det.x1
    h = det.y2 - det.y1
    diag = float((w * w + h * h) ** 0.5)
    return cx, cy, max(diag, 1.0)


def hand_phone_proximity(
    hands: List[HandInfo],
    phone: Optional[Detection],
    frame_width: int,
    frame_height: int,
) -> float:
    """
    Return the highest proximity across all hands to the phone.
    Returns 0.0 if no phone or no hands.
    """
    if not hands or phone is None:
        return 0.0

    cx, cy, diag = _phone_center_and_diagonal(phone)

    best_prox = 0.0
    for hand in hands:
        # Use only the fingertip landmarks (4, 8, 12, 16, 20) — those
        # are what actually touch the phone when scrolling or tapping.
        fingertip_indices = {4, 8, 12, 16, 20}
        for i, (nx, ny, _nz) in enumerate(hand.landmarks):
            if i not in fingertip_indices:
                continue
            # Normalized coords → pixel coords
            px = nx * frame_width
            py = ny * frame_height
            if px <= 0 and py <= 0:
                continue
            dist = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
            prox = 1.0 - (dist / diag)
            if prox > best_prox:
                best_prox = prox

    return max(0.0, min(1.0, best_prox))


def nearest_hand_to_phone(
    hands: List[HandInfo],
    phone: Optional[Detection],
    frame_width: int,
    frame_height: int,
) -> Optional[HandInfo]:
    """Return the hand whose fingertips are closest to the phone center."""
    if not hands or phone is None:
        return None

    cx, cy, _ = _phone_center_and_diagonal(phone)
    best_hand: Optional[HandInfo] = None
    best_dist = float("inf")

    for hand in hands:
        for i in (4, 8, 12, 16, 20):
            if i >= len(hand.landmarks):
                continue
            nx, ny, _ = hand.landmarks[i]
            px = nx * frame_width
            py = ny * frame_height
            if px <= 0 and py <= 0:
                continue
            d = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
            if d < best_dist:
                best_dist = d
                best_hand = hand

    return best_hand