import customtkinter as ctk
from datetime import datetime, date, timedelta
from core.logger import get_logger

logger = get_logger(__name__)

class AttendanceView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color="transparent")
        self.app = app
        
        self.grid_rowconfigure(2, weight=2)
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # --- 1. Header & Live Sync ---
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        
        title_group = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_group.pack(side="left")
        ctk.CTkLabel(title_group, text="Today's Attendance", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")
        
        sync_group = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        sync_group.pack(side="right")
        
        ctk.CTkLabel(sync_group, text="● Live Sync Active", text_color="#00FF00", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 15))
        self.btn_refresh = ctk.CTkButton(sync_group, text="↻ Refresh List", command=self.load_attendance, width=120, fg_color="#007acc", hover_color="#005999")
        self.btn_refresh.pack(side="left")
        
        # --- 2. Mini-Stats Ribbon ---
        self.stats_ribbon = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_ribbon.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 15))
        
        self.lbl_active = ctk.CTkLabel(self.stats_ribbon, text="Active Shifts (IN): 0", font=ctk.CTkFont(size=13, weight="bold"), text_color="#1f6aa5")
        self.lbl_active.pack(side="left", padx=(0, 20))
        
        self.lbl_completed = ctk.CTkLabel(self.stats_ribbon, text="Completed Check-Outs: 0", font=ctk.CTkFont(size=13, weight="bold"), text_color="gray60")
        self.lbl_completed.pack(side="left")
        
        # --- 3. Table Container ---
        self.table_container = ctk.CTkFrame(self)
        self.table_container.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.table_container.grid_rowconfigure(0, weight=1)
        self.table_container.grid_columnconfigure(0, weight=1)
        
        # Scrollable rows with headers inside
        self.scroll_frame = ctk.CTkScrollableFrame(self.table_container, corner_radius=0, fg_color="transparent")
        self.scroll_frame.grid(row=0, column=0, sticky="nsew")
        
        # --- 4. Break Tracking Container ---
        self.break_container = ctk.CTkFrame(self)
        self.break_container.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.break_container.grid_rowconfigure(1, weight=1)
        self.break_container.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.break_container, text="Live Break Tracking & Countdown", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, sticky="w", padx=15, pady=10)
        
        self.break_scroll = ctk.CTkScrollableFrame(self.break_container, corner_radius=0, fg_color="transparent")
        self.break_scroll.grid(row=1, column=0, sticky="nsew")
        
    def start(self):
        self.load_attendance()
        
    def stop(self):
        pass
        
    def load_attendance(self):
        # Clear table
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
            
        columns = ["ID", "Name", "Check-In", "Lunch Out", "Lunch In", "Check-Out", "Status", "Actions"]
        for i in range(len(columns)):
            self.scroll_frame.grid_columnconfigure(i, weight=1, uniform="col")
            
        # Draw Headers
        for i, col in enumerate(columns):
            header_lbl = ctk.CTkLabel(self.scroll_frame, text=col, font=ctk.CTkFont(weight="bold"), fg_color="gray25", corner_radius=4)
            header_lbl.grid(row=0, column=i, pady=5, padx=2, sticky="ew")
            
        records = self.app.attendance_service.get_today_attendance()
        
        if not records:
            ctk.CTkLabel(self.scroll_frame, text="No attendance records found for today.", text_color="gray60").grid(row=1, column=0, columnspan=8, pady=40)
            self.lbl_active.configure(text="Active Shifts (IN): 0")
            self.lbl_completed.configure(text="Completed Check-Outs: 0")
            return
            
        active_count = 0
        completed_count = 0
        
        open_breaks = self.app.db._execute(
            "SELECT employee_id, break_out FROM employee_breaks WHERE break_date = CURDATE() AND break_in IS NULL",
            (), fetch="all", dictionary=True
        )
        open_breaks_dict = {str(b["employee_id"]): b["break_out"] for b in open_breaks} if open_breaks else {}
        
        lunch_start_str = self.app.db.get_setting("LUNCH_START", "13:00:00")
        try:
            lunch_start_t = datetime.strptime(lunch_start_str, "%H:%M:%S").time()
        except Exception:
            lunch_start_t = datetime.strptime("13:00:00", "%H:%M:%S").time()
            
        for row_idx, record in enumerate(records, start=1):
            emp_id = str(record.get('employee_id', 'N/A'))
            name = record.get('employee_name', 'N/A')
            
            check_in = record.get('check_in')
            check_in_str = check_in.strftime('%H:%M:%S') if check_in else "-"
            
            lunch_out = record.get('lunch_out')
            if lunch_out:
                l_dt = datetime.combine(lunch_out.date(), lunch_start_t)
                if lunch_out < l_dt and (l_dt - lunch_out).total_seconds() <= 300:
                    lunch_out_str = f"{lunch_start_str} ({lunch_out.strftime('%H:%M:%S')})"
                else:
                    lunch_out_str = lunch_out.strftime('%H:%M:%S')
            else:
                lunch_out_str = "-"
            
            lunch_in = record.get('lunch_in')
            lunch_in_str = lunch_in.strftime('%H:%M:%S') if lunch_in else "-"
            
            check_out = record.get('check_out')
            check_out_str = check_out.strftime('%H:%M:%S') if check_out else "-"
            
            status = record.get('status', 'Unknown')
            if emp_id in open_breaks_dict and status not in ["Checked Out", "OUT", "Lunch Out"]:
                b_out = open_breaks_dict[emp_id]
                l_dt = datetime.combine(b_out.date(), lunch_start_t)
                if l_dt - timedelta(minutes=5) <= b_out <= l_dt:
                    status = "On Break (Pre-Lunch)"
                else:
                    status = "On Break"
            
            # --- 4. Row Styling & Status Formatting ---
            color = "white"
            is_active_shift = False
            
            if status in ["Checked In", "IN", "Present"]:
                color = "#00FF00" # Bright Green
                active_count += 1
                is_active_shift = True
            elif status in ["Checked Out", "OUT", "Checked Out (Manual)"]:
                color = "#8A9AA3" # Muted Light Blue/Grey
                completed_count += 1
            elif status == "Late":
                color = "orange"
                active_count += 1 
                is_active_shift = True
            elif status in ["Lunch Out", "On Break", "On Break (Pre-Lunch)"]:
                color = "yellow"
                active_count += 1
                is_active_shift = True
            
            # Additional fallback check: if they have a check-in but no check-out, they are active
            if check_in and not check_out:
                is_active_shift = True
            
            # Draw Data Row
            ctk.CTkLabel(self.scroll_frame, text=emp_id).grid(row=row_idx, column=0, pady=2, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll_frame, text=name).grid(row=row_idx, column=1, pady=2, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll_frame, text=check_in_str).grid(row=row_idx, column=2, pady=2, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll_frame, text=lunch_out_str).grid(row=row_idx, column=3, pady=2, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll_frame, text=lunch_in_str).grid(row=row_idx, column=4, pady=2, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll_frame, text=check_out_str).grid(row=row_idx, column=5, pady=2, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll_frame, text=status, text_color=color, font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=6, pady=2, padx=10, sticky="w")
            
            # Draw Actions (Force Out Button)
            if is_active_shift and not check_out:
                btn_force = ctk.CTkButton(
                    self.scroll_frame, 
                    text="Force Out", 
                    width=80, 
                    fg_color="#8B0000", 
                    hover_color="#A52A2A",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    command=lambda e=emp_id: self.on_force_out_click(e)
                )
                btn_force.grid(row=row_idx, column=7, pady=2, padx=5, sticky="ew")
            elif status in ["Checked Out", "OUT", "Checked Out (Manual)"]:
                ctk.CTkLabel(self.scroll_frame, text="Completed").grid(row=row_idx, column=7, pady=2, padx=10, sticky="w")
            else:
                ctk.CTkLabel(self.scroll_frame, text="-", text_color="gray50").grid(row=row_idx, column=7, pady=2, padx=10, sticky="ew")
            
        # Update Mini-Stats Ribbon
        self.lbl_active.configure(text=f"Active Shifts (IN): {active_count}")
        self.lbl_completed.configure(text=f"Completed Check-Outs: {completed_count}")
        
        # --- Refresh Break Tracking Panel ---
        for widget in self.break_scroll.winfo_children():
            widget.destroy()
            
        break_cols = ["Name", "Break Out", "Break In", "Status / Remaining"]
        for i in range(len(break_cols)):
            self.break_scroll.grid_columnconfigure(i, weight=1, uniform="break_col")
            
        for i, col in enumerate(break_cols):
            b_header = ctk.CTkLabel(self.break_scroll, text=col, font=ctk.CTkFont(weight="bold"), fg_color="gray25", corner_radius=4)
            b_header.grid(row=0, column=i, pady=5, padx=2, sticky="ew")
            
        breaks = self.app.db._execute(
            """
            SELECT b.employee_id, e.employee_name, b.break_out, b.break_in
            FROM employee_breaks b
            JOIN employees e ON b.employee_id = e.employee_id
            WHERE b.break_date = CURDATE()
            ORDER BY b.break_out DESC
            """,
            (), fetch="all", dictionary=True
        )
        
        if not breaks:
            ctk.CTkLabel(self.break_scroll, text="No breaks logged today.", text_color="gray60").grid(row=1, column=0, columnspan=4, pady=20)
        else:
            for r_idx, b_record in enumerate(breaks, start=1):
                b_name = b_record["employee_name"]
                b_out = b_record["break_out"].strftime('%H:%M:%S') if b_record["break_out"] else "-"
                b_in = b_record["break_in"].strftime('%H:%M:%S') if b_record["break_in"] else "-"
                
                ctk.CTkLabel(self.break_scroll, text=b_name).grid(row=r_idx, column=0, pady=2, padx=10, sticky="w")
                ctk.CTkLabel(self.break_scroll, text=b_out).grid(row=r_idx, column=1, pady=2, padx=10, sticky="w")
                ctk.CTkLabel(self.break_scroll, text=b_in).grid(row=r_idx, column=2, pady=2, padx=10, sticky="w")
                
                if b_record["break_in"] is None:
                    b_out = b_record["break_out"]
                    l_dt = datetime.combine(b_out.date(), lunch_start_t)
                    if l_dt - timedelta(minutes=5) <= b_out <= l_dt:
                        ctk.CTkLabel(self.break_scroll, text="On Break (Pre-Lunch)", text_color="orange", font=ctk.CTkFont(weight="bold")).grid(row=r_idx, column=3, pady=2, padx=10, sticky="w")
                    else:
                        ctk.CTkLabel(self.break_scroll, text="Currently on Break", text_color="orange", font=ctk.CTkFont(weight="bold")).grid(row=r_idx, column=3, pady=2, padx=10, sticky="w")
                else:
                    ctk.CTkLabel(self.break_scroll, text="Active", text_color="green", font=ctk.CTkFont(weight="bold")).grid(row=r_idx, column=3, pady=2, padx=10, sticky="w")

    def on_force_out_click(self, emp_id):
        try:
            if hasattr(self.app.attendance_service, 'force_checkout'):
                success = self.app.attendance_service.force_checkout(emp_id)
                if success:
                    self.load_attendance()
                    logger.info(f"Admin manually forced out employee {emp_id}")
            else:
                logger.warning(f"force_checkout not implemented yet on attendance_service")
        except Exception as e:
            logger.error(f"Error forcing checkout for {emp_id}: {e}")
