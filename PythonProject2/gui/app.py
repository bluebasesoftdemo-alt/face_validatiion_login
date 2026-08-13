import customtkinter as ctk
from services.employee_service import EmployeeService
from services.attendance_service import AttendanceService
from services.report_service import ReportService
from core.database import Database
from gui.pages.dashboard import Dashboard
from gui.pages.employee_mgmt import EmployeeManagement
from gui.pages.attendance_view import AttendanceView
from gui.pages.reports import Reports
from gui.pages.settings import Settings
from core.logger import get_logger

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

logger = get_logger(__name__)

class AttendanceApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Facial Recognition Attendance System")
        self.geometry("1200x800")
        self.minsize(1000, 600)

        # Initialize Services (Centralized)
        self.db = Database()
        self.employee_service = EmployeeService(self.db)
        self.attendance_service = AttendanceService(self.db)
        self.report_service = ReportService(self.db)

        # Layout: 1x2 Grid (Sidebar, Main Content)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # --- Sidebar ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="SYSTEM", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 30))

        # Sidebar Buttons
        self.btn_dashboard = ctk.CTkButton(self.sidebar_frame, text="Dashboard", anchor="w", 
                                           command=lambda: self.select_frame("dashboard"))
        self.btn_dashboard.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        self.btn_employees = ctk.CTkButton(self.sidebar_frame, text="Employees", anchor="w", 
                                           command=lambda: self.select_frame("employees"))
        self.btn_employees.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        self.btn_attendance = ctk.CTkButton(self.sidebar_frame, text="Attendance", anchor="w", 
                                            command=lambda: self.select_frame("attendance"))
        self.btn_attendance.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        self.btn_reports = ctk.CTkButton(self.sidebar_frame, text="Reports", anchor="w", 
                                         command=lambda: self.select_frame("reports"))
        self.btn_reports.grid(row=4, column=0, padx=20, pady=10, sticky="ew")

        self.btn_settings = ctk.CTkButton(self.sidebar_frame, text="Settings", anchor="w", 
                                          command=lambda: self.select_frame("settings"))
        self.btn_settings.grid(row=5, column=0, padx=20, pady=10, sticky="ew")

        # Status Bar
        self.status_bar = ctk.CTkLabel(self.sidebar_frame, text="Ready", text_color="gray", anchor="w")
        self.status_bar.grid(row=7, column=0, padx=20, pady=10, sticky="ew")

        # --- Main Frames (Placeholders) ---
        self.frames = {}

        self.frames["dashboard"] = Dashboard(self, self)

        self.frames["employees"] = EmployeeManagement(self, self)
        self.frames["attendance"] = AttendanceView(self, self)
        self.frames["reports"] = Reports(self, self)
        self.frames["settings"] = Settings(self, self)

        # Default selection
        self.select_frame("dashboard")

        # Bind closing protocol to cleanup resources
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def select_frame(self, name):
        # Update button colors based on selection
        for btn, key in [
            (self.btn_dashboard, "dashboard"),
            (self.btn_employees, "employees"),
            (self.btn_attendance, "attendance"),
            (self.btn_reports, "reports"),
            (self.btn_settings, "settings")
        ]:
            if key == name:
                btn.configure(fg_color=("gray75", "gray25"))
            else:
                btn.configure(fg_color="transparent")

        # Show selected frame
        for key, frame in self.frames.items():
            if key == name:
                frame.grid(row=0, column=1, sticky="nsew")
                if hasattr(frame, 'start'):
                    frame.start()
            else:
                frame.grid_forget()
                if hasattr(frame, 'stop'):
                    frame.stop()

    def set_status(self, message: str):
        """Update the status bar."""
        self.status_bar.configure(text=message)
        # Clear status after 3 seconds
        self.after(3000, lambda: self.status_bar.configure(text="Ready"))

    def on_closing(self):
        """Cleanup DB connections and close app."""
        self.db.close()
        self.destroy()

if __name__ == "__main__":
    app = AttendanceApp()
    app.mainloop()
