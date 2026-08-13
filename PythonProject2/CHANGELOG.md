# Changelog

All notable changes to the Facial Recognition Attendance System will be documented in this file.

## [v1.0.0] - Final Release
### Added
- **Phase 4 Integration:** Complete CustomTkinter GUI deployment replacing all CLI stubs.
- **Settings Module:** In-app modification of `.env` configurations (Camera index, thresholds, DB credentials).
- **Employee Management:** Native GUI face capture, saving, and database storage.
- **Attendance View:** Real-time data table reflecting daily attendance and statuses.
- **Reports Module:** Excel exportation of monthly attendance data utilizing Pandas.
- **Dashboard Refinement:** Fully integrated background daemon worker for InsightFace recognition without freezing the UI.
- **Documentation:** Added comprehensive `README.md`, `INSTALL.md`, `USER_MANUAL.md`, and `PROJECT_REPORT.md`.

## [Phase 3] - Reporting and Advanced Logic
### Added
- Monthly Excel reporting generation via Pandas and OpenPyXL.
- Service Layer Architecture (`ReportService`, `EmployeeService`, `AttendanceService`) separating logic from the core.
- Late status calculation based on configurable environment threshold.

## [Phase 2] - Face Engine
### Added
- Wrapped InsightFace `buffalo_l` model into a modular `FaceRecognizer` class.
- Built a `ThreadedCamera` to offload `cv2.VideoCapture` latency.
- Implemented `LivenessDetector` placeholder (pass-through) in accordance with the 5-landmark limitation of RetinaFace.

## [Phase 1] - Foundation
### Added
- Centralized `Database` connection pool via `mysql-connector-python`.
- `config.py` environment variable parsing using `python-dotenv`.
- Professional logging framework outputting to file and console.
