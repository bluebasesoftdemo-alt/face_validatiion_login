"""
test_full_monitor.py

Full proctoring test: presence monitoring + object detection (phone/book) +
a warning engine that ends the session and saves a report to MySQL once
malpractice crosses the threshold (3 violations) OR the time limit runs out.

Exam duration is read from system_settings (EXAM_DURATION_MINUTES) --
change it any time by re-running set_exam_duration.py, no code edits needed.

A countdown timer chip (top-right) shows remaining time, turns red in
the final minute, and auto-submits when time hits zero.
"""

import cv2
import time
import numpy as np
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

from face_engine.camera import ThreadedCamera
from face_engine.recognizer import FaceRecognizer
from face_engine.monitoring.presence import PresenceMonitor
from face_engine.monitoring.object_detector import ObjectDetector
from face_engine.monitoring.warning_engine import WarningEngine
from core.database import Database

TIMES_BOLD_PATH = "C:/Windows/Fonts/timesbd.ttf"
TIMES_REG_PATH = "C:/Windows/Fonts/times.ttf"

DANGER_THRESHOLD_SECONDS = 60    # timer turns red in the last 60 seconds
DEFAULT_DURATION_MINUTES = 30    # fallback only, used if the DB setting is missing


def _load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def draw_warning_modal(frame, title="Warning", subtitle="Please follow the exam guidelines."):
    h, w = frame.shape[:2]
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    base = Image.fromarray(rgb_frame).convert("RGBA")

    dim = Image.new("RGBA", base.size, (0, 0, 0, 90))
    base = Image.alpha_composite(base, dim)

    card_w, card_h = 340, 130
    card_x = (w - card_w) // 2
    card_y = 30
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    draw.rounded_rectangle(
        [card_x + 4, card_y + 6, card_x + card_w + 4, card_y + card_h + 6],
        radius=14, fill=(0, 0, 0, 60)
    )
    draw.rounded_rectangle(
        [card_x, card_y, card_x + card_w, card_y + card_h],
        radius=14, fill=(255, 255, 255, 235), outline=(210, 60, 60, 255), width=2
    )

    icon_cx, icon_cy = card_x + 40, card_y + 40
    draw.polygon(
        [(icon_cx, icon_cy - 18), (icon_cx - 18, icon_cy + 14), (icon_cx + 18, icon_cy + 14)],
        fill=(235, 87, 45, 255)
    )
    exclaim_font = _load_font(TIMES_BOLD_PATH, 16)
    draw.text((icon_cx - 3, icon_cy - 12), "!", font=exclaim_font, fill=(255, 255, 255, 255))

    title_font = _load_font(TIMES_BOLD_PATH, 24)
    subtitle_font = _load_font(TIMES_REG_PATH, 14)
    text_x = card_x + 75
    draw.text((text_x, card_y + 22), title, font=title_font, fill=(180, 30, 30, 255))
    draw.text((text_x, card_y + 60), subtitle, font=subtitle_font, fill=(60, 60, 60, 255))

    composited = Image.alpha_composite(base, overlay).convert("RGB")
    return cv2.cvtColor(np.array(composited), cv2.COLOR_RGB2BGR)


def draw_timer(frame, text, danger=False):
    """Small rounded chip, top-right, showing remaining time."""
    h, w = frame.shape[:2]
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    base = Image.fromarray(rgb_frame).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    chip_w, chip_h = 150, 40
    chip_x = w - chip_w - 15
    chip_y = 15
    bg_color = (200, 40, 40, 210) if danger else (30, 30, 30, 190)
    draw.rounded_rectangle([chip_x, chip_y, chip_x + chip_w, chip_y + chip_h], radius=8, fill=bg_color)

    font = _load_font(TIMES_BOLD_PATH, 20)
    draw.text((chip_x + 16, chip_y + 8), text, font=font, fill=(255, 255, 255, 255))

    composited = Image.alpha_composite(base, overlay).convert("RGB")
    return cv2.cvtColor(np.array(composited), cv2.COLOR_RGB2BGR)


def format_remaining(seconds_left: float) -> str:
    seconds_left = max(0, int(seconds_left))
    minutes, seconds = divmod(seconds_left, 60)
    return f"{minutes:02d}:{seconds:02d} left"


def main():
    candidate_id = "TEST001"

    print("Starting camera...")
    camera = ThreadedCamera()

    print("Loading InsightFace...")
    recognizer = FaceRecognizer()

    print("Loading YOLOv8...")
    detector = ObjectDetector(confidence=0.5)

    presence_monitor = PresenceMonitor()
    warning_engine = WarningEngine(candidate_id=candidate_id, max_violations=3, cooldown_seconds=5)
    db = Database()

    # --- Read exam duration from the database (set by set_exam_duration.py) ---
    setting_row = db._execute(
        "SELECT setting_value FROM system_settings WHERE setting_key = 'EXAM_DURATION_MINUTES'",
        fetch="one", dictionary=True
    )
    exam_duration_minutes = int(setting_row["setting_value"]) if setting_row else DEFAULT_DURATION_MINUTES

    warning_active_until = 0.0
    WARNING_DURATION = 3.0

    session_start = datetime.now()
    exam_duration_seconds = exam_duration_minutes * 60
    end_reason = "completed"  # default if candidate quits manually with 'q'

    print(f"Session started. Duration: {exam_duration_minutes} min (from database). Press 'q' to end manually.")

    try:
        while True:
            ret, frame = camera.read()
            if not ret or frame is None:
                continue

            # --- Time remaining ---
            elapsed = (datetime.now() - session_start).total_seconds()
            remaining = exam_duration_seconds - elapsed

            # --- Face presence checks ---
            faces = recognizer.detect_faces(frame)
            presence_status = presence_monitor.check(faces)
            new_violation = False
            new_violation |= warning_engine.report("no_face", presence_status["no_face_violation"], frame)
            new_violation |= warning_engine.report("multiple_faces", presence_status["multi_face_violation"], frame)

            for face in faces:
                x1, y1, x2, y2 = map(int, face.bbox)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # --- Object checks ---
            objects = detector.detect(frame)
            phone_seen = any(o["label"] == "cell phone" for o in objects)
            book_seen = any(o["label"] == "book" for o in objects)
            new_violation |= warning_engine.report("mobile_phone", phone_seen, frame)
            new_violation |= warning_engine.report("book", book_seen, frame)

            for o in objects:
                x1, y1, x2, y2 = o["bbox"]
                color = (0, 0, 255) if o["label"] == "cell phone" else (0, 165, 255)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"{o['label']} {o['conf']:.2f}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            # --- Countdown timer (always visible) ---
            is_danger = remaining <= DANGER_THRESHOLD_SECONDS
            frame = draw_timer(frame, format_remaining(remaining), danger=is_danger)

            # --- Arm the modal if a NEW violation just fired ---
            if new_violation:
                warning_active_until = time.time() + WARNING_DURATION

            if time.time() < warning_active_until:
                frame = draw_warning_modal(frame)

            cv2.imshow("Full Proctoring Monitor", frame)

            if warning_engine.should_terminate():
                cv2.waitKey(1000)
                end_reason = "terminated"
                print(f"Malpractice threshold reached ({warning_engine.count} violations). Ending test.")
                break

            if remaining <= 0:
                end_reason = "time_up"
                print("Time limit reached. Auto-submitting test.")
                break

            if cv2.waitKey(1) & 0xFF == ord('q'):
                end_reason = "completed"
                print("Test ended manually.")
                break
    finally:
        session_end = datetime.now()

        db.save_exam_report(
            candidate_id=candidate_id,
            session_start=session_start,
            session_end=session_end,
            status=end_reason,
            violation_count=warning_engine.count,
            violation_log=warning_engine.violations,
        )
        print(f"Report saved -> status: {end_reason}, violations: {warning_engine.count}")

        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()