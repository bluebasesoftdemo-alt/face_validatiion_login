"""
face_engine/camera.py
=====================
Threaded camera frame capture.

Architectural Improvements (Phase 2):
1. Background Threading: OpenCV's `cap.read()` blocks the execution thread. If face 
   recognition takes 100ms, the camera buffer builds up, and the GUI will show "stale" 
   delayed frames. By running a background thread that constantly drains the buffer,
   we ensure `camera.read()` instantly returns the freshest frame.
2. Graceful Error Handling: Raises `CameraError` on failure instead of a hard `exit()`.
"""

import cv2
import threading
import time
from typing import Tuple, Optional
import numpy as np

import config
from core.logger import get_logger
from core.exceptions import CameraError

logger = get_logger(__name__)

class ThreadedCamera:
    """
    Constantly captures frames from the camera in a background thread.
    Keeps only the most recent frame in memory.
    """
    def __init__(self, camera_index: Optional[int] = None):
        self.camera_index = camera_index if camera_index is not None else config.CAMERA_INDEX
        self.cap = cv2.VideoCapture(self.camera_index)
        
        # Request minimal internal buffering from the OS/driver
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not self.cap.isOpened():
            raise CameraError(f"Failed to open camera at index {self.camera_index}")

        # Ensure we can read at least one frame
        self.ret, self.frame = self.cap.read()
        if not self.ret:
            self.cap.release()
            raise CameraError("Failed to read initial frame from camera.")

        self.running = True
        self.thread = threading.Thread(target=self._update, daemon=True, name="CameraThread")
        self.thread.start()
        
        logger.info("ThreadedCamera started on index %s", self.camera_index)

    def _update(self) -> None:
        """Background thread loop: continuously read frames and discard old ones."""
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                self.ret = ret
                self.frame = frame
            else:
                logger.warning("Camera frame dropped or stream ended.")
                time.sleep(0.01) # prevent tight looping if disconnected

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Returns the most recent frame instantly without blocking.
        Compatible with the `ret, frame = cap.read()` OpenCV pattern.
        """
        return self.ret, self.frame

    def release(self) -> None:
        """Stops the thread and releases the hardware."""
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self.cap.release()
        logger.info("ThreadedCamera released.")
