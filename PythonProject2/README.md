# Exam Monitoring Service (Project 2)

## Overview
A Flask-based web service that monitors a candidate during an online exam. It receives an already-verified candidate (handed off by **FaceVerificationService**, the login/identity project) and tracks presence, unauthorized objects, and tab-switching for the duration of the test — automatically ending the session if malpractice is detected or time runs out.

This project does **not** perform identity verification itself. Login and face matching live entirely in the separate `FaceVerificationService` project; this service trusts whoever it's handed and focuses purely on monitoring.

## Features
- **Live Presence Monitoring**: Detects no-face and multiple-face situations in real time using InsightFace.
- **Object Detection**: Flags phones and books in frame using a YOLOv8 model, tuned for CPU performance.
- **Weighted Violation System**: Different violation types carry different severity, with cooldown logic so one continuous violation doesn't spam multiple counts. Session auto-terminates after 3 violations.
- **Tab-Switch Detection**: Browser-side reporting when the candidate navigates away from the exam tab.
- **Configurable Exam Duration**: Duration is read from a database setting (`system_settings`), not hardcoded — change it any time via `set_exam_duration.py` with no code changes.
- **Automatic Exam Reports**: Every session (completed, terminated, or timed out) is logged to MySQL with a full violation log.

## Technologies Used
- **Language**: Python 3.9+
- **Web Framework**: Flask
- **Database**: MySQL 8.0+
- **Face Presence**: InsightFace (`buffalo_l` model) — presence only, not identity matching
- **Object Detection**: YOLOv8 (Ultralytics), OpenCV

## How This Fits Into the Two-Project Architecture
Once `FaceVerificationService` verifies a candidate, it redirects the browser to this project's `/exam` route with `candidate_id` and `candidate_name` attached — no further identity check happens here.





## Project Structure

```text
PythonProject2/
├── core/                  # Core utilities
├── face_engine/           # Face recognition and camera processing
├── services/              # Application business logic
├── gui/                   # User interface components
│   └── pages/             # Individual UI pages
├── assets/                # Application assets
├── data/                  # Application data
├── templates/             # HTML templates
├── config.py              # Project configuration
├── app_web.py             # Web application
├── main.py                # Application entry point
└── requirements.txt       # Python dependencies


## Installation
1. Install dependencies:
```bash
   pip install -r requirements.txt
```
2. Copy `.env.example` to `.env` and fill in your MySQL credentials.
3. Make sure MySQL is running and the `exam_reports` and `system_settings` tables exist.
4. Set the exam duration:
```bash
   python set_exam_duration.py
```

## Running the Application
**FaceVerificationService must be running first** (port 5001), since this project's `/register` route forwards there.

```bash
python app_web.py
```
Runs on `http://127.0.0.1:5000`. Candidates should not open this project directly — they arrive here automatically via redirect from FaceVerificationService's login page.

## Useful Scripts
- `register_candidate.py` — register a test candidate straight from the terminal, no browser needed.
- `check_exam_reports.py` — quickly view saved exam reports without opening MySQL directly.
- `check_embedding_similarity.py` — diagnostic tool for tuning `SIMILARITY_THRESHOLD`.







