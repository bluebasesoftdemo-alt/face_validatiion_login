# User Manual

## 1. Getting Started
To start the application, navigate to the project directory, activate your virtual environment, and run:
```bash
python main.py
```
Upon launching, the professional CustomTkinter graphical interface will appear, defaulting to the Dashboard tab.

## 2. Using the Dashboard
The Dashboard provides a live view of the camera feed and daily statistics.
- **Live Feed:** The left pane displays the camera with bounding boxes around recognized faces.
- **Statistics:** The right pane displays real-time statistics including Total Employees, Present Today, Late Today, and a live log of recent check-ins.

## 3. Employee Management (Registering Employees)
To add a new employee:
1. Click the **Employees** tab in the sidebar.
2. In the Registration Form on the left, enter the **Employee ID**, **Full Name**, and optionally the **Department**.
3. Instruct the employee to look at the camera and click **Start Face Capture**.
4. The system will process multiple frames to ensure a high-quality averaged face profile. 
5. A success message will appear, and the employee will immediately show up in the Employee List on the right.

## 4. Attendance View
To view all of today's attendance data:
1. Click the **Attendance** tab in the sidebar.
2. The table displays ID, Name, Check-In time, Check-Out time, and Status.
3. Statuses are color-coded (Green for Present, Orange for Late).
4. Click **Refresh** to manually pull the latest data from the database.

## 5. Reports (Exporting Data)
To generate monthly Excel reports:
1. Click the **Reports** tab.
2. Ensure the correct **Year** and **Month** are entered.
3. Click **Export to Excel**.
4. The system will query the monthly records and save a formatted `.xlsx` file into the `exports/` folder of the project directory.

## 6. Settings
To configure system parameters without restarting code:
1. Click the **Settings** tab.
2. You can safely configure:
   - **Camera Index:** Change to `1` or `2` if you are using an external USB webcam.
   - **Similarity Threshold:** Lower this (e.g., `0.25`) to make recognition more lenient. Raise it (e.g., `0.45`) to make it stricter and prevent false matches.
   - **Late Threshold:** Define what time marks an employee as late (e.g., `09:00`).
   - **Database Configurations:** Update your host, user, and database names.
3. Click **Save Settings**. *Note: You must restart the application for changes to take effect.*

## 7. Troubleshooting & FAQ

**Q: The camera feed is completely blank or says "Camera Disconnected".**
A: Go to the Settings tab, ensure your Camera Index is correct (usually `0` for laptop webcams), save, and restart the app.

**Q: It's recognizing the wrong person!**
A: Navigate to Settings and increase the **Similarity Threshold** to a higher value like `0.40`.

**Q: The application won't launch and throws a MySQL connection error.**
A: Ensure your local MySQL server is actually running (via XAMPP, WAMP, or Windows Services) and the credentials in Settings (or your `.env` file) match your server.

**Q: Someone scanned their face, but the attendance didn't log.**
A: The system has a built-in cooldown (default 5 seconds). If they just scanned, they must wait for the cooldown to expire before scanning again. Ensure they are not flagged as "Unknown". If they are unknown, re-register them via Employee Management.
