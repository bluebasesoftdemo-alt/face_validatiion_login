import customtkinter as ctk
import dotenv
import os
import mysql.connector
from pathlib import Path
from core.logger import get_logger

logger = get_logger(__name__)

class Settings(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color="transparent")
        self.app = app
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Header
        ctk.CTkLabel(self, text="System Settings", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, pady=20)
        
        # Scrollable Settings Area
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        
        # 2-Column Grid Layout for the Scrollable Frame
        self.scroll_frame.grid_columnconfigure(0, weight=1, uniform="col")
        self.scroll_frame.grid_columnconfigure(1, weight=1, uniform="col")
        
        # Load env path
        self.env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        
        # Validation Commands
        self.vcmd_float = (self.register(self.validate_float), '%P')
        self.vcmd_int = (self.register(self.validate_int), '%P')
        
        # Sections (Cards)
        self.create_hardware_settings()
        self.create_attendance_settings()
        self.create_db_settings()
        self.create_corporate_time_settings()
        
        # Footer for Save Button & Status
        self.footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.footer_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 20))
        
        # Save Button
        self.btn_save = ctk.CTkButton(
            self.footer_frame, 
            text="Save Settings", 
            font=ctk.CTkFont(weight="bold"), 
            width=200, 
            height=40,
            command=self.save_settings
        )
        self.btn_save.pack(pady=5)

        self.status_label = ctk.CTkLabel(self.footer_frame, text="", text_color="green")
        self.status_label.pack(pady=5)

    def get_env_val(self, key, default=""):
        return os.environ.get(key, default)

    def validate_float(self, value):
        if value == "": return True
        try:
            float(value)
            return True
        except ValueError:
            return False

    def validate_int(self, value):
        if value == "": return True
        return value.isdigit()

    def create_hardware_settings(self):
        # Card 1: Hardware & Core AI (Row 0, Col 0)
        card = ctk.CTkFrame(self.scroll_frame, border_width=1, border_color="gray30")
        card.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(card, text="Hardware & Core AI", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10, anchor="w", padx=15)
        
        input_frame = ctk.CTkFrame(card, fg_color="transparent")
        input_frame.pack(fill="x", padx=15, pady=5)
        
        # Camera Index Dropdown
        ctk.CTkLabel(input_frame, text="Camera Index:").grid(row=0, column=0, padx=5, pady=10, sticky="w")
        self.var_camera_index = ctk.StringVar(value=self.get_env_val("CAMERA_INDEX", "0"))
        self.camera_dropdown = ctk.CTkComboBox(input_frame, variable=self.var_camera_index, values=["0", "1", "2", "3", "4"], state="readonly")
        self.camera_dropdown.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        
        # Similarity Threshold (Numeric Validation)
        ctk.CTkLabel(input_frame, text="Similarity Threshold (0-1):").grid(row=1, column=0, padx=5, pady=10, sticky="w")
        self.var_similarity = ctk.StringVar(value=self.get_env_val("SIMILARITY_THRESHOLD", "0.35"))
        ctk.CTkEntry(input_frame, textvariable=self.var_similarity, validate="key", validatecommand=self.vcmd_float).grid(row=1, column=1, padx=5, pady=10, sticky="ew")
        
        input_frame.grid_columnconfigure(1, weight=1)

    def create_attendance_settings(self):
        # Card 2: Attendance Rules (Row 1, Col 0)
        card = ctk.CTkFrame(self.scroll_frame, border_width=1, border_color="gray30")
        card.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(card, text="Attendance Rules", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10, anchor="w", padx=15)
        
        input_frame = ctk.CTkFrame(card, fg_color="transparent")
        input_frame.pack(fill="x", padx=15, pady=5)
        
        # Late Threshold
        ctk.CTkLabel(input_frame, text="Late Threshold (HH:MM):").grid(row=0, column=0, padx=5, pady=10, sticky="w")
        self.var_late = ctk.StringVar(value=self.get_env_val("LATE_THRESHOLD", "09:00"))
        ctk.CTkEntry(input_frame, textvariable=self.var_late).grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        
        # Cooldown (Numeric Validation)
        ctk.CTkLabel(input_frame, text="Cooldown (seconds):").grid(row=1, column=0, padx=5, pady=10, sticky="w")
        self.var_cooldown = ctk.StringVar(value=self.get_env_val("ATTENDANCE_COOLDOWN", "5"))
        ctk.CTkEntry(input_frame, textvariable=self.var_cooldown, validate="key", validatecommand=self.vcmd_int).grid(row=1, column=1, padx=5, pady=10, sticky="ew")
        
        input_frame.grid_columnconfigure(1, weight=1)

    def create_corporate_time_settings(self):
        # Card 4: Corporate Time Rules (Row 0, Col 1, rowspan 2)
        card = ctk.CTkFrame(self.scroll_frame, border_width=1, border_color="gray30")
        card.grid(row=0, column=1, rowspan=2, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(card, text="Corporate Time Rules", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10, anchor="w", padx=15)
        
        input_frame = ctk.CTkFrame(card, fg_color="transparent")
        input_frame.pack(fill="x", padx=15, pady=5)
        
        # Shift Start Time
        ctk.CTkLabel(input_frame, text="Shift Start (HH:MM:SS):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.var_shift_start = ctk.StringVar(value=self.app.db.get_setting("SHIFT_START", "10:00:00"))
        ctk.CTkEntry(input_frame, textvariable=self.var_shift_start).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Late Buffer Minutes
        ctk.CTkLabel(input_frame, text="Late Buffer (Minutes):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.var_late_buffer = ctk.StringVar(value=self.app.db.get_setting("LATE_BUFFER", "5"))
        ctk.CTkEntry(input_frame, textvariable=self.var_late_buffer, validate="key", validatecommand=self.vcmd_int).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        # Lunch Start Time
        ctk.CTkLabel(input_frame, text="Lunch Start (HH:MM:SS):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.var_lunch_start = ctk.StringVar(value=self.app.db.get_setting("LUNCH_START", "13:00:00"))
        ctk.CTkEntry(input_frame, textvariable=self.var_lunch_start).grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        
        # Lunch End Time
        ctk.CTkLabel(input_frame, text="Lunch End (HH:MM:SS):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.var_lunch_end = ctk.StringVar(value=self.app.db.get_setting("LUNCH_END", "13:45:00"))
        ctk.CTkEntry(input_frame, textvariable=self.var_lunch_end).grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        
        # Check-Out Earliest Unlock
        ctk.CTkLabel(input_frame, text="Earliest Check-Out (HH:MM:SS):").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.var_checkout_unlock = ctk.StringVar(value=self.app.db.get_setting("CHECKOUT_UNLOCK", "16:30:00"))
        ctk.CTkEntry(input_frame, textvariable=self.var_checkout_unlock).grid(row=4, column=1, padx=5, pady=5, sticky="ew")
        
        # Shift End
        ctk.CTkLabel(input_frame, text="Shift End (HH:MM:SS):").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.var_shift_end = ctk.StringVar(value=self.app.db.get_setting("SHIFT_END", "15:00:00"))
        ctk.CTkEntry(input_frame, textvariable=self.var_shift_end).grid(row=5, column=1, padx=5, pady=5, sticky="ew")
        
        input_frame.grid_columnconfigure(1, weight=1)

    def create_db_settings(self):
        # Card 3: Database Settings (Row 2, Col 0 span 2)
        card = ctk.CTkFrame(self.scroll_frame, border_width=1, border_color="gray30")
        card.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(header_frame, text="Database Settings", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        
        self.btn_test_db = ctk.CTkButton(header_frame, text="Test Connection", width=120, command=self.test_connection)
        self.btn_test_db.pack(side="right")
        
        input_frame = ctk.CTkFrame(card, fg_color="transparent")
        input_frame.pack(fill="x", padx=15, pady=5)
        
        # Host
        ctk.CTkLabel(input_frame, text="Host:").grid(row=0, column=0, padx=5, pady=10, sticky="w")
        self.var_db_host = ctk.StringVar(value=self.get_env_val("DB_HOST", "localhost"))
        ctk.CTkEntry(input_frame, textvariable=self.var_db_host).grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        
        # User
        ctk.CTkLabel(input_frame, text="User:").grid(row=0, column=2, padx=20, pady=10, sticky="w")
        self.var_db_user = ctk.StringVar(value=self.get_env_val("DB_USER", "root"))
        ctk.CTkEntry(input_frame, textvariable=self.var_db_user).grid(row=0, column=3, padx=5, pady=10, sticky="ew")
        
        # Name
        ctk.CTkLabel(input_frame, text="Database Name:").grid(row=1, column=0, padx=5, pady=10, sticky="w")
        self.var_db_name = ctk.StringVar(value=self.get_env_val("DB_NAME", "facial_attendance"))
        ctk.CTkEntry(input_frame, textvariable=self.var_db_name).grid(row=1, column=1, padx=5, pady=10, sticky="ew")
        
        # Password (Masked)
        ctk.CTkLabel(input_frame, text="Password:").grid(row=1, column=2, padx=20, pady=10, sticky="w")
        self.var_db_password = ctk.StringVar(value=self.get_env_val("DB_PASSWORD", ""))
        ctk.CTkEntry(input_frame, textvariable=self.var_db_password, show="*").grid(row=1, column=3, padx=5, pady=10, sticky="ew")
        
        input_frame.grid_columnconfigure((1, 3), weight=1)

    def test_connection(self):
        self.btn_test_db.configure(state="disabled", text="Testing...")
        self.update()
        
        try:
            conn = mysql.connector.connect(
                host=self.var_db_host.get(),
                user=self.var_db_user.get(),
                password=self.var_db_password.get(),
                database=self.var_db_name.get(),
                connection_timeout=3
            )
            if conn.is_connected():
                conn.close()
                self.status_label.configure(text="Database Connection Successful!", text_color="green")
        except Exception as e:
            self.status_label.configure(text=f"Database Connection Failed: {e}", text_color="red")
        finally:
            self.btn_test_db.configure(state="normal", text="Test Connection")

    def start(self):
        pass
        
    def stop(self):
        pass
        
    def save_settings(self):
        try:
            # 1. Save env settings
            dotenv.set_key(self.env_path, "CAMERA_INDEX", self.var_camera_index.get())
            dotenv.set_key(self.env_path, "SIMILARITY_THRESHOLD", self.var_similarity.get())
            dotenv.set_key(self.env_path, "LATE_THRESHOLD", self.var_late.get())
            dotenv.set_key(self.env_path, "ATTENDANCE_COOLDOWN", self.var_cooldown.get())
            dotenv.set_key(self.env_path, "DB_HOST", self.var_db_host.get())
            dotenv.set_key(self.env_path, "DB_USER", self.var_db_user.get())
            dotenv.set_key(self.env_path, "DB_NAME", self.var_db_name.get())
            dotenv.set_key(self.env_path, "DB_PASSWORD", self.var_db_password.get())
            
            # 2. Save corporate time settings to MySQL system_settings table
            self.app.db.set_setting("SHIFT_START", self.var_shift_start.get())
            self.app.db.set_setting("LATE_BUFFER", self.var_late_buffer.get())
            self.app.db.set_setting("LUNCH_START", self.var_lunch_start.get())
            self.app.db.set_setting("LUNCH_END", self.var_lunch_end.get())
            self.app.db.set_setting("CHECKOUT_UNLOCK", self.var_checkout_unlock.get())
            self.app.db.set_setting("SHIFT_END", self.var_shift_end.get())
            
            self.status_label.configure(text="Settings Saved! Please restart the application to apply changes.", text_color="green")
            logger.info("Application settings updated by user.")
        except Exception as e:
            self.status_label.configure(text=f"Error saving settings: {e}", text_color="red")
            logger.error(f"Error saving settings: {e}")
