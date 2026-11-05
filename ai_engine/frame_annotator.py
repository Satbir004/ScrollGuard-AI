"""
Draws detection overlays onto frames. Kept separate so we can change
visual style without touching the pipeline.
"""

from __future__ import annotations

from typing import List

import cv2
import numpy as np

from .phone_tracker import Track


# Palette matching config.json
COLOR_PHONE       = (0, 220, 255)   # cyan (BGR)
COLOR_TRACK_TEXT  = (255, 255, 255)
COLOR_BG          = (11, 16, 32)    # #0B1020


def draw_tracks(
    frame: np.ndarray,
    tracks: List[Track],
    show_ids: bool = True,
) -> np.ndarray:
    """Return a copy of frame with phone tracks drawn."""
    out = frame.copy()
    for track in tracks:
        d = track.detection
        x1, y1, x2, y2 = d.x1, d.y1, d.x2, d.y2

        # Box
        cv2.rectangle(out, (x1, y1), (x2, y2), COLOR_PHONE, 2)

        # Corner accents for a modern look
        corner = 14
        for (cx, cy, dx, dy) in [
            (x1, y1, 1, 1), (x2, y1, -1, 1),
            (x1, y2, 1, -1), (x2, y2, -1, -1),
        ]:
            cv2.line(out, (cx, cy), (cx + corner * dx, cy), COLOR_PHONE, 3)
            cv2.line(out, (cx, cy), (cx, cy + corner * dy), COLOR_PHONE, 3)

        # Label
        label = f"PHONE {d.confidence * 100:.0f}%"
        if show_ids:
            label += f"  #{track.track_id}"

        (tw, th), base = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2,
        )
        label_y = max(y1 - 10, th + 6)
        cv2.rectangle(
            out,
            (x1, label_y - th - 6),
            (x1 + tw + 12, label_y + base - 2),
            COLOR_PHONE, -1,
        )
        cv2.putText(
            out, label,
            (x1 + 6, label_y - 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2, cv2.LINE_AA,
        )

    return out

# ─────────────────────────────────────────────────────────────
# Hand drawing (Phase 5)
# ─────────────────────────────────────────────────────────────

# MediaPipe hand connections (pairs of landmark indices)
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),            # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),            # index
    (5, 9), (9, 10), (10, 11), (11, 12),       # middle
    (9, 13), (13, 14), (14, 15), (15, 16),     # ring
    (13, 17), (17, 18), (18, 19), (19, 20),    # pinky
    (0, 17),                                    # palm base
]

COLOR_HAND        = (0, 200, 120)   # green (BGR)
COLOR_LANDMARK    = (0, 255, 200)   # brighter green
COLOR_PROX_HIGH   = (0, 100, 255)   # orange/red when proximity is high


def draw_hands(
    frame,
    hands,
    frame_width: int,
    frame_height: int,
    phone_detection=None,
    proximity: float = 0.0,
    draw_landmarks: bool = True,
):
    """
    Draw hand landmarks and connections.

    Also draws a dashed line from the nearest hand fingertip to the
    phone center if a phone is present, colored by proximity.
    """
    out = frame
    if not hands:
        return out

    import cv2
    import numpy as np

    for hand in hands:
        # Convert normalized landmarks to pixel coords
        pts = []
        for nx, ny, _nz in hand.landmarks:
            pts.append((int(nx * frame_width), int(ny * frame_height)))

        # Draw connections
        for a, b in HAND_CONNECTIONS:
            if a < len(pts) and b < len(pts):
                cv2.line(out, pts[a], pts[b], COLOR_HAND, 2, cv2.LINE_AA)

        # Draw landmark dots
        if draw_landmarks:
            for i, p in enumerate(pts):
                if i in (4, 8, 12, 16, 20):  # fingertip
                    cv2.circle(out, p, 6, COLOR_LANDMARK, -1, cv2.LINE_AA)
                else:
                    cv2.circle(out, p, 3, COLOR_LANDMARK, -1, cv2.LINE_AA)

        # Hand label
        label = f"{hand.handedness} hand"
        x1, y1 = hand.x1, max(hand.y1 - 6, 12)
        cv2.putText(
            out, label, (x1, y1),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA,
        )
        cv2.putText(
            out, label, (x1, y1),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_HAND, 1, cv2.LINE_AA,
        )

    # Draw proximity line if we have a phone + hand
    if phone_detection is not None and proximity > 0.0:
        pcx = (phone_detection.x1 + phone_detection.x2) // 2
        pcy = (phone_detection.y1 + phone_detection.y2) // 2

        # Color: green at low proximity → red at high
        if proximity > 0.6:
            line_color = COLOR_PROX_HIGH
        else:
            line_color = COLOR_HAND

        for hand in hands:
            for i in (4, 8, 12, 16, 20):
                if i >= len(hand.landmarks):
                    continue
                nx, ny, _ = hand.landmarks[i]
                px = int(nx * frame_width)
                py = int(ny * frame_height)
                # Only draw the closest tip's line — visually cleaner
                # (approximation: draw lines from all tips, thin)
                cv2.line(out, (px, py), (pcx, pcy), line_color, 1, cv2.LINE_AA)

    return out

# ─────────────────────────────────────────────────────────────
# State badge (Phase 6)
# ─────────────────────────────────────────────────────────────

def draw_state_badge(frame, state_name: str, color, x: int, y: int):
    """Draw a rounded-ish state badge at (x, y)."""
    import cv2

    text = state_name.replace("_", " ")
    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)

    pad = 10
    x1, y1 = x, y - th - pad
    x2, y2 = x + tw + pad * 2, y + base + pad - 4
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)
    cv2.putText(
        frame, text, (x + pad, y - 4),
        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2, cv2.LINE_AA,
    )
    return frame