"""Compatibility type for the legacy MongoEngine scaffold only.

The XRay domain uses SQLAlchemy and does not import this module.  Keeping the
alias avoids restoring any legacy database connection or business semantics.
"""

from bson import ObjectId as OID

__all__ = ["OID"]
