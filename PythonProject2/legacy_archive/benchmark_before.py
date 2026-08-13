"""
benchmark_before.py
===================
PHASE 2 — BEFORE Benchmark.
Captures baseline performance metrics using the original approach.
Run this BEFORE Phase 2 changes are applied.

Measures (no camera required):
  1. DB query time       : get_all_employees()
  2. Cosine similarity   : original O(n) loop vs vectorized (numpy)
  3. Frame I/O penalty   : print() call overhead per frame
  4. Estimated FPS       : based on recognition latency
"""

import time
import gc
import statistics
import numpy as np

# ── Helpers ───────────────────────────────────────────────────────────────────

def _timeit(fn, iterations=200):
    """Return mean and std of fn() runtime in milliseconds."""
    gc.disable()
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    gc.enable()
    return statistics.mean(times), statistics.stdev(times)


def section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


# ── 1. Database query timing ──────────────────────────────────────────────────
section("1. DATABASE QUERY — get_all_employees()")
try:
    from database import Database
    db = Database()
    mean_ms, std_ms = _timeit(db.get_all_employees, iterations=50)
    print(f"  get_all_employees()  :  {mean_ms:.2f} ms  (±{std_ms:.2f})")
    emp_count = len(db.get_all_employees())
    print(f"  Employees in DB      :  {emp_count}")
    db.close()
except Exception as e:
    print(f"  DB test skipped: {e}")


# ── 2. Original cosine loop vs vectorized ─────────────────────────────────────
section("2. RECOGNITION — Old O(n) Loop vs Vectorized (Numpy)")

EMB_DIM = 512
test_sizes = [1, 5, 10, 20, 50, 100]

results = {}
for n in test_sizes:
    # Synthetic employee embeddings (unit vectors to match real data)
    embs = np.random.randn(n, EMB_DIM).astype(np.float32)
    norms = np.linalg.norm(embs, axis=1, keepdims=True)
    embs = embs / norms  # normalized

    query = np.random.randn(EMB_DIM).astype(np.float32)
    query /= np.linalg.norm(query)

    # ── Old approach: pairwise loop ───────────────────────────────────────────
    def old_cosine_loop():
        best = -1.0
        for i in range(n):
            a, b = query, embs[i]
            d = np.linalg.norm(a) * np.linalg.norm(b)
            s = float(np.dot(a, b) / d) if d > 0 else 0.0
            if s > best:
                best = s
        return best

    # ── New approach: vectorized matrix multiply ──────────────────────────────
    emb_matrix = embs  # already normalized
    def new_vectorized():
        scores = emb_matrix @ query
        return float(np.max(scores))

    old_mean, old_std = _timeit(old_cosine_loop, iterations=500)
    new_mean, new_std = _timeit(new_vectorized,  iterations=500)
    speedup = old_mean / new_mean if new_mean > 0 else float("inf")

    results[n] = {"old_ms": old_mean, "new_ms": new_mean, "speedup": speedup}
    print(f"  N={n:4d}  |  Old loop: {old_mean:.4f} ms  |  Vectorized: {new_mean:.4f} ms  |  Speedup: {speedup:.1f}x")


# ── 3. print() call overhead ──────────────────────────────────────────────────
section("3. print() OVERHEAD PER FRAME (stdout I/O cost)")
import io, sys

def print_call():
    print("Score: 0.9123456789  ID: EMP001")

# Redirect to /dev/null so it doesn't actually print
original_stdout = sys.stdout
sys.stdout = io.StringIO()
print_mean, _ = _timeit(print_call, iterations=500)
sys.stdout = original_stdout

print(f"  Single print() call  :  {print_mean:.4f} ms")
print(f"  At 30 FPS (1 emp)    :  {print_mean * 30:.2f} ms/sec consumed by I/O")
print(f"  At 30 FPS (10 emps)  :  {print_mean * 30 * 10:.2f} ms/sec consumed by I/O")
print(f"  (Original code prints EVERY score EVERY frame)")


# ── 4. Frame skip savings estimate ───────────────────────────────────────────
section("4. ESTIMATED FPS — Current vs Optimized")

# Typical InsightFace buffalo_l CPU inference: 80–200 ms per frame (640x640)
# Use conservative estimate
INSIGHTFACE_LATENCY_MS = 120.0
CAMERA_FPS = 30
TARGET_RECOG_FPS = 10  # How often we NEED to recognize (1 per 3 frames)

n = emp_count if 'emp_count' in dir() else 1
old_loop_ms = results.get(n, results[1])["old_ms"]
new_vec_ms  = results.get(n, results[1])["new_ms"]

old_total_ms = INSIGHTFACE_LATENCY_MS + old_loop_ms
new_total_ms = INSIGHTFACE_LATENCY_MS + new_vec_ms  # vectorized
new_skip_ms  = new_total_ms / 3                      # frame skipping (every 3 frames)

print(f"\n  Assumptions:")
print(f"    InsightFace inference (640x640, CPU)  :  ~{INSIGHTFACE_LATENCY_MS:.0f} ms")
print(f"    Employees in DB                        :  {n}")
print(f"    Recognition interval (new)             :  every 3 frames")
print(f"\n  Recognition latency per frame:")
print(f"    OLD (inference + loop, every frame)   :  {old_total_ms:.2f} ms  →  ~{1000/old_total_ms:.1f} recognition FPS")
print(f"    NEW (inference + vectorized, ev frame) :  {new_total_ms:.2f} ms  →  ~{1000/new_total_ms:.1f} recognition FPS")
print(f"    NEW (inference + vectorized, skip 3)   :  ~{new_skip_ms:.2f} ms effective overhead")
print(f"\n  Display FPS (camera captures at {CAMERA_FPS} FPS):")
print(f"    OLD: limited by recognition blocking the display loop")
print(f"    NEW: camera runs in background thread → display at full camera FPS")
print(f"\n  CPU load reduction (no print spam):")
print(f"    Eliminated: {print_mean * CAMERA_FPS * n:.2f} ms/sec of print() I/O")


# ── Summary table ─────────────────────────────────────────────────────────────
section("BEFORE/AFTER SUMMARY TABLE")
print(f"\n  {'Metric':<40}  {'BEFORE':<18}  {'AFTER (projected)'}")
print(f"  {'-'*40}  {'-'*18}  {'-'*18}")
print(f"  {'Cosine similarity (N=1)':<40}  {results[1]['old_ms']:.4f} ms       {results[1]['new_ms']:.4f} ms")
if 10 in results:
    print(f"  {'Cosine similarity (N=10)':<40}  {results[10]['old_ms']:.4f} ms       {results[10]['new_ms']:.4f} ms")
if 50 in results:
    print(f"  {'Cosine similarity (N=50)':<40}  {results[50]['old_ms']:.4f} ms       {results[50]['new_ms']:.4f} ms")
print(f"  {'Camera reads (blocking vs threaded)':<40}  Main thread      Background thread")
print(f"  {'print() per frame per employee':<40}  Yes              No (logger DEBUG)")
print(f"  {'Frame skip (recognition interval)':<40}  Every frame      Every 3rd frame")
print(f"  {'Cooldown management (dual bug)':<40}  2 places         1 place (controller)")
print(f"  {'Camera error handling':<40}  exit()           CameraError raise")
print(f"  {'Liveness check':<40}  None             PresenceLiveness")
