"""
scripts/test_presence_monitor.py

Standalone test: run this file directly to see presence monitoring
working live on your webcam. Doesn't touch MySQL or the GUI at all --
just camera -> face detection -> presence check -> on-screen warning.
"""

import cv2
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from face_engine.camera import ThreadedCamera
from face_engine.recognizer import FaceRecognizer
from face_engine.monitoring.presence import PresenceMonitor


def main():
    print("Starting camera...")
    camera = ThreadedCamera()

    print("Loading InsightFace (this takes a few seconds the first time)...")
    recognizer = FaceRecognizer()

    monitor = PresenceMonitor(no_face_grace_frames=15, multi_face_grace_frames=5)

    print("Ready. Press 'q' in the video window to quit.")

    try:
        while True:
            ret, frame = camera.read()
            if not ret or frame is None:
                continue

            faces = recognizer.detect_faces(frame)
            status = monitor.check(faces)

            for face in faces:
                x1, y1, x2, y2 = map(int, face.bbox)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            y_offset = 30
            if status["no_face_violation"]:
                cv2.putText(frame, "WARNING: No face detected", (10, y_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                y_offset += 35
            if status["multi_face_violation"]:
                cv2.putText(frame, "WARNING: Multiple faces detected", (10, y_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            cv2.putText(frame, f"Faces: {status['num_faces']}", (10, frame.shape[0] - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            cv2.imshow("Presence Monitor Test", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("Camera released. Exiting.")


if __name__ == "__main__":
    main()