"""
scripts/test_object_detector.py

Standalone test: shows YOLOv8 detecting phones/books live on your webcam.
Independent of the face pipeline -- just camera -> object detector -> draw boxes.
"""

import cv2
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from face_engine.camera import ThreadedCamera
from face_engine.monitoring.object_detector import ObjectDetector


def main():
    print("Starting camera...")
    camera = ThreadedCamera()

    print("Loading YOLOv8 (downloads the model on first run)...")
    detector = ObjectDetector(confidence=0.5)

    print("Ready. Hold up your phone or a book to test. Press 'q' to quit.")

    try:
        while True:
            ret, frame = camera.read()
            if not ret or frame is None:
                continue

            detections = detector.detect(frame)

            for d in detections:
                x1, y1, x2, y2 = d["bbox"]
                color = (0, 0, 255) if d["label"] == "cell phone" else (0, 165, 255)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"{d['label']} {d['conf']:.2f}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            cv2.imshow("Object Detector Test", frame)




            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("Camera released. Exiting.")


if __name__ == "__main__":
    main()