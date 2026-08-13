"""
face_engine/monitoring/warning_engine.py

Turns raw per-frame/per-event detections into countable "violations",
using a debounce idea -- a violation only counts once per incident,
not once per frame.

Weighted violations: camera-side violations (phone, book, no_face,
multiple_faces) count as 1 point. Tab switching counts as 2 points.
max_violations is a POINTS threshold, not a strict incident count.

Also saves a snapshot image at the moment of camera-side violations.
"""

import os
import cv2
from datetime import datetime

VIOLATION_WEIGHTS = {
    "no_face": 1,
    "multiple_faces": 1,
    "mobile_phone": 1,
    "book": 1,
    "tab_switch": 2,
}
DEFAULT_WEIGHT = 1


class WarningEngine:
    def __init__(self, candidate_id, max_violations=3, cooldown_seconds=5,
                 snapshot_dir="violation_snapshots"):
        self.candidate_id = candidate_id
        self.max_violations = max_violations
        self.cooldown_seconds = cooldown_seconds
        self.snapshot_dir = snapshot_dir
        os.makedirs(self.snapshot_dir, exist_ok=True)

        self.violations = []
        self.score = 0
        self._active = {}
        self._last_added = {}

    def _save_snapshot(self, frame, violation_type, when: datetime) -> str:
        timestamp_str = when.strftime("%Y%m%d_%H%M%S")
        filename = f"{self.candidate_id}_{timestamp_str}_{violation_type}.jpg"
        path = os.path.join(self.snapshot_dir, filename)
        cv2.imwrite(path, frame)
        return path

    def report(self, violation_type: str, is_detected: bool, frame=None) -> bool:
        was_active = self._active.get(violation_type, False)
        self._active[violation_type] = is_detected

        if is_detected and not was_active:
            last_time = self._last_added.get(violation_type)
            now = datetime.now()
            if last_time is None or (now - last_time).total_seconds() >= self.cooldown_seconds:
                weight = VIOLATION_WEIGHTS.get(violation_type, DEFAULT_WEIGHT)
                entry = {"type": violation_type, "timestamp": now.isoformat(), "weight": weight}

                if frame is not None:
                    entry["snapshot"] = self._save_snapshot(frame, violation_type, now)

                self.violations.append(entry)
                self.score += weight
                self._last_added[violation_type] = now
                return True
        return False

    @property
    def count(self) -> int:
        return len(self.violations)

    @property
    def weighted_score(self) -> int:
        return self.score

    def should_terminate(self) -> bool:
        return self.score >= self.max_violations