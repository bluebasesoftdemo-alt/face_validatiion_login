"""
face_engine/liveness.py
=======================
Optional Anti-spoofing / Liveness detection module.

Architectural Improvements (Phase 2):
1. Implements a placeholder structure using the `EAR_THRESHOLD` from `config.py`
   (originally `blinkconfig.py`).
2. NOTE: The project requires preserving the `buffalo_l` model from InsightFace.
   `buffalo_l` uses the RetinaFace detector which only outputs 5 facial landmarks
   (2 eyes, nose, 2 mouth corners). Eye Aspect Ratio (EAR) requires the full
   68-point facial landmark set (specifically 6 points mapping the eye contour).
   Because we must not change the model (per requirements), EAR cannot be computed
   using the current embeddings. 
   
   This module provides a basic pass-through for now. In a future phase, a secondary
   model (like MediaPipe FaceMesh) could be injected here if EAR is strictly needed,
   or a different heuristic can be used.
"""

from typing import Dict, Any
import config
from core.logger import get_logger

logger = get_logger(__name__)

class LivenessDetector:
    """
    Evaluates whether the detected face belongs to a live person.
    """
    def __init__(self):
        self.ear_threshold = config.EAR_THRESHOLD
        self.consecutive_frames = config.CONSECUTIVE_FRAMES
        
        self.enabled = False # Disabled by default due to model limitations
        
        logger.info(
            "LivenessDetector initialized (EAR=%.2f, Frames=%d). Currently running in PASS-THROUGH mode.",
            self.ear_threshold, self.consecutive_frames
        )

    def is_live(self, face_obj: Any) -> bool:
        """
        Determine if the face is live.
        
        Args:
            face_obj: The Face object returned by InsightFace FaceAnalysis.
            
        Returns:
            True if determined to be live (or if disabled), False otherwise.
        """
        if not self.enabled:
            return True
            
        # Fallback/Placeholder: 
        # If enabled, logic relying on 68-point landmarks or 
        # depth sensors / anti-spoofing models would go here.
        # Currently, RetinaFace only provides `face_obj.kps` (5 landmarks).
        
        return True
