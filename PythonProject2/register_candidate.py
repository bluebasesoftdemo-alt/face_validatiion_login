"""
register_candidate.py

One-time (per candidate) script: opens your webcam, captures your face,
and stores it in the candidates table -- so recognize() has something
to match against later. Mirrors how employees get registered.
"""

import time
from face_engine.camera import ThreadedCamera
from face_engine.recognizer import FaceRecognizer
from core.database import Database


def main():
    candidate_id = input("Enter candidate ID (e.g. TEST001): ").strip()
    candidate_name = input("Enter candidate name: ").strip()

    print("Starting camera...")
    camera = ThreadedCamera()

    print("Loading InsightFace...")
    recognizer = FaceRecognizer()

    print("Look at the camera. Capturing in 3 seconds...")
    time.sleep(3)

    ret, frame = camera.read()
    if not ret or frame is None:
        print("Failed to capture a frame. Try again.")
        camera.release()
        return

    face = recognizer.get_largest_face(frame)
    if face is None:
        print("No face detected. Make sure your face is clearly visible and try again.")
        camera.release()
        return

    db = Database()
    db.add_candidate(candidate_id, candidate_name, face.embedding)
    print(f"Registered candidate '{candidate_name}' ({candidate_id}) successfully.")

    camera.release()


if __name__ == "__main__":
    main()