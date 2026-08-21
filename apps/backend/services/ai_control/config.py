"""AI Control transitional configuration boundary.

The control plane currently uses the repository's shared authentication and
database settings.  Its own source-of-truth configuration storage will replace
this adapter when the release/event contract is implemented.
"""

from apps.backend.core.config import Settings, settings

__all__ = ["Settings", "settings"]
