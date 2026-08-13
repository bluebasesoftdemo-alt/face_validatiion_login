import customtkinter as ctk
import cv2
import threading
import numpy as np
import os
from PIL import Image
from core.logger import get_logger
import config
from face_engine.recognizer import FaceRecognizer

logger = get_logger(__name__)

class EmployeeManagement(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color="transparent")
        self.app = app
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        
        # Header
        ctk.CTkLabel(self, text="Employee Management", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, columnspan=2, pady=20)
        
        # --- Left: Registration Form ---
        self.form_frame = ctk.CTkFrame(self, fg_color="gray10", corner_radius=10)
        self.form_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        ctk.CTkLabel(self.form_frame, text="Register New Employee", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=20)
        
        self.entry_id = ctk.CTkEntry(self.form_frame, placeholder_text="🆔 Employee ID (e.g. EMP001)", height=40, border_width=1)
        self.entry_id.pack(pady=10, padx=30, fill="x")
        
        self.entry_name = ctk.CTkEntry(self.form_frame, placeholder_text="👤 Full Name", height=40, border_width=1)
        self.entry_name.pack(pady=10, padx=30, fill="x")
        
        self.entry_dept = ctk.CTkEntry(self.form_frame, placeholder_text="🏢 Department (Optional)", height=40, border_width=1)
        self.entry_dept.pack(pady=10, padx=30, fill="x")
        
        self.btn_capture = ctk.CTkButton(self.form_frame, text="📷 Start Face Capture", command=self.start_capture, height=45, corner_radius=8, hover_color="#2980b9")
        self.btn_capture.pack(pady=20, padx=30, fill="x")
        
        self.capture_status = ctk.CTkLabel(self.form_frame, text="", text_color="yellow")
        self.capture_status.pack()
        
        # Dashed Viewport for Preview
        self.preview_frame = ctk.CTkFrame(self.form_frame, width=200, height=200, border_width=2, corner_radius=10, border_color="gray30", fg_color="transparent")
        self.preview_frame.pack(pady=15)
        self.preview_frame.pack_propagate(False)
        self.preview_label = ctk.CTkLabel(self.preview_frame, text="👤", font=ctk.CTkFont(size=80), text_color="gray30")
        self.preview_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # --- Right: Employee List ---
        self.list_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.list_frame.grid(row=1, column=1, padx=20, pady=10, sticky="nsew")
        
        self.list_header_frame = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        self.list_header_frame.pack(fill="x")
        
        ctk.CTkLabel(self.list_header_frame, text="Employee Directory", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left", padx=10, pady=10)
        self.btn_refresh = ctk.CTkButton(self.list_header_frame, text="↻ Refresh", command=self.load_employees, width=100, height=35, corner_radius=6, hover_color="gray40")
        self.btn_refresh.pack(side="right", padx=10, pady=10)
        
        self.scroll_frame = ctk.CTkScrollableFrame(self.list_frame, fg_color="gray10", corner_radius=10)
        self.scroll_frame.pack(fill="both", expand=True, pady=(10,0))
        
        self.recognizer = FaceRecognizer()
        
    def start(self):
        self.load_employees()
        
    def stop(self):
        pass
        
    def load_employees(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
            
        employees = self.app.employee_service.db.get_all_employees_info() 
        
        for i, emp in enumerate(employees):
            if not emp.get("is_active", True):
                continue
                
            card = ctk.CTkFrame(self.scroll_frame, fg_color="gray15", corner_radius=8)
            card.pack(fill="x", pady=5, padx=10)
            
            # Avatar Frame
            avatar_lbl = ctk.CTkLabel(card, text="👤", font=ctk.CTkFont(size=30), text_color="gray40", width=50, height=50)
            photo_path = emp.get("photo_path")
            if photo_path and os.path.exists(photo_path):
                try:
                    pil_img = Image.open(photo_path).resize((50, 50))
                    ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(50, 50))
                    avatar_lbl.configure(image=ctk_img, text="")
                    avatar_lbl.image = ctk_img
                except Exception as e:
                    logger.error(f"Could not load image {photo_path}: {e}")
            avatar_lbl.pack(side="left", padx=10, pady=10)
            
            # Info Frame
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="y", pady=10, padx=10)
            
            name = emp.get('employee_name', 'Unknown')
            ctk.CTkLabel(info_frame, text=name, font=ctk.CTkFont(weight="bold", size=15)).pack(anchor="w")
            ctk.CTkLabel(info_frame, text=f"ID: {emp['employee_id']}", font=ctk.CTkFont(size=12), text_color="gray60").pack(anchor="w")
            
            # Status Badge
            badge = ctk.CTkLabel(card, text=" ✅ Active ", font=ctk.CTkFont(size=12, weight="bold"), text_color="white", fg_color="green", corner_radius=10)
            badge.pack(side="left", padx=20)
            
            # Delete Button
            btn_delete = ctk.CTkButton(
                card, 
                text="🗑️ Delete", 
                width=100, 
                height=35, 
                fg_color="#8B0000", 
                hover_color="#A52A2A", 
                corner_radius=8, 
                font=ctk.CTkFont(weight="bold"),
                command=lambda e=emp['employee_id']: self.delete_employee(e)
            )
            btn_delete.pack(side="right", padx=15, pady=10)

    def delete_employee(self, emp_id):
        try:
            self.app.employee_service.update_employee_status(emp_id, is_active=False)
            self.load_employees()
            if "dashboard" in self.app.frames:
                active_emps = self.app.employee_service.get_all_active_employees()
                self.app.frames["dashboard"].recognizer.load_employees(active_emps)
        except Exception as e:
            logger.error(f"Failed to delete employee: {e}")

    def start_capture(self):
        emp_id = self.entry_id.get().strip()
        name = self.entry_name.get().strip()
        dept = self.entry_dept.get().strip()
        
        if not emp_id or not name:
            self.capture_status.configure(text="ID and Name are required!", text_color="red")
            return
            
        self.btn_capture.configure(state="disabled")
        self.capture_status.configure(text="Initializing camera...", text_color="yellow")
        
        # Setup data/profiles directory
        os.makedirs("data/profiles", exist_ok=True)
        
        threading.Thread(target=self.capture_process, args=(emp_id, name, dept), daemon=True).start()
        
    def capture_process(self, emp_id, name, dept):
        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        
        collected_data = [] # List of tuples: (embedding, frame, score)
        
        for _ in range(60): # 60 attempts to get 10 good frames
            ret, frame = cap.read()
            if not ret:
                continue
                
            # Update Preview
            display_frame = cv2.resize(frame, (200, 200))
            rgb_image = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_image)
            ctk_img = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(200, 200))
            self.preview_label.after(0, lambda img=ctk_img: self.preview_label.configure(image=img, text=""))
            
            faces = self.recognizer.detect_faces(frame)
            if faces:
                face = faces[0]
                # InsightFace det_score
                score = face.det_score if hasattr(face, 'det_score') else 0
                collected_data.append((face.embedding, frame.copy(), score))
                self.capture_status.after(0, lambda count=len(collected_data): self.capture_status.configure(text=f"Captured {count}/10"))
                
            if len(collected_data) >= 10:
                break
                
        cap.release()
        
        if len(collected_data) < 10:
            self.capture_status.after(0, lambda: self.capture_status.configure(text="Failed to capture 10 frames.", text_color="red"))
            self.btn_capture.after(0, lambda: self.btn_capture.configure(state="normal"))
            self.preview_label.after(0, lambda: self.preview_label.configure(image="", text="👤"))
            return
            
        # Vector average all 10 embeddings
        embeddings = [d[0] for d in collected_data]
        final_embedding = np.mean(embeddings, axis=0).astype(np.float32)
        
        # Select highest quality frame
        best_data = max(collected_data, key=lambda d: d[2])
        best_frame = best_data[1]
        
        # Compress and save
        photo_path = f"data/profiles/{emp_id}.jpg"
        cv2.imwrite(photo_path, best_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        
        # Clear temporary memory
        collected_data.clear()
        
        success = self.app.employee_service.register_employee(
            emp_id=emp_id, 
            name=name, 
            embedding=final_embedding.tobytes(), 
            department=dept,
            photo_path=photo_path
        )
        
        if success:
            self.capture_status.after(0, lambda: self.capture_status.configure(text="✅ Registration Complete", text_color="green"))
            # Update Dashboard embeddings
            if "dashboard" in self.app.frames:
                active_emps = self.app.employee_service.get_all_active_employees()
                self.app.frames["dashboard"].recognizer.load_employees(active_emps)
            self.after(0, self.load_employees)
        else:
            self.capture_status.after(0, lambda: self.capture_status.configure(text="❌ Registration Failed (ID Exists?)", text_color="red"))
            
        self.btn_capture.after(0, lambda: self.btn_capture.configure(state="normal"))
        self.preview_label.after(0, lambda: self.preview_label.configure(image="", text="👤"))
