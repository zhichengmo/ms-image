from typing import Any


MESSAGE_FIELDS = frozenset(
    {
        "run_id",
        "task_id",
        "stage_key",
        "release_fingerprint",
        "expected_version",
        "trace_namespace",
    }
)


class InvalidWorkerMessage(ValueError):
    pass


def validate_message(message: dict[str, Any]) -> dict[str, Any]:
    """Validate and copy the only payload allowed across the broker boundary."""
    if not isinstance(message, dict):
        raise InvalidWorkerMessage("message_must_be_object")
    unknown = set(message) - MESSAGE_FIELDS
    missing = MESSAGE_FIELDS - set(message)
    if unknown:
        raise InvalidWorkerMessage("message_field_not_allowed")
    if missing:
        raise InvalidWorkerMessage("message_field_missing")
    for key in MESSAGE_FIELDS:
        value = message[key]
        if key == "expected_version":
            if type(value) is not int or value < 0:
                raise InvalidWorkerMessage("expected_version_invalid")
        elif not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise InvalidWorkerMessage(f"{key}_invalid")
    return {key: message[key] for key in MESSAGE_FIELDS}
