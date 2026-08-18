class XRayServiceError(Exception):
    """Base error with a stable API mapping owned by the endpoint layer."""


class InputContractError(XRayServiceError):
    pass


class QualificationAccessError(XRayServiceError):
    """Qualification is an operator-controlled offline operation."""


class LeakageInputError(InputContractError):
    def __init__(self, paths: list[str]):
        self.paths = paths
        super().__init__("leakage_invalid")


class IdempotencyConflictError(XRayServiceError):
    pass


class RunNotFoundError(XRayServiceError):
    pass


class SessionNotFoundError(XRayServiceError):
    pass


class StudyNotFoundError(XRayServiceError):
    pass


class CASConflictError(XRayServiceError):
    pass
