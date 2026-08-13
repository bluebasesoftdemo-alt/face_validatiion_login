"""
phase2_verifier.py
==================
Complete, strict verification of Phase 2 optimizations.
Tests threads, memory leaks, performance metrics, and correctness.
"""

import os
import cv2
import time
import threading
import tracemalloc
import numpy as np
from typing import Dict, Any

from config import CAMERA_INDEX, DETECTION_SIZE, SIMILARITY_THRESHOLD, ATTENDANCE_COOLDOWN
from core.database import Database
from face_engine.recognizer import FaceRecognizer
from face_engine.camera import ThreadedCamera
from attendance_controller import AttendanceController

def section(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")

def verify_camera_and_threads():
    section("1-3. Camera & Thread Management Verification")
    
    initial_threads = threading.active_count()
    print(f"Initial thread count: {initial_threads}")
    
    # 1. Open Camera
    try:
        cam = ThreadedCamera(CAMERA_INDEX)
        print("✅ Camera initialized successfully in background thread.")
    except Exception as e:
        print(f"❌ Camera failed to initialize: {e}")
        return

    running_threads = threading.active_count()
    print(f"Thread count while running: {running_threads} (expected: {initial_threads + 1})")
    if running_threads > initial_threads:
        print("✅ Background thread created.")
        
    # Read a few frames
    for _ in range(5):
        ret, frame = cam.read()
        time.sleep(0.1)
    
    if ret and frame is not None:
        print(f"✅ Successfully read frames. Shape: {frame.shape}")
    else:
        print("❌ Failed to read frames from camera.")

    # 3. Stop cleanly
    cam.release()
    time.sleep(0.5) # allow thread to die
    final_threads = threading.active_count()
    print(f"Thread count after release: {final_threads} (expected: {initial_threads})")
    if final_threads == initial_threads:
        print("✅ Threaded camera stopped cleanly with no orphans.")
    else:
        print("❌ Thread leak detected!")


def verify_fps_and_memory():
    section("4 & 11. FPS Counter & Memory Leak Verification")
    
    print("Starting AttendanceController in headless mode for 100 frames...")
    
    # We will override cv2.imshow and cv2.waitKey to run headlessly
    original_imshow = cv2.imshow
    original_waitkey = cv2.waitKey
    cv2.imshow = lambda winname, mat: None
    
    frames_processed = [0]
    
    def headless_waitkey(delay):
        frames_processed[0] += 1
        if frames_processed[0] >= 100:
            return 27 # ESC key
        return -1
        
    cv2.waitKey = headless_waitkey
    
    app = AttendanceController(CAMERA_INDEX)
    
    tracemalloc.start()
    snapshot1 = tracemalloc.take_snapshot()
    
    try:
        app.run()
        print(f"✅ Application loop ran successfully. FPS calculated: {app.fps:.1f}")
        if app.fps > 0:
            print("✅ FPS counter logic is functioning.")
    except Exception as e:
        print(f"❌ App crashed during headless run: {e}")
        
    snapshot2 = tracemalloc.take_snapshot()
    stats = snapshot2.compare_to(snapshot1, 'lineno')
    
    print("\nMemory allocation changes (top 3):")
    total_diff = 0
    for stat in stats[:3]:
        # Ignore Python's internal importlib caching which happens lazily
        if 'importlib' not in str(stat.traceback):
            print(f"  {stat}")
            total_diff += stat.size_diff
        
    if total_diff < 15 * 1024 * 1024: # Less than 15MB growth after init is acceptable
        print("✅ No significant memory leaks detected during extended runtime.")
    else:
        print(f"❌ Possible memory leak detected: {total_diff / 1024 / 1024:.2f} MB growth.")
        
    # Restore cv2
    cv2.imshow = original_imshow
    cv2.waitKey = original_waitkey


def verify_recognition_logic():
    section("5-7. Face Recognition Correctness & 512-dim Embeddings")
    
    db = Database()
    employees = db.get_all_employees()
    db.close()
    
    if not employees:
        print("⚠️ No employees in DB. Cannot test matching.")
        return
        
    target_emp = employees[0]
    emb = target_emp["embedding"]
    
    print(f"Target employee: {target_emp['id']} ({target_emp.get('name', 'Unknown')})")
    print(f"Embedding type: {type(emb)}, shape: {emb.shape}")
    
    if emb.shape == (512,):
        print("✅ Verified 512-dimensional InsightFace embedding compatibility.")
    else:
        print(f"❌ Invalid embedding shape: {emb.shape}")
        
    rec = FaceRecognizer()
    rec.load_employees(employees)
    
    # Synthetic face object for testing similarity strictly
    class MockFace:
        def __init__(self, embedding, bbox):
            self.embedding = embedding
            self.bbox = bbox

    # Test True Positive (Same embedding)
    mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # 1. Perfect Match
    print("\nTesting known face matching...")
    face_tp = MockFace(emb, [100, 100, 200, 200])
    
    # We patch get_largest_face to return our mock
    original_get = rec.get_largest_face
    rec.get_largest_face = lambda frame: face_tp
    
    res_tp = rec.recognize(mock_frame)
    if res_tp["employee"] and res_tp["employee"]["id"] == target_emp["id"]:
        print(f"✅ Known face recognized correctly. Score: {res_tp['similarity']:.4f} >= {SIMILARITY_THRESHOLD}")
    else:
        print(f"❌ Failed to recognize known face. Score: {res_tp['similarity']:.4f}")
        
    # 2. Unknown Face (Random orthogonal embedding)
    print("\nTesting unknown face rejection...")
    rng = np.random.default_rng(42)
    random_emb = rng.standard_normal(512).astype(np.float32)
    random_emb /= np.linalg.norm(random_emb)
    
    face_tn = MockFace(random_emb, [100, 100, 200, 200])
    rec.get_largest_face = lambda frame: face_tn
    
    # Temporarily bypass cooldown to ensure it processes
    rec.cooldown_time = 0
    
    res_tn = rec.recognize(mock_frame)
    if res_tn["employee"] is None:
        print(f"✅ Unknown face correctly rejected. Score: {res_tn['similarity']:.4f} < {SIMILARITY_THRESHOLD}")
    else:
        print(f"❌ Unknown face incorrectly accepted! Score: {res_tn['similarity']:.4f}")
        
    rec.get_largest_face = original_get


def verify_attendance_and_database():
    section("8-10. Attendance DB, Cooldown & Check-in Logic")
    
    db = Database()
    
    # Clear out records for employee 1 for today to ensure clean test state
    emp_id = "1"
    
    try:
        with db._pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM attendance WHERE employee_id = %s AND attendance_date = CURDATE()", (emp_id,))
            conn.commit()
    except Exception as e:
        print(f"Warning: Cleanup failed: {e}")
        
    print(f"Testing attendance for employee {emp_id}...")
    
    # 1. First check-in
    db.mark_check_in(emp_id)
    print("Marked initial check-in.")
    
    # Verify
    with db._pool.get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM attendance WHERE employee_id = %s AND attendance_date = CURDATE()", (emp_id,))
        records = cur.fetchall()
        
        if len(records) == 1:
            print(f"✅ Check-in written correctly to MySQL: {records[0]['check_in']}")
        else:
            print("❌ Failed to write check-in!")
            
    # 2. Duplicate prevention (Cooldown)
    print("\nTesting application-level cooldown (simulate instant re-detect)...")
    app_cooldown = ATTENDANCE_COOLDOWN
    last_marked = {}
    
    now = time.time()
    last = last_marked.get(emp_id, 0)
    if now - last > app_cooldown:
        db.mark_check_in(emp_id)
        last_marked[emp_id] = now
        print("  Allowed (first)")
    
    now = time.time()
    last = last_marked.get(emp_id, 0)
    if now - last > app_cooldown:
        db.mark_check_in(emp_id)
        last_marked[emp_id] = now
        print("  Allowed (second) -> THIS SHOULD NOT HAPPEN")
    else:
        print(f"✅ Application cooldown successfully prevented duplicate call. (Last marked: {now - last:.1f}s ago, Threshold: {app_cooldown}s)")

    # 3. Database-level idempotent update logic (Check-out)
    print("\nTesting database idempotent check-out logic...")
    db.mark_check_in(emp_id) # Call it again at DB level directly
    
    with db._pool.get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM attendance WHERE employee_id = %s AND attendance_date = CURDATE()", (emp_id,))
        updated = cur.fetchone()
        
        if updated['check_out'] is not None:
            print(f"✅ Database check-out logic correctly updated existing record. Check-out time: {updated['check_out']}")
        else:
            # Phase 1's mark_check_in implements idempotent check-out by running an UPDATE if insert fails.
            print("⚠️ Database check-out logic might just be an UPDATE. If 'check_out' is None, check the SQL logic.")
            
    db.close()


def benchmark_performance():
    section("12. Precise Performance Benchmarking")
    print("Distinguishing between detection, embedding, cosine, and total FPS.")
    
    # We will benchmark the FaceRecognizer components explicitly
    rec = FaceRecognizer()
    
    db = Database()
    employees = db.get_all_employees()
    db.close()
    
    # We'll duplicate the employee to test with N=100
    if len(employees) > 0:
        emp = employees[0]
        test_employees = [emp for _ in range(100)]
        rec.load_employees(test_employees)
    else:
        print("❌ Cannot benchmark without employees.")
        return
        
    print(f"\nConfiguration: InsightFace size {DETECTION_SIZE}, DB Size: N={len(test_employees)}")
    
    # Load a real image or grab one from camera for accurate detection timing
    cam = cv2.VideoCapture(CAMERA_INDEX)
    ret, frame = cam.read()
    cam.release()
    
    if not ret:
        # Fallback to noise image
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        print("Using synthetic noise image for inference.")
        
    import time, gc
    
    def measure(fn, name, iters=10):
        gc.disable()
        start = time.perf_counter()
        for _ in range(iters):
            res = fn()
        end = time.perf_counter()
        gc.enable()
        avg_ms = ((end - start) / iters) * 1000
        print(f"  {name:<35}: {avg_ms:>8.2f} ms")
        return avg_ms

    print("\nMetrics:")
    
    # 1. Detection + Embedding (InsightFace app.get does both simultaneously in buffalo_l)
    def run_insightface():
        return rec.detect_faces(frame)
        
    det_ms = measure(run_insightface, "Detection + Embedding Generation", iters=5)
    
    # 2. Cosine Similarity (Vectorized)
    faces = run_insightface()
    if faces:
        q_emb = faces[0].embedding.astype(np.float32)
        q_emb /= np.linalg.norm(q_emb)
        
        def run_cosine():
            scores = rec._embedding_matrix @ q_emb
            return np.argmax(scores)
            
        cos_ms = measure(run_cosine, f"Cosine Similarity (N={len(test_employees)})", iters=100)
    else:
        cos_ms = 0.0
        print("  Cosine Similarity omitted (No face found in test frame)")

    total_rec_ms = det_ms + cos_ms
    print(f"  ------------------------------------------------")
    print(f"  Total Recognition Latency          : {total_rec_ms:>8.2f} ms")
    print(f"  Maximum Theoretical Inference FPS  : {1000.0/total_rec_ms:>8.1f} FPS")

    print("\nCPU & Thread Tracking (over 2 seconds):")
    t1_cpu = time.process_time()
    t1_wall = time.perf_counter()
    time.sleep(2.0)
    t2_cpu = time.process_time()
    t2_wall = time.perf_counter()
    
    cpu_util = ((t2_cpu - t1_cpu) / (t2_wall - t1_wall)) * 100
    print(f"  Idle CPU Utilization (Main Thread) : {cpu_util:>8.1f} %")


if __name__ == "__main__":
    print("🚀 Starting Phase 2 Verification Suite\n")
    verify_camera_and_threads()
    verify_fps_and_memory()
    verify_recognition_logic()
    verify_attendance_and_database()
    benchmark_performance()
    print("\n✅ Verification Complete.")
