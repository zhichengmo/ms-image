"""Stable service-domain errors for AI control-plane endpoints."""


class AIControlServiceError(ValueError):
    pass


class AIControlNotFoundError(AIControlServiceError):
    pass


class AIControlStateConflictError(AIControlServiceError):
    pass


class AIControlValidationError(AIControlServiceError):
    pass


class AIControlCommandConflictError(AIControlServiceError):
    pass


__all__ = [
    "AIControlCommandConflictError",
    "AIControlNotFoundError",
    "AIControlServiceError",
    "AIControlStateConflictError",
    "AIControlValidationError",
]
