import cv2
import time
from database import Database
from services.employee_service import EmployeeService
from services.attendance_service import AttendanceService
from face_utils_code import FaceRecognizer
from face_engine.camera import ThreadedCamera
from face_engine.liveness import LivenessDetector
import config
from core.logger import get_logger

logger = get_logger(__name__)

class AttendanceController:

    def __init__(self, camera_index=0):

        # Initialize the database and inject into services
        self.db = Database()
        self.employee_service = EmployeeService(self.db)
        self.attendance_service = AttendanceService(self.db)

        self.recognizer = FaceRecognizer()
        self.liveness = LivenessDetector()

        # Fetch employees via Service Layer
        self.employees = self.employee_service.get_all_active_employees()
        self.recognizer.load_employees(self.employees)
        logger.info(f"Loaded {len(self.employees)} employees into memory.")

        self.cap = ThreadedCamera(camera_index)

        # Metrics for FPS overlay
        self.fps = 0.0
        self.frame_count = 0
        self.start_time = time.time()

    def mark_attendance(self, emp_id):
        # The Service layer now handles cooldowns and business logic
        # We simply pass the request down.
        self.attendance_service.mark_attendance(emp_id)

    def run(self):

        while True:
            ret, frame = self.cap.read()

            if not ret or frame is None:
                time.sleep(0.01)
                continue

            result = self.recognizer.recognize(frame)

            if result is None:
                cv2.putText(frame, "No Face Detected", (50, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            else:
                is_live = self.liveness.is_live(result.get("face_obj"))
                
                if not is_live:
                    cv2.putText(frame, "SPOOF DETECTED", (50, 80),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                else:
                    frame = self.recognizer.draw_result(frame, result)

                    if result.get("employee"):
                        self.mark_attendance(result["employee"]["id"])

            self.frame_count += 1
            elapsed = time.time() - self.start_time
            if elapsed > 1.0:
                self.fps = self.frame_count / elapsed
                self.frame_count = 0
                self.start_time = time.time()
                
            cv2.putText(frame, f"FPS: {self.fps:.1f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

            cv2.imshow("Attendance System", frame)

            if cv2.waitKey(1) & 0xFF == 27:
                break

        self.cap.release()
        cv2.destroyAllWindows()
        self.db.close()


if __name__ == "__main__":
    app = AttendanceController(config.CAMERA_INDEX)
    app.run()