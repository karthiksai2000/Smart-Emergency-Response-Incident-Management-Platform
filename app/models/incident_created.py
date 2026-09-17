"""Input event model for incident creation."""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class IncidentCreatedEvent(BaseModel):
    """Event received from Kafka topic 'incident.created'."""

    incidentId: int = Field(
        ...,
        description="Unique identifier for the incident",
        examples=[101]
    )
    title: str = Field(
        ...,
        min_length=1,
        description="Short title summarizing the incident",
        examples=["Major road accident"]
    )
    description: str = Field(
        ...,
        min_length=1,
        description="Detailed description of the emergency incident",
        examples=["Three cars crashed. One person appears unconscious and smoke is coming from one vehicle."]
    )
    latitude: Optional[float] = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="Latitude coordinate of the incident location",
        examples=[16.3065]
    )
    longitude: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Longitude coordinate of the incident location",
        examples=[80.4375]
    )

    @field_validator("title", "description")
    @classmethod
    def validate_non_empty_string(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Field cannot be empty or whitespace only")
        return trimmed

    model_config = {
        "json_schema_extra": {
            "example": {
                "incidentId": 101,
                "title": "Major road accident",
                "description": "Three cars crashed. One person appears unconscious and smoke is coming from one vehicle.",
                "latitude": 16.3065,
                "longitude": 80.4375
            }
        }
    }
