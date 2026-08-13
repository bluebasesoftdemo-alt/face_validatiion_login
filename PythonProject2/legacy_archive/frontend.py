import tkinter as tk
from attendance_controller import AttendanceController

def start_camera():
    app = AttendanceController(0)
    app.run()

root = tk.Tk()
root.title("Face Attendance System")

btn = tk.Button(root, text="Start Camera", command=start_camera)
btn.pack(pady=20)

root.mainloop()