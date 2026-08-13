import customtkinter as ctk
import pandas as pd
from datetime import datetime
import os
from core.logger import get_logger

logger = get_logger(__name__)

class Reports(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color="transparent")
        self.app = app
        
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        now = datetime.now()
        
        # --- 1. Top Filter & Action Bar ---
        self.filter_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.filter_bar.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        
        # Left side: Filters
        filter_group = ctk.CTkFrame(self.filter_bar, fg_color="transparent")
        filter_group.pack(side="left")
        
        self.year_var = ctk.StringVar(value=str(now.year))
        self.month_var = ctk.StringVar(value=str(now.month))
        self.dept_var = ctk.StringVar(value="All")
        
        self.year_enabled_var = ctk.BooleanVar(value=True)
        self.month_enabled_var = ctk.BooleanVar(value=True)
        
        self.year_var.trace_add("write", self.on_filter_change)
        self.month_var.trace_add("write", self.on_filter_change)
        self.dept_var.trace_add("write", self.on_filter_change)
        
        # Validation Command for Year
        vcmd = (self.register(self.validate_year), '%P')
        
        # Year Group
        ctk.CTkLabel(filter_group, text="Year:").pack(side="left", padx=(0, 5))
        self.year_entry = ctk.CTkEntry(filter_group, textvariable=self.year_var, width=60, validate="key", validatecommand=vcmd)
        self.year_entry.pack(side="left", padx=(0, 5))
        self.chk_year = ctk.CTkCheckBox(filter_group, text="Enable", variable=self.year_enabled_var, command=self.toggle_year, width=60)
        self.chk_year.pack(side="left", padx=(0, 15))
        
        # Month Group (Dropdown)
        ctk.CTkLabel(filter_group, text="Month:").pack(side="left", padx=(0, 5))
        self.month_entry = ctk.CTkComboBox(filter_group, variable=self.month_var, values=[str(i) for i in range(1, 13)], state="readonly", width=70)
        self.month_entry.pack(side="left", padx=(0, 5))
        self.chk_month = ctk.CTkCheckBox(filter_group, text="Enable", variable=self.month_enabled_var, command=self.toggle_month, width=60)
        self.chk_month.pack(side="left", padx=(0, 15))
        
        # Department Group
        ctk.CTkLabel(filter_group, text="Department:").pack(side="left", padx=(0, 5))
        self.dept_dropdown = ctk.CTkComboBox(filter_group, variable=self.dept_var, values=["All"], state="readonly", width=140)
        self.dept_dropdown.pack(side="left", padx=(0, 15))
        
        # Right side: Export button
        self.btn_export = ctk.CTkButton(self.filter_bar, text="Export to Excel", command=self.export_excel, font=ctk.CTkFont(weight="bold"))
        self.btn_export.pack(side="right")
        
        # --- 2. Analytics Summary Row ---
        self.analytics_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.analytics_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        self.analytics_frame.grid_columnconfigure((0,1,2), weight=1, uniform="card")
        
        self.card_days = self.create_stat_card(self.analytics_frame, "Days Tracked", "0 Days", 0, "Active operations in filtered range")
        self.card_ontime = self.create_stat_card(self.analytics_frame, "On-Time Performance", "0.0%", 1)
        self.card_late = self.create_stat_card(self.analytics_frame, "Late Incidents", "0 Incidents", 2, val_color="orange")
        
        # --- 3. Live Preview Data Table ---
        self.table_container = ctk.CTkFrame(self)
        self.table_container.grid(row=2, column=0, sticky="nsew", padx=20, pady=(10, 10))
        self.table_container.grid_rowconfigure(0, weight=1)
        self.table_container.grid_columnconfigure(0, weight=1)
        
        # Scrollable rows (Headers included inside to ensure perfect column alignment)
        self.scroll_table = ctk.CTkScrollableFrame(self.table_container, corner_radius=0, fg_color="transparent")
        self.scroll_table.grid(row=0, column=0, sticky="nsew")
        
        self.status_label = ctk.CTkLabel(self, text="")
        self.status_label.grid(row=3, column=0, pady=(0, 10))
        
        self.current_raw_data = []

    def validate_year(self, P):
        if P == "" or P.isdigit():
            if hasattr(self, "status_label"):
                self.status_label.configure(text="")
            return True
        else:
            if hasattr(self, "status_label"):
                self.status_label.configure(text="Invalid Input: Year must contain digits only!", text_color="red")
            return False

    def create_stat_card(self, parent, title, default_val, col, subtext="", val_color=None):
        card = ctk.CTkFrame(parent, border_width=1, border_color="gray30")
        card.grid(row=0, column=col, padx=10, sticky="ew")
        
        ctk.CTkLabel(card, text=title, text_color="gray60", font=ctk.CTkFont(size=12)).pack(pady=(15, 5))
        lbl_val = ctk.CTkLabel(card, text=default_val, font=ctk.CTkFont(size=24, weight="bold"), text_color=val_color)
        lbl_val.pack(pady=0)
        
        if subtext:
            ctk.CTkLabel(card, text=subtext, text_color="gray50", font=ctk.CTkFont(size=10)).pack(pady=(0, 10))
        else:
            ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=10)).pack(pady=(0, 10)) # padding consistency
            
        return lbl_val

    def start(self):
        self.populate_departments()
        self.refresh_data()
        
    def stop(self):
        pass

    def toggle_year(self):
        if self.year_enabled_var.get():
            self.year_entry.configure(state="normal")
        else:
            self.year_entry.configure(state="disabled")
        self.refresh_data()

    def toggle_month(self):
        if self.month_enabled_var.get():
            self.month_entry.configure(state="readonly")
        else:
            self.month_entry.configure(state="disabled")
        self.refresh_data()

    def populate_departments(self):
        try:
            employees = self.app.employee_service.get_all_active_employees()
            depts = set(emp.get("department") for emp in employees if emp.get("department"))
            depts_list = ["All"] + sorted(list(depts))
            self.dept_dropdown.configure(values=depts_list)
            if self.dept_var.get() not in depts_list:
                self.dept_var.set("All")
        except Exception as e:
            logger.error(f"Error loading departments: {e}")

    def on_filter_change(self, *args):
        # Triggered by text typing. We only refresh if it's a valid digit or empty (meaning disabled soon)
        self.refresh_data()

    def refresh_data(self):
        year = None
        if self.year_enabled_var.get():
            try:
                y = int(self.year_var.get())
                if 2000 <= y <= 2100:
                    year = y
                else:
                    return # invalid year while typing
            except ValueError:
                return
                
        month = None
        if self.month_enabled_var.get():
            try:
                m = int(self.month_var.get())
                if 1 <= m <= 12:
                    month = m
                else:
                    return # invalid month while typing
            except ValueError:
                return
            
        dept = self.dept_var.get()
        self.current_raw_data = self.app.report_service.get_monthly_raw_data(year, month, dept)
        
        # Update analytics cards
        stats = self.app.report_service.get_monthly_analytics(self.current_raw_data)
        self.card_days.configure(text=stats["total_days"])
        self.card_ontime.configure(text=stats["ontime_rate"])
        self.card_late.configure(text=stats["total_late"])
        
        # Render Table
        self.render_table()
        
    def render_table(self):
        # Clear table
        for widget in self.scroll_table.winfo_children():
            widget.destroy()
            
        columns = ["Date", "Employee ID", "Name", "Check-In", "Check-Out", "Status"]
        for i, col in enumerate(columns):
            self.scroll_table.grid_columnconfigure(i, weight=1, uniform="col")
            
        # Draw Headers (Row 0)
        for i, col in enumerate(columns):
            header_lbl = ctk.CTkLabel(self.scroll_table, text=col, font=ctk.CTkFont(weight="bold"), fg_color="gray25", corner_radius=4)
            header_lbl.grid(row=0, column=i, pady=5, padx=2, sticky="ew")
            
        if not self.current_raw_data:
            ctk.CTkLabel(self.scroll_table, text="No attendance records found for this period.", text_color="gray60").grid(row=1, column=0, columnspan=6, pady=40)
            return
            
        # Render table rows (limit to 200 for preview performance)
        for row_idx, record in enumerate(self.current_raw_data[:200], start=1):
            date_str = record.get("Date").strftime("%Y-%m-%d") if record.get("Date") else ""
            in_str = record.get("Check-In").strftime("%H:%M:%S") if record.get("Check-In") else "--"
            out_str = record.get("Check-Out").strftime("%H:%M:%S") if record.get("Check-Out") else "--"
            
            # Format status with color if late
            status_text = record.get("Status", "")
            is_late = record.get("is_late", 0)
            if is_late:
                status_text = "Late"
                
            status_color = "orange" if is_late else "white"
            
            ctk.CTkLabel(self.scroll_table, text=date_str).grid(row=row_idx, column=0, pady=2, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll_table, text=record.get("Employee ID", "")).grid(row=row_idx, column=1, pady=2, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll_table, text=record.get("Name", "")).grid(row=row_idx, column=2, pady=2, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll_table, text=in_str).grid(row=row_idx, column=3, pady=2, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll_table, text=out_str).grid(row=row_idx, column=4, pady=2, padx=10, sticky="w")
            ctk.CTkLabel(self.scroll_table, text=status_text, text_color=status_color).grid(row=row_idx, column=5, pady=2, padx=10, sticky="w")
            
        if len(self.current_raw_data) > 200:
            ctk.CTkLabel(self.scroll_table, text=f"...and {len(self.current_raw_data)-200} more rows (Export to Excel to view all)", text_color="gray60").grid(row=201, column=0, columnspan=6, pady=20)

    def export_excel(self):
        if not self.current_raw_data:
            self.status_label.configure(text="No data to export.", text_color="orange")
            return
            
        self.status_label.configure(text="Generating report...", text_color="yellow")
        self.update()
        
        try:
            # We want to drop the raw 'is_late' from the excel and just format correctly
            df = pd.DataFrame(self.current_raw_data)
            
            # Format datetime columns to timezone-naive strings for excel
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
            if "Check-In" in df.columns:
                df["Check-In"] = pd.to_datetime(df["Check-In"]).dt.strftime("%H:%M:%S")
            if "Check-Out" in df.columns:
                df["Check-Out"] = pd.to_datetime(df["Check-Out"]).dt.strftime("%H:%M:%S")
                
            # Update Status text based on is_late
            if "is_late" in df.columns:
                df.loc[df["is_late"] == 1, "Status"] = "Late"
                df = df.drop(columns=["is_late"])
                
            os.makedirs("exports", exist_ok=True)
            year_str = self.year_var.get() if self.year_enabled_var.get() else "AllY"
            month_str = self.month_var.get().zfill(2) if self.month_enabled_var.get() else "AllM"
            dept_str = self.dept_var.get().replace(" ", "_")
            
            filename = f"exports/Attendance_Report_{year_str}_{month_str}_{dept_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            df.to_excel(filename, index=False)
            
            self.status_label.configure(text=f"Exported successfully to {filename}", text_color="green")
            logger.info(f"Report exported to {filename}")
        except Exception as e:
            self.status_label.configure(text=f"Export failed: {e}", text_color="red")
            logger.error(f"Excel export failed: {e}")
