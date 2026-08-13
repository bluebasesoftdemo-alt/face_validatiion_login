simport cv2
import numpy as np
from insightface.app import FaceAnalysis
from database import Database
from services.employee_service import EmployeeService
import config
from core.logger import get_logger

logger = get_logger(__name__)

# Initialize DB and Services
db = Database()
employee_service = EmployeeService(db)

# We use the config constants for sizes
app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
app.prepare(ctx_id=0, det_size=config.DETECTION_SIZE)

cap = cv2.VideoCapture(config.CAMERA_INDEX)

emp_id = input("Enter Employee ID: ")
emp_name = input("Enter Name: ")

embeddings = []

print("Look at camera... collecting samples")

while len(embeddings) < 10:
    ret, frame = cap.read()
    if not ret:
        continue

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    faces = app.get(rgb)

    if len(faces) > 0:
        emb = faces[0].embedding.astype(np.float32)
        embeddings.append(emb)

        cv2.putText(frame, f"Captured {len(embeddings)}/10",
                    (30, 40), cv2.FONT_HERSHEY_SIMPLEX,
                    1, (0, 255, 0), 2)

    cv2.imshow("Register", frame)
    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()

if len(embeddings) > 0:
    final_embedding = np.mean(embeddings, axis=0)
    # Convert numpy array to bytes for the database
    embedding_bytes = final_embedding.tobytes()
    
    # Use the Service Layer to register the employee safely
    success = employee_service.register_employee(emp_id, emp_name, embedding_bytes)
    
    if success:
        print("✅ Registration completed successfully.")
    else:
        print("❌ Registration failed. Employee ID might already exist.")
else:
    print("⚠️ No face embeddings captured. Registration aborted.")

db.close()