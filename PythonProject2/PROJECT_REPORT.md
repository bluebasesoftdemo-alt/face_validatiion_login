# Project Report: Facial Recognition Attendance System

## 1. Abstract
The Facial Recognition Attendance System is an automated, real-time desktop application designed to streamline employee check-ins. By utilizing advanced deep learning models (InsightFace), it replaces manual registers and legacy biometric systems. The system provides a modern GUI, robust database logging, and automated Excel reporting.

## 2. Objectives
- Eliminate buddy punching and manual entry errors.
- Create a fast, contactless attendance tracking solution.
- Provide HR departments with automated monthly attendance exports.
- Deliver a modern, dark-mode desktop interface for administration.

## 3. Problem Statement
Traditional attendance tracking (RFID cards, manual registers, fingerprint scanners) suffers from buddy punching, physical wear and tear, and slow processing times during peak hours. An automated facial recognition system is required to track attendance seamlessly as employees walk past a camera.

## 4. Existing System vs. Proposed System
- **Existing Systems:** Legacy fingerprint scanners are contact-based and unhygienic. RFID systems are easily spoofed via shared cards.
- **Proposed System:** A contactless, continuous facial recognition pipeline leveraging the `buffalo_l` InsightFace model. The system evaluates video frames asynchronously, avoiding UI freezes, and instantly logs attendance against a centralized MySQL database.

## 5. Technologies Used
- **Backend/Logic:** Python 3.9+, OpenCV, InsightFace, ONNXRuntime
- **Database:** MySQL, mysql-connector-python
- **GUI:** CustomTkinter (built on Tkinter)
- **Data/Reporting:** Pandas, OpenPyXL

## 6. Software Architecture
The application employs a **Service Layer Architecture**:
- **Core:** Contains singletons and utilities (Database Connection Pool, Logger).
- **Face Engine:** Encapsulates the InsightFace model, threaded camera reading, and liveness placeholders.
- **Services:** Contains the business logic (`EmployeeService`, `AttendanceService`, `ReportService`). Ensures the GUI never interacts directly with SQL strings.
- **GUI:** A CustomTkinter router that maps independent page frames (Dashboard, Employees, Reports, Settings).

## 7. Folder Structure
- `core/`: DB utilities and centralized exception logging.
- `face_engine/`: `camera.py`, `recognizer.py`, `liveness.py`.
- `services/`: Encapsulated database transaction logic.
- `gui/`: `app.py` UI router, and `pages/` (Dashboard, Employees, Attendance, Reports, Settings).
- `assets/`: Stores captured physical employee face images.

## 8. Database Schema
- **employees:** `id` (VARCHAR PK), `name` (VARCHAR), `face_encoding` (BLOB), `department` (VARCHAR), `created_at` (TIMESTAMP).
- **attendance:** `id` (INT PK), `employee_id` (FK), `date` (DATE), `check_in` (TIME), `check_out` (TIME), `status` (VARCHAR: 'Present', 'Late').

## 9. Face Recognition Workflow
1. Frames are retrieved from the `ThreadedCamera` and placed in a `Queue`.
2. A background daemon thread pops frames and passes them to `InsightFace`.
3. If a face is detected, the embedding is extracted.
4. Cosine similarity is calculated against all active embeddings loaded in RAM.
5. If the similarity is above the threshold (default `0.35`), a match is identified.

## 10. Attendance Workflow
1. Once a face is recognized, the system triggers `AttendanceService.mark_attendance()`.
2. The service enforces an `ATTENDANCE_COOLDOWN` to prevent database spamming if the person stands in front of the camera.
3. If it is the first check-in of the day, it is compared against the `LATE_THRESHOLD` to determine status. Subsequent check-ins update the `check_out` time.

## 11. Performance Optimizations
- **Threaded Camera:** Prevents `cv2.VideoCapture.read()` from blocking the GUI mainloop.
- **Asynchronous Model Inference:** The heavy InsightFace ONNX execution is offloaded to a queue-based daemon worker, keeping the video feed smooth at ~30 FPS.
- **In-Memory Embedding Cache:** The `FaceRecognizer` holds employee embeddings in a NumPy array. DB hits are only required during registration or manual synchronization.

## 12. Testing Performed
- **Integration Testing:** Verified seamless UI transition between Employee Registration to the Live Dashboard recognizing the new face immediately.
- **Load Testing:** Handled multiple rapid face detections by properly dropping overflow frames and utilizing the cooldown logic.

## 13. Current Limitations
- **Liveness/Anti-Spoofing:** IMPORTANT: The current `LivenessDetector` is a placeholder structural class. It does NOT implement real anti-spoofing. Because the project mandated the use of InsightFace's `buffalo_l` model, the system only has access to 5 facial landmarks (provided by RetinaFace). Genuine blink detection (EAR) requires 68 facial landmarks to map eye contours. The system currently returns `True` for all liveness checks.

## 14. Future Scope
- Implement a secondary fast model (e.g., MediaPipe FaceMesh) specifically to handle the 68-point contour mapping required for true EAR liveness detection.
- Syncing logs and databases to cloud infrastructure (AWS/GCP).
- Expanding to multi-camera inputs processing simultaneously.

## 15. Conclusion
The Facial Recognition Attendance System successfully modernizes attendance tracking. By strictly decoupling the UI from business and database logic, and leveraging asynchronous threaded inference, the system achieves real-time professional performance.
