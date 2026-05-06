"""Base Pydantic models with modern serialization patterns.

Provides CustomModel with automatic datetime serialization using
Pydantic v2 @field_serializer pattern (replaces deprecated json_encoders).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, field_serializer


class CustomModel(BaseModel):
    """Base model with automatic datetime serialization.

    All datetime fields are serialized to ISO format with timezone.
    Naive datetimes are assumed UTC before serialization.

    Usage:
        class UserResponse(CustomModel):
            id: str
            created_at: datetime

        user = UserResponse(id="123", created_at=datetime.utcnow())
        print(user.model_dump_json())  # {"id": "123", "created_at": "2024-01-15T10:30:00+0000"}
    """

    model_config = ConfigDict(populate_by_name=True)

    @field_serializer("*", when_used="json", check_fields=False)
    def _serialize_datetimes(self, value: datetime) -> str:
        """Serialize datetime fields to ISO format with timezone.

        Args:
            value: The field value being serialized.

        Returns:
            ISO formatted datetime string with timezone, or original value.
        """
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=ZoneInfo("UTC"))
            return value.strftime("%Y-%m-%dT%H:%M:%S%z")
        return value


__all__ = ["CustomModel"]
