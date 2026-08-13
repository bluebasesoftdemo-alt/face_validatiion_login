"""
database.py  (root-level backward-compatibility shim)
======================================================
The ``Database`` class has been moved to ``core/database.py`` to live alongside
the logger and exceptions in the foundation package.

This module re-exports it so that all existing imports continue to work
without any changes:

    from database import Database   # still works

Do NOT add business logic here.  All database code lives in core/database.py.
"""

from core.database import Database  # noqa: F401  (re-export)

__all__ = ["Database"]