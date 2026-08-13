"""
face_engine/monitoring/presence.py

Reuses the face list your recognizer.py already produces each frame.
No new model, no new dependency -- just counting.

Uses real elapsed TIME instead of frame count for the grace period.
This matters because the desktop version ran at ~15-30fps (so "5
frames" was under a second), but the web version only sends about
1 frame per second -- counting frames would make violations take
5x longer to trigger than intended. Counting seconds keeps behavior
consistent no matter how fast frames arrive.
"""

import time


class PresenceMonitor:
    def __init__(self, no_face_grace_seconds=1.0, multi_face_grace_seconds=1.0):
        self.no_face_grace = no_face_grace_seconds
        self.multi_face_grace = multi_face_grace_seconds
        self._no_face_since = None
        self._multi_face_since = None

    def check(self, faces: list) -> dict:
        """
        faces: the list returned by InsightFace's FaceAnalysis().get(frame)
        Returns a dict describing this frame's presence status.
        """
        num_faces = len(faces)
        now = time.time()

        if num_faces == 0:
            if self._no_face_since is None:
                self._no_face_since = now
            self._multi_face_since = None
        elif num_faces > 1:
            if self._multi_face_since is None:
                self._multi_face_since = now
            self._no_face_since = None
        else:
            self._no_face_since = None
            self._multi_face_since = None

        no_face_elapsed = (now - self._no_face_since) if self._no_face_since else 0
        multi_face_elapsed = (now - self._multi_face_since) if self._multi_face_since else 0

        return {
            "num_faces": num_faces,
            "no_face_violation": no_face_elapsed >= self.no_face_grace,
            "multi_face_violation": multi_face_elapsed >= self.multi_face_grace,
        }