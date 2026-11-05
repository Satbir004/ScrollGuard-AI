"""
Single-object IoU tracker for phone detections.

Phase 6 addition: fast-drop. If two consecutive YOLO inferences return
zero phone detections, all tracks are cleared immediately — this eliminates
ghost boxes when the phone genuinely leaves the frame.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass
from typing import List, Optional

from .detector import Detection

logger = logging.getLogger(__name__)


def _iou(a: Detection, b: Detection) -> float:
    xa1, ya1, xa2, ya2 = a.x1, a.y1, a.x2, a.y2
    xb1, yb1, xb2, yb2 = b.x1, b.y1, b.x2, b.y2
    ix1, iy1 = max(xa1, xb1), max(ya1, yb1)
    ix2, iy2 = min(xa2, xb2), min(ya2, yb2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0, xa2 - xa1) * max(0, ya2 - ya1)
    area_b = max(0, xb2 - xb1) * max(0, yb2 - yb1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


@dataclass
class Track:
    track_id: int
    detection: Detection
    missed_frames: int = 0
    hit_count: int = 1

    def update(self, det: Detection) -> None:
        self.detection = det
        self.missed_frames = 0
        self.hit_count += 1

    def mark_missed(self) -> None:
        self.missed_frames += 1

    def to_dict(self) -> dict:
        d = self.detection
        return {
            "track_id": self.track_id,
            "x1": d.x1, "y1": d.y1, "x2": d.x2, "y2": d.y2,
            "confidence": d.confidence,
            "hit_count": self.hit_count,
            "missed_frames": self.missed_frames,
        }


class PhoneTracker:
    def __init__(
        self,
        iou_threshold: float = 0.3,
        max_missed_frames: int = 6,
        fast_drop_empty_runs: int = 2,
    ):
        self.iou_threshold = iou_threshold
        self.max_missed_frames = max_missed_frames
        self.fast_drop_empty_runs = fast_drop_empty_runs

        self._tracks: dict[int, Track] = {}
        self._next_id = itertools.count(1)
        self._empty_inference_streak = 0

    def update(self, detections: List[Detection]) -> None:
        # Fast-drop: two empty inferences in a row → clear everything
        if not detections:
            self._empty_inference_streak += 1
            if self._empty_inference_streak >= self.fast_drop_empty_runs:
                if self._tracks:
                    logger.debug(
                        "Fast-drop: %d empty inferences, clearing %d tracks",
                        self._empty_inference_streak, len(self._tracks),
                    )
                self._tracks.clear()
                return
        else:
            self._empty_inference_streak = 0

        for t in self._tracks.values():
            t.mark_missed()

        unmatched = list(detections)
        for track in list(self._tracks.values()):
            best_score, best_det = 0.0, None
            for det in unmatched:
                score = _iou(track.detection, det)
                if score > best_score:
                    best_score, best_det = score, det
            if best_det is not None and best_score >= self.iou_threshold:
                track.update(best_det)
                unmatched.remove(best_det)

        for det in unmatched:
            tid = next(self._next_id)
            self._tracks[tid] = Track(track_id=tid, detection=det)

        to_delete = [
            tid for tid, t in self._tracks.items()
            if t.missed_frames > self.max_missed_frames
        ]
        for tid in to_delete:
            del self._tracks[tid]

    def tick(self) -> None:
        pass

    def active_tracks(self) -> List[Track]:
        return list(self._tracks.values())

    def best_track(self) -> Optional[Track]:
        if not self._tracks:
            return None
        return max(self._tracks.values(), key=lambda t: t.detection.confidence)

    def reset(self) -> None:
        self._tracks.clear()
        self._next_id = itertools.count(1)
        self._empty_inference_streak = 0