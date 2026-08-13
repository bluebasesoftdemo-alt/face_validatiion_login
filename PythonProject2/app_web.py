"""
app_web.py  (Project 2 -- Monitoring / Exam)

This project has NO login page and NO face verification code at all.
It only ever receives an ALREADY-VERIFIED candidate (sent here by
Project 1's redirect) and runs the actual monitored exam.

Routes:
  /exam        -- the exam page. Reads candidate_id/candidate_name
                   from the URL (put there by Project 1's redirect).
  /begin       -- starts the exam session for that candidate. No
                   photo, no verification -- just trusts the redirect.
  /analyze     -- the live monitoring loop (unchanged from before).
  /report_violation -- browser-side violations (tab switching).
"""

import base64
import numpy as np
import cv2
from datetime import datetime
from flask import Flask, render_template, request, jsonify

from face_engine.recognizer import FaceRecognizer
from face_engine.monitoring.presence import PresenceMonitor
from face_engine.monitoring.object_detector import ObjectDetector
from face_engine.monitoring.warning_engine import WarningEngine
from core.database import Database

app = Flask(__name__)

print("Loading InsightFace (for face presence detection only)...")
recognizer = FaceRecognizer()
print("Loading YOLOv8...")
detector = ObjectDetector(confidence=0.30)

print("Warming up models (avoids a slow first frame for the candidate)...")
_dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
try:
    recognizer.detect_faces(_dummy_frame)
    detector.detect(_dummy_frame)
    print("Warm-up complete.")
except Exception as e:
    print(f"Warm-up skipped (non-fatal): {e}")

db = Database()

# --- Single active session state (one candidate at a time, for now) ---
candidate_id = None
candidate_name = None
presence_monitor = None
warning_engine = None
session_start = None
exam_duration_seconds = None


def get_exam_duration_seconds() -> int:
    setting_row = db._execute(
        "SELECT setting_value FROM system_settings WHERE setting_key = 'EXAM_DURATION_MINUTES'",
        fetch="one", dictionary=True,
    )
    return (int(setting_row["setting_value"]) if setting_row else 30) * 60


def decode_frame(data_url: str):
    header, encoded = data_url.split(",", 1)
    img_bytes = base64.b64decode(encoded)
    img_arr = np.frombuffer(img_bytes, dtype=np.uint8)
    return cv2.imdecode(img_arr, cv2.IMREAD_COLOR)


def finalize_if_needed():
    elapsed = (datetime.now() - session_start).total_seconds()
    remaining = max(0, exam_duration_seconds - elapsed)
    should_end = warning_engine.should_terminate() or remaining <= 0
    end_reason = None

    if should_end:
        end_reason = "terminated" if warning_engine.should_terminate() else "time_up"
        db.save_exam_report(
            candidate_id=candidate_id,
            session_start=session_start,
            session_end=datetime.now(),
            status=end_reason,
            violation_count=warning_engine.count,
            violation_log=warning_engine.violations,
        )
    return remaining, should_end, end_reason


@app.route("/exam")
def exam_page():
    cid = request.args.get("candidate_id", "")
    cname = request.args.get("candidate_name", "")

    if not cid or not cname:
        return "Missing candidate information. Please verify through the login page first.", 400

    return render_template("exam.html", candidate_id=cid, candidate_name=cname)


@app.route("/begin", methods=["POST"])
def begin_session():
    global candidate_id, candidate_name, presence_monitor, warning_engine
    global session_start, exam_duration_seconds

    payload = request.get_json(silent=True) or {}
    cid = payload.get("candidate_id", "")
    cname = payload.get("candidate_name", "")

    if not cid:
        return jsonify({"started": False, "reason": "No candidate ID provided."}), 400

    candidate_id = cid
    candidate_name = cname
    presence_monitor = PresenceMonitor()
    warning_engine = WarningEngine(candidate_id=candidate_id, max_violations=3, cooldown_seconds=5)
    session_start = datetime.now()
    exam_duration_seconds = get_exam_duration_seconds()

    return jsonify({"started": True, "duration_seconds": exam_duration_seconds})


@app.route("/analyze", methods=["POST"])
def analyze():
    if warning_engine is None:
        return jsonify({"error": "No active session."}), 400

    payload = request.get_json()
    frame = decode_frame(payload["image"])

    raw_faces = recognizer.detect_faces(frame)
    faces = [f for f in raw_faces if getattr(f, "det_score", 1.0) >= 0.5]
    presence_status = presence_monitor.check(faces)
    new_violation_type = None

    if warning_engine.report("no_face", presence_status["no_face_violation"], frame):
        new_violation_type = "no_face"
    if warning_engine.report("multiple_faces", presence_status["multi_face_violation"], frame):
        new_violation_type = "multiple_faces"

    objects = detector.detect(frame)
    phone_seen = any(o["label"] == "cell phone" for o in objects)
    book_seen = any(o["label"] == "book" for o in objects)

    if warning_engine.report("mobile_phone", phone_seen, frame):
        new_violation_type = "mobile_phone"
    if warning_engine.report("book", book_seen, frame):
        new_violation_type = "book"

    remaining, should_end, end_reason = finalize_if_needed()

    return jsonify({
        "num_faces": presence_status["num_faces"],
        "faces": [{"bbox": list(map(int, f.bbox))} for f in faces],
        "objects": [{"label": o["label"], "bbox": o["bbox"]} for o in objects],
        "new_violation": new_violation_type,
        "violation_count": warning_engine.count,
        "remaining_seconds": int(remaining),
        "should_end": should_end,
        "end_reason": end_reason,
    })


@app.route("/report_violation", methods=["POST"])
def report_violation():
    if warning_engine is None:
        return jsonify({"error": "No active session."}), 400

    payload = request.get_json(silent=True) or {}
    violation_type = payload.get("type", "unknown")
    detected = bool(payload.get("detected", False))

    warning_engine.report(violation_type, detected, frame=None)

    remaining, should_end, end_reason = finalize_if_needed()

    return jsonify({
        "violation_count": warning_engine.count,
        "should_end": should_end,
        "end_reason": end_reason,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False, threaded=True)