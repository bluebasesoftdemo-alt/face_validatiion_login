"""
main.py
=======
Main Entry Point for the Facial Recognition Attendance System.
Launches the Phase 4 CustomTkinter GUI.
"""
import config
from core.logger import get_logger
if __name__ == "__main__":
    # Initialize the core logger immediately upon startup
    get_logger(__name__)
    # Import the application window
    # We import here so logger setup captures any module-level issues
    from gui.app import AttendanceApp
    print("Launching Professional GUI...")
    app = AttendanceApp()
    # Run startup sweeps
    app.db.close_yesterday_shifts()
    app.mainloop()