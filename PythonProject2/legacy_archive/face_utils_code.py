"""
face_utils_code.py  (root-level backward-compatibility shim)
============================================================
The FaceRecognizer has been vectorized and optimized, and now lives in
the `face_engine` package.

This module re-exports it so that any existing imports continue to work
without modification:

    from face_utils_code import FaceRecognizer   # still works

Do NOT add business logic here. All face recognition code lives in face_engine/recognizer.py.
"""

from face_engine.recognizer import FaceRecognizer  # noqa: F401

__all__ = ["FaceRecognizer"]