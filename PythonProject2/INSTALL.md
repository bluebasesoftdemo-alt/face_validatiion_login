# Installation Guide

## System Requirements
- **Operating System:** Windows 10/11, macOS, or Linux
- **RAM:** Minimum 8GB (16GB recommended for model inference)
- **Webcam:** Any standard USB or integrated camera

## Software Requirements
- **Python:** Version 3.9, 3.10, or 3.11 (Do not use 3.12+ as ONNXRuntime/InsightFace support may vary)
- **MySQL:** Version 8.0 or higher
- **C++ Build Tools:** Required on Windows for InsightFace compilation (Visual Studio Build Tools)

## Database Setup (MySQL)
1. Install MySQL Server and ensure the service is running.
2. Log in to your MySQL terminal or workbench:
   ```sql
   CREATE DATABASE facial_attendance;
   ```
3. The application will automatically create the required tables (`employees`, `attendance`) upon its first connection if they do not exist.

## Project Setup
1. **Clone/Download the repository** and navigate to the root directory (`PythonProject2`).
2. **Create a Virtual Environment**:
   ```bash
   python -m venv .venv
   ```
3. **Activate the Virtual Environment**:
   - Windows:
     ```bash
     .venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     source .venv/bin/activate
     ```

## Installing Dependencies
Install all required packages with strict versioning using the provided requirements file:
```bash
pip install -r requirements.txt
```

## Environment Configuration
1. Copy the example `.env.example` file (if provided) or create a new `.env` file in the root directory.
2. Populate the `.env` file with your MySQL credentials:
```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=facial_attendance
CAMERA_INDEX=0
SIMILARITY_THRESHOLD=0.35
LATE_THRESHOLD=09:00
ATTENDANCE_COOLDOWN=5
```

## Launching the Application
Once dependencies are installed and the `.env` file is configured:
```bash
python main.py
```

## Troubleshooting
- **ModuleNotFoundError: No module named 'customtkinter'**: Ensure your virtual environment is activated before installing dependencies and running the script.
- **Database Connection Error**: Verify your MySQL server is running, the credentials in `.env` are strictly correct, and the database `facial_attendance` exists.
- **InsightFace Model Download Error**: On first run, InsightFace attempts to download the `buffalo_l` model (~300MB) to `~/.insightface/models/`. Ensure you have an active internet connection.
- **Camera Not Found**: If the camera feed fails, change `CAMERA_INDEX` in the `.env` file from `0` to `1` or `2`.
