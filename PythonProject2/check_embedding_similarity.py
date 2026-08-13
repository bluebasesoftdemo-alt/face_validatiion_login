"""
check_embedding_similarity.py

Diagnostic tool: captures your live face and prints the RAW cosine
similarity score against EVERY registered candidate, AND clearly
labels whether that score actually passes your system's real
SIMILARITY_THRESHOLD -- not just "highest among those compared."
"""

import time
import numpy as np

from face_engine.camera import ThreadedCamera
from face_engine.recognizer import FaceRecognizer
from core.database import Database
import config


def cosine_similarity(a, b):
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    return float(np.dot(a, b))


def main():
    print("Starting camera...")
    camera = ThreadedCamera()

    print("Loading InsightFace...")
    recognizer = FaceRecognizer()

    print("Look at the camera. Capturing in 3 seconds...")
    time.sleep(3)

    ret, frame = camera.read()
    camera.release()

    if not ret or frame is None:
        print("Failed to capture a frame. Try again.")
        return

    face = recognizer.get_largest_face(frame)
    if face is None:
        print("No face detected. Make sure your face is clearly visible.")
        return

    live_embedding = face.embedding

    db = Database()
    candidates = db.get_all_candidates()

    if not candidates:
        print("No candidates registered yet -- register someone via /register first.")
        return

    threshold = config.SIMILARITY_THRESHOLD
    print(f"\nComparing your live face against {len(candidates)} registered candidate(s)")
    print(f"(SIMILARITY_THRESHOLD = {threshold})\n")

    results = []
    for c in candidates:
        score = cosine_similarity(live_embedding, c["embedding"])
        results.append((c["id"], c["name"], score))

    results.sort(key=lambda x: x[2], reverse=True)

    best_score = results[0][2]
    overall_verdict = "MATCH" if best_score >= threshold else "NO MATCH -- REJECTED"

    for cid, name, score in results:
        passes = score >= threshold
        verdict = "PASSES threshold" if passes else "below threshold"
        print(f"  {cid:<12} {name:<20} similarity: {score:.4f}   ({verdict})")

    print(f"\nOverall result: {overall_verdict}")


if __name__ == "__main__":
    main()