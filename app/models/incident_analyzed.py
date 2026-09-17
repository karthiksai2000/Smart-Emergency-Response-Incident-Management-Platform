"""Output event models and enums for incident analysis."""

from enum import Enum
from typing import List
from pydantic import BaseModel, Field, field_validator


class IncidentCategory(str, Enum):
    """Allowed incident classification categories."""
    FIRE = "FIRE"
    ROAD_ACCIDENT = "ROAD_ACCIDENT"
    MEDICAL_EMERGENCY = "MEDICAL_EMERGENCY"
    CRIME = "CRIME"
    FLOOD = "FLOOD"
    EARTHQUAKE = "EARTHQUAKE"
    BUILDING_COLLAPSE = "BUILDING_COLLAPSE"
    INDUSTRIAL_ACCIDENT = "INDUSTRIAL_ACCIDENT"
    ELECTRICAL_HAZARD = "ELECTRICAL_HAZARD"
    RESCUE = "RESCUE"
    OTHER = "OTHER"


class IncidentSeverity(str, Enum):
    """Allowed severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ResponseTeam(str, Enum):
    """Allowed response teams."""
    MEDICAL = "MEDICAL"
    FIRE = "FIRE"
    POLICE = "POLICE"
    RESCUE = "RESCUE"
    DISASTER_RESPONSE = "DISASTER_RESPONSE"
    HAZMAT = "HAZMAT"


class IncidentAnalysisResult(BaseModel):
    """Structured intelligence produced by AI analysis."""

    category: IncidentCategory = Field(
        ...,
        description="Normalized category classification of the incident"
    )
    severity: IncidentSeverity = Field(
        ...,
        description="Assessed severity level of the incident"
    )
    summary: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Concise, 1-2 sentence factual summary without reasoning or markdown"
    )
    requiredTeams: List[ResponseTeam] = Field(
        ...,
        min_length=1,
        description="List of recommended response teams needed at the incident"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score of the classification (between 0.0 and 1.0)"
    )

    @field_validator("summary")
    @classmethod
    def clean_summary(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Summary cannot be empty")
        return trimmed

    @field_validator("requiredTeams")
    @classmethod
    def unique_teams(cls, value: List[ResponseTeam]) -> List[ResponseTeam]:
        # Preserve order while eliminating duplicates
        seen = set()
        deduped = []
        for team in value:
            if team not in seen:
                seen.add(team)
                deduped.append(team)
        return deduped


class IncidentAnalyzedEvent(IncidentAnalysisResult):
    """Event published to Kafka topic 'incident.analyzed'."""

    incidentId: int = Field(
        ...,
        description="Original identifier of the incident",
        examples=[101]
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "incidentId": 101,
                "category": "ROAD_ACCIDENT",
                "severity": "CRITICAL",
                "summary": "Multi-vehicle accident with possible casualties and fire risk.",
                "requiredTeams": [
                    "MEDICAL",
                    "FIRE",
                    "POLICE"
                ],
                "confidence": 0.94
            }
        }
    }
