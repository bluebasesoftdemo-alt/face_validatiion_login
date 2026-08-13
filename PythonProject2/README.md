# Facial Recognition Attendance System (v1.0.0)

## Overview
A professional, automated attendance tracking system leveraging InsightFace `buffalo_l` for high-accuracy facial recognition. Designed with a robust Service Layer architecture and a modern, threaded CustomTkinter GUI.

## Features
- **Real-Time Facial Recognition**: Utilizes InsightFace for robust face detection and matching.
- **Asynchronous Processing**: Ensures smooth GUI frame-rates by decoupling the camera loop from model inference latency.
- **Employee Management**: Capture, store, and manage employee faces natively.
- **Attendance Tracking**: Automatically records check-ins, tracks lateness based on a configurable threshold, and enforces cooldowns to prevent spam.
- **Excel Reporting**: Generate comprehensive monthly attendance reports dynamically.
- **Dynamic Configuration**: Tweak core system settings directly from the UI without touching source code.

## Technologies Used
- **Language**: Python 3.9+
- **Database**: MySQL 8.0+
- **Face Engine**: InsightFace (`buffalo_l` model), OpenCV
- **GUI Engine**: CustomTkinter
- **Data Export**: Pandas, OpenPyXL

## Folder Structure
```text
PythonProject2/
├── core/                  # Core utilities (DB connection, Logger, Exceptions)
├── face_engine/           # InsightFace wrappers (Camera, Recognizer, Liveness)
├── services/              # Business logic (Employee, Attendance, Reports)
├── gui/                   # CustomTkinter UI (App router and Pages)
│   ├── pages/             # Individual UI views (Dashboard, Settings, etc.)
├── assets/                # Assets and employee photos
├── exports/               # Generated Excel reports
├── logs/                  # System logs
├── config.py              # Environment variable parser
├── main.py                # Application entry point
├── .env                   # Environment variables (excluded from VCS)
└── requirements.txt       # Exact pip dependencies
```

## Installation
See [INSTALL.md](INSTALL.md) for detailed installation and database configuration instructions.

## Running the Application
Ensure the virtual environment is activated and the MySQL server is running.
```bash
python main.py
```

## Screenshots
- ![Dashboard Placeholder](path/to/dashboard.png)
- ![Employee Management Placeholder](path/to/employee.png)
- ![Reports Placeholder](path/to/reports.png)

## Future Enhancements
- Integration of a true 68-point landmark model (e.g., MediaPipe FaceMesh) to implement actual EAR anti-spoofing, as current `buffalo_l` limitations restrict us to 5 landmarks.
- Cloud database synchronization (e.g., AWS RDS).
- Multi-camera support.

## License
MIT License
