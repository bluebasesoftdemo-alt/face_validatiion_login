"""
face_verification/service.py

The reusable face verification engine -- lives in its own folder so
it can be copied as one self-contained unit into other projects.
To reuse elsewhere, copy this whole face_verification/ folder,
along with face_engine/ and core/database.py (its dependencies).
"""

import base64
import random
import numpy as np
import cv2

from face_engine.recognizer import FaceRecognizer
from core.database import Database


class FaceVerificationService:
    def __init__(self):
        self.recognizer = FaceRecognizer()
        self.db = Database()

    @staticmethod
    def decode_frame(data_url: str):
        header, encoded = data_url.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        img_arr = np.frombuffer(img_bytes, dtype=np.uint8)
        return cv2.imdecode(img_arr, cv2.IMREAD_COLOR)

    def verify(self, image_data_url: str) -> dict:
        frame = self.decode_frame(image_data_url)

        all_candidates = self.db.get_all_candidates()
        if not all_candidates:
            return {"verified": False, "reason": "No candidates registered yet."}

        result = self.recognizer.recognize(frame, all_candidates)
        matched = result is not None and result.get("employee") is not None

        if not matched:
            return {"verified": False, "reason": "Face not recognized."}

        matched_candidate = result["employee"]
        return {
            "verified": True,
            "candidate_id": matched_candidate["id"],
            "candidate_name": matched_candidate["name"],
            "embedding": matched_candidate["embedding"].tolist(),
        }

    def verify_against_one(self, image_data_url: str, candidate_id: str) -> dict:
        existing = self.db.get_candidate(candidate_id)
        if existing is None:
            return {"verified": False, "reason": f"No candidate found with ID '{candidate_id}'."}

        frame = self.decode_frame(image_data_url)
        result = self.recognizer.recognize(frame, [existing])
        matched = result is not None and result.get("employee") is not None

        if not matched:
            return {"verified": False, "reason": "Face does not match the registered photo."}

        return {"verified": True, "candidate_id": existing["id"], "candidate_name": existing["name"]}

    def register(self, image_data_url: str, name: str) -> dict:
        if not name or not name.strip():
            return {"success": False, "reason": "Name is required."}

        frame = self.decode_frame(image_data_url)
        face = self.recognizer.get_largest_face(frame)
        if face is None:
            return {"success": False, "reason": "No face detected. Please face the camera clearly."}

        candidate_id = self._generate_id()
        self.db.add_candidate(candidate_id, name.strip(), face.embedding)

        return {"success": True, "candidate_id": candidate_id, "candidate_name": name.strip()}

    def _generate_id(self) -> str:
        while True:
            candidate_id = f"APP{random.randint(1000, 9999)}"
            if self.db.get_candidate(candidate_id) is None:
                return candidate_id