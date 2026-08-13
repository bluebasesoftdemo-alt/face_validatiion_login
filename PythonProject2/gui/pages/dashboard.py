import customtkinter as ctk
import cv2
import time
import threading
import queue
from PIL import Image
from datetime import datetime, date, timedelta

from face_engine.camera import ThreadedCamera
from face_engine.recognizer import FaceRecognizer
from face_engine.liveness import LivenessDetector
import config
from core.logger import get_logger

logger = get_logger(__name__)

class Dashboard(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color="transparent")
        self.app = app
        
        # UI Layout: Left Camera (65%), Right Stats (35%)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=65)
        self.grid_columnconfigure(1, weight=35)
        
        # --- Camera Frame ---
        self.camera_frame = ctk.CTkFrame(self, fg_color="gray10", corner_radius=15)
        self.camera_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.camera_frame.grid_rowconfigure(1, weight=1)
        self.camera_frame.grid_columnconfigure(0, weight=1)
        
        self.camera_header = ctk.CTkLabel(self.camera_frame, text="Live Biometric Feed", font=ctk.CTkFont(size=22, weight="bold"))
        self.camera_header.grid(row=0, column=0, pady=(20, 10))
        
        self.camera_label = ctk.CTkLabel(self.camera_frame, text="Initializing Camera...", font=ctk.CTkFont(size=18, weight="bold"), text_color="gray50")
        self.camera_label.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        
        # Dynamic Status Banner
        self.banner_frame = ctk.CTkFrame(self.camera_frame, height=60, corner_radius=10, fg_color="gray20")
        self.banner_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        self.banner_frame.grid_propagate(False)
        self.banner_label = ctk.CTkLabel(self.banner_frame, text="READY TO SCAN", font=ctk.CTkFont(size=22, weight="bold"), text_color="white")
        self.banner_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # --- Stats Frame (Live Activity Log) ---
        self.stats_frame = ctk.CTkFrame(self, fg_color="gray10", corner_radius=15)
        self.stats_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.stats_frame.grid_columnconfigure(0, weight=1)
        self.stats_frame.grid_rowconfigure(5, weight=1)
        
        self.datetime_label = ctk.CTkLabel(self.stats_frame, text="", font=ctk.CTkFont(size=24, weight="bold"), text_color="#3498db")
        self.datetime_label.grid(row=0, column=0, pady=(20, 10))
        
        self.fps_label = ctk.CTkLabel(self.stats_frame, text="Video FPS: 0.0", font=ctk.CTkFont(size=14), text_color="gray50")
        self.fps_label.grid(row=1, column=0, pady=0)
        
        # Ribbon Stats
        ribbon = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
        ribbon.grid(row=2, column=0, pady=15, sticky="ew")
        ribbon.grid_columnconfigure((0,1,2), weight=1)
        
        self.total_emp_label = ctk.CTkLabel(ribbon, text="Total: 0", font=ctk.CTkFont(size=14, weight="bold"))
        self.total_emp_label.grid(row=0, column=0)
        self.present_label = ctk.CTkLabel(ribbon, text="Present: 0", font=ctk.CTkFont(size=14, weight="bold"), text_color="#2ecc71")
        self.present_label.grid(row=0, column=1)
        self.late_label = ctk.CTkLabel(ribbon, text="Late: 0", font=ctk.CTkFont(size=14, weight="bold"), text_color="#f39c12")
        self.late_label.grid(row=0, column=2)
        
        ctk.CTkLabel(self.stats_frame, text="Live Activity Log", font=ctk.CTkFont(size=18, weight="bold")).grid(row=4, column=0, pady=(20, 5), sticky="w", padx=20)
        
        self.log_scroll_frame = ctk.CTkScrollableFrame(self.stats_frame, fg_color="transparent")
        self.log_scroll_frame.grid(row=5, column=0, sticky="nsew", padx=10, pady=(0, 20))
        
        # --- Background Engine ---
        self.camera = None
        self.recognizer = FaceRecognizer()
        self.liveness = LivenessDetector()
        
        employees = self.app.employee_service.get_all_active_employees()
        self.recognizer.load_employees(employees)
        
        self.frame_queue = queue.Queue(maxsize=1)
        self.result_queue = queue.Queue(maxsize=1)
        self.running = False
        self.current_result = None
        self.last_scan_time = 0
        
        self.fps_count = 0
        self.fps_start = time.time()
        
        self.update_stats()

    def start(self):
        if self.running:
            return
            
        self.running = True
        try:
            self.camera = ThreadedCamera(config.CAMERA_INDEX)
        except Exception as e:
            self.banner_frame.configure(fg_color="#c0392b")
            self.banner_label.configure(text="CAMERA ERROR")
            logger.error(f"Dashboard Camera init error: {e}")
            return
            
        self.worker_thread = threading.Thread(target=self.recognition_worker, daemon=True)
        self.worker_thread.start()
        
        self.update_datetime()
        self.update_frame()
        # Periodic grid update for countdown timers
        self.update_timers()
        
    def stop(self):
        self.running = False
        if self.camera:
            self.camera.release()
            self.camera = None

    def update_timers(self):
        if not self.running:
            return
        self.update_stats()
        self.after(30000, self.update_timers) # Update countdowns every 30s

    def update_stats(self):
        stats = self.app.report_service.get_dashboard_stats()
        self.total_emp_label.configure(text=f"Total: {stats.get('total', 0)}")
        self.present_label.configure(text=f"Present: {stats.get('present', 0)}")
        self.late_label.configure(text=f"Late: {stats.get('late', 0)}")
        
        for widget in self.log_scroll_frame.winfo_children():
            widget.destroy()
            
        records = self.app.attendance_service.get_today_attendance()
        if not records:
            ctk.CTkLabel(self.log_scroll_frame, text="No activity yet today.", text_color="gray50").pack(pady=20)
            return
            
        for r_idx, record in enumerate(records):
            emp_id = str(record.get('employee_id', 'N/A'))
            name = record.get('employee_name', 'N/A')
            status = record.get('status', 'Unknown')
            
            # Check for Pre-Lunch open breaks
            open_b = self.app.db._execute(
                "SELECT break_out FROM employee_breaks WHERE employee_id = %s AND break_date = CURDATE() AND break_in IS NULL ORDER BY id DESC LIMIT 1",
                (emp_id,), fetch="one", dictionary=True
            )
            if open_b and status not in ["Checked Out", "OUT", "Lunch Out", "On Break"]:
                b_out = open_b["break_out"]
                ls_str = self.app.db.get_setting("LUNCH_START", "13:00:00")
                try:
                    ls_t = datetime.strptime(ls_str, "%H:%M:%S").time()
                except Exception:
                    ls_t = datetime.strptime("13:00:00", "%H:%M:%S").time()
                l_dt = datetime.combine(date.today(), ls_t)
                if l_dt - timedelta(minutes=5) <= b_out <= l_dt:
                    status = "On Break (Pre-Lunch)"
                else:
                    status = "On Break"
            
            # Pill badge color
            color = "gray50"
            if status in ["Checked In", "IN", "Present"]: color = "#2ecc71" # Green
            elif status == "Late": color = "#f39c12" # Yellow/Orange
            elif status in ["Lunch Out", "Break Out", "On Break", "On Break (Pre-Lunch)"]: color = "#e67e22" # Orange
            elif "Forced Out" in status: color = "#c0392b" # Red
            elif status in ["Checked Out", "OUT"]: color = "#7f8c8d" # Gray
            
            # Calculate remaining hours
            rem_hours = ""
            try:
                if status not in ["Checked Out", "OUT"] and "Forced Out" not in status:
                    rem = self.app.attendance_service.break_service.get_remaining_hours(emp_id)
                    rem_hours = f"⏳ {rem}"
            except Exception:
                pass
                
            # Render Row
            row_frame = ctk.CTkFrame(self.log_scroll_frame, fg_color="gray15", corner_radius=8)
            row_frame.pack(fill="x", pady=4, padx=5)
            
            ctk.CTkLabel(row_frame, text=emp_id, width=60, anchor="w", font=ctk.CTkFont(size=11), text_color="gray60").pack(side="left", padx=(10, 5), pady=8)
            ctk.CTkLabel(row_frame, text=name, font=ctk.CTkFont(weight="bold", size=13), width=120, anchor="w").pack(side="left", padx=5, pady=8)
            
            # Pill badge
            ctk.CTkLabel(row_frame, text=f" {status} ", font=ctk.CTkFont(size=11, weight="bold"), text_color="white", fg_color=color, corner_radius=10, width=80).pack(side="left", padx=10, pady=8)
            
            if rem_hours:
                ctk.CTkLabel(row_frame, text=rem_hours, text_color="cyan", font=ctk.CTkFont(weight="bold", size=12)).pack(side="right", padx=15, pady=8)
                
            # Add Force Out Button if shift is active
            if status not in ["Checked Out", "OUT"] and "Forced Out" not in status:
                btn_force = ctk.CTkButton(
                    row_frame, 
                    text="✖ Force Out", 
                    width=60, 
                    height=24,
                    fg_color="#8B0000", 
                    hover_color="#A52A2A",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    command=lambda e=emp_id: self.force_out_action(e)
                )
                btn_force.pack(side="right", padx=(0, 5), pady=8)
                
    def force_out_action(self, emp_id):
        try:
            success = self.app.attendance_service.force_checkout(emp_id)
            if success:
                logger.info(f"Dashboard: Admin manually forced out employee {emp_id}")
                self.update_stats()
        except Exception as e:
            logger.error(f"Error forcing out employee from dashboard: {e}", exc_info=True)
            
    def update_datetime(self):
        if not self.running:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.datetime_label.configure(text=now)
        self.after(1000, self.update_datetime)
            
    def recognition_worker(self):
        while self.running:
            try:
                frame = self.frame_queue.get(timeout=0.5)
            except queue.Empty:
                continue
                
            result = self.recognizer.recognize(frame)
            
            if self.result_queue.full():
                try:
                    self.result_queue.get_nowait()
                except queue.Empty:
                    pass
            self.result_queue.put(result)
            self.frame_queue.task_done()
            
    def update_frame(self):
        if not self.running:
            return
            
        ret, frame = self.camera.read()
        if not ret or frame is None:
            self.banner_frame.configure(fg_color="#c0392b")
            self.banner_label.configure(text="CAMERA DISCONNECTED")
            self.after(100, self.update_frame)
            return
            
        frame = cv2.resize(frame, (640, 480))
            
        if self.frame_queue.empty():
            self.frame_queue.put(frame.copy())
            
        try:
            new_result = self.result_queue.get_nowait()
            
            if new_result and new_result.get("face_obj"):
                new_result["is_live"] = self.liveness.is_live(new_result["face_obj"])
            else:
                if new_result:
                    new_result["is_live"] = True
                    
            self.current_result = new_result
            
            if new_result and new_result.get("employee"):
                is_live = new_result.get("is_live", True)
                if is_live:
                    emp_id = new_result["employee"]["id"]
                    emp_name = new_result["employee"].get('name', new_result["employee"].get('employee_name'))
                    
                    # Prevent rapid re-scanning
                    current_t = time.time()
                    if current_t - self.last_scan_time > 3.0: # 3 second global debounce for UI updates
                        self.last_scan_time = current_t
                        def async_mark_attendance(e_id, e_name):
                            try:
                                # Capture prior state to determine transitions
                                prev_record = self.app.db.get_today_attendance_record(e_id)
                                prev_status = prev_record.get('status') if prev_record else None
                                prev_open_b = self.app.db._execute(
                                    "SELECT id FROM employee_breaks WHERE employee_id = %s AND break_date = CURDATE() AND break_in IS NULL ORDER BY id DESC LIMIT 1",
                                    (e_id,), fetch="one", dictionary=True
                                )
                                
                                success = self.app.attendance_service.mark_attendance(e_id)
                                # Update UI state
                                record = self.app.db.get_today_attendance_record(e_id)
                                status = record.get('status', 'Present') if record else 'Present'
                                
                                open_b = self.app.db._execute(
                                    "SELECT break_out FROM employee_breaks WHERE employee_id = %s AND break_date = CURDATE() AND break_in IS NULL ORDER BY id DESC LIMIT 1",
                                    (e_id,), fetch="one", dictionary=True
                                )
                                if open_b and status not in ["Checked Out", "OUT", "Lunch Out", "On Break"]:
                                    b_out = open_b["break_out"]
                                    ls_str = self.app.db.get_setting("LUNCH_START", "13:00:00")
                                    try:
                                        ls_t = datetime.strptime(ls_str, "%H:%M:%S").time()
                                    except Exception:
                                        ls_t = datetime.strptime("13:00:00", "%H:%M:%S").time()
                                    l_dt = datetime.combine(date.today(), ls_t)
                                    if l_dt - timedelta(minutes=5) <= b_out <= l_dt:
                                        status = "On Break (Pre-Lunch)"
                                    else:
                                        status = "On Break"
                                
                                is_return = (prev_status == "Lunch Out" or prev_open_b is not None)
                                
                                if status in ["Present", "Checked In", "IN", "Late"]:
                                    if is_return:
                                        b_color, b_text = "#27ae60", f"🔄 Welcome Back: {e_name} status RESET TO PRESENT!"
                                    else:
                                        b_color, b_text = "#27ae60", f"✅ Check-in Successful: {e_name} marked PRESENT!"
                                elif status == "Lunch Out":
                                    b_color, b_text = "#d35400", f"🍱 Lunch Out: {e_name} marked ON LUNCH!"
                                elif status in ["Break Out", "On Break", "On Break (Pre-Lunch)"]:
                                    b_color, b_text = "#e67e22", f"☕ Break Registered: {e_name} marked ON BREAK!"
                                elif status in ["Checked Out", "OUT"]:
                                    b_color, b_text = "#2980b9", f"👋 Shift Completed: Goodbye {e_name}!"
                                elif "Forced Out" in status:
                                    b_color, b_text = "#c0392b", f"🚨 {e_name} - {status.upper()}"
                                else:
                                    b_color, b_text = "#2980b9", f"ℹ️ {e_name} - {status.upper()}"
                                    
                                self.after(0, lambda: self.banner_frame.configure(fg_color=b_color))
                                self.after(0, lambda: self.banner_label.configure(text=b_text))
                                self.after(0, self.update_stats)
                                
                                self.after(2500, lambda: self.banner_frame.configure(fg_color="gray20"))
                                self.after(2500, lambda: self.banner_label.configure(text="READY TO SCAN"))
                            except Exception as e:
                                logger.error(f"Unhandled exception in async_mark_attendance for {e_id}: {e}", exc_info=True)
                                self.after(0, lambda: self.banner_frame.configure(fg_color="#c0392b"))
                                self.after(0, lambda: self.banner_label.configure(text="SYSTEM ERROR"))
                                self.after(2500, lambda: self.banner_frame.configure(fg_color="gray20"))
                                self.after(2500, lambda: self.banner_label.configure(text="READY TO SCAN"))
                                
                        threading.Thread(target=async_mark_attendance, args=(emp_id, emp_name), daemon=True).start()
        except queue.Empty:
            pass
            
        display_frame = frame.copy()
        
        # Digital Corner Alignment Brackets
        if self.current_result and self.current_result.get("bbox"):
            x1, y1, x2, y2 = self.current_result["bbox"]
            length = 25
            t = 4
            is_live = self.current_result.get("is_live", True)
            
            if not is_live:
                color = (0, 0, 255) # Red for spoof
            elif self.current_result.get("employee"):
                color = (0, 255, 0) # Green for recognized
            else:
                color = (255, 255, 0) # Cyan/Yellow for unknown
                
            # Top-left
            cv2.line(display_frame, (x1, y1), (x1 + length, y1), color, t)
            cv2.line(display_frame, (x1, y1), (x1, y1 + length), color, t)
            # Top-right
            cv2.line(display_frame, (x2, y1), (x2 - length, y1), color, t)
            cv2.line(display_frame, (x2, y1), (x2, y1 + length), color, t)
            # Bottom-left
            cv2.line(display_frame, (x1, y2), (x1 + length, y2), color, t)
            cv2.line(display_frame, (x1, y2), (x1, y2 - length), color, t)
            # Bottom-right
            cv2.line(display_frame, (x2, y2), (x2 - length, y2), color, t)
            cv2.line(display_frame, (x2, y2), (x2, y2 - length), color, t)
            
            if not is_live:
                cv2.putText(display_frame, "SPOOF DETECTED", (x1, y1 - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            else:
                name = self.current_result.get("employee", {}).get("name", "Unknown") if self.current_result.get("employee") else "Unknown"
                cv2.putText(display_frame, name, (x1, y1 - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                
        # GUI Video FPS
        self.fps_count += 1
        elapsed = time.time() - self.fps_start
        if elapsed > 1.0:
            self.current_fps = self.fps_count / elapsed
            self.fps_count = 0
            self.fps_start = time.time()
            self.fps_label.configure(text=f"Video Feed: {self.current_fps:.1f} FPS")
            
        rgb_image = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_image)
        
        ctk_img = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(640, 480))
        self.camera_label.configure(image=ctk_img, text="")
        self.camera_label.image = ctk_img
        
        self.after(33, self.update_frame)
