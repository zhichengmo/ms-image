from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


SESSION_STATUSES = frozenset({"open", "processing", "completed", "closed", "cancelled"})


def _required_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("value_must_not_be_blank")
    return normalized


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime_timezone_required")
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_system: str = Field(min_length=1, max_length=64)
    source_session_id: str = Field(min_length=1, max_length=128)
    source_medical_record_id: str | None = Field(default=None, max_length=128)
    subject_id: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    started_at: datetime

    @field_validator("source_system", "source_session_id", "subject_id", "request_id")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("source_medical_record_id")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("started_at")
    @classmethod
    def normalize_started_at(cls, value: datetime) -> datetime:
        return _utc_datetime(value)


class SessionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_state_version: int = Field(ge=0)
    status: str = Field(min_length=1, max_length=32)
    completed_at: datetime | None = None
    closed_at: datetime | None = None
    cancelled_by_id: str | None = Field(default=None, max_length=128)
    cancel_reason: str | None = Field(default=None, max_length=200)
    cancelled_at: datetime | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = _required_text(value)
        if normalized not in SESSION_STATUSES:
            raise ValueError("session_status_invalid")
        return normalized

    @field_validator("completed_at", "closed_at", "cancelled_at")
    @classmethod
    def normalize_event_time(cls, value: datetime | None) -> datetime | None:
        return _utc_datetime(value) if value is not None else None

    @field_validator("cancelled_by_id", "cancel_reason")
    @classmethod
    def normalize_optional_update_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class SessionQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return _required_text(value)


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_system: str
    source_session_id: str
    source_medical_record_id: str | None = None
    subject_id: str
    requester_id: str
    request_id: str
    status: str
    state_version: int
    started_at: datetime
    completed_at: datetime | None = None
    closed_at: datetime | None = None
    cancelled_by_id: str | None = None
    cancel_reason: str | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


__all__ = [
    "SESSION_STATUSES",
    "SessionCreate",
    "SessionQuery",
    "SessionResponse",
    "SessionUpdate",
]
