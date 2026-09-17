"""Unit tests for Pydantic models and enums."""

import pytest
from pydantic import ValidationError

from app.models.incident_created import IncidentCreatedEvent
from app.models.incident_analyzed import (
    IncidentCategory,
    IncidentSeverity,
    ResponseTeam,
    IncidentAnalysisResult,
    IncidentAnalyzedEvent,
)


class TestIncidentCreatedModel:
    """Tests for IncidentCreatedEvent."""

    def test_valid_incident_created(self):
        event = IncidentCreatedEvent(
            incidentId=101,
            title="Major road accident",
            description="Three cars crashed. One person appears unconscious.",
            latitude=16.3065,
            longitude=80.4375,
        )
        assert event.incidentId == 101
        assert event.title == "Major road accident"
        assert event.latitude == 16.3065
        assert event.longitude == 80.4375

    def test_valid_without_coordinates(self):
        event = IncidentCreatedEvent(
            incidentId=102,
            title="Fire alert",
            description="Smoke visible from roof.",
        )
        assert event.incidentId == 102
        assert event.latitude is None
        assert event.longitude is None

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError):
            IncidentCreatedEvent(
                incidentId=103,
                title="   ",
                description="Valid description",
            )

    def test_empty_description_rejected(self):
        with pytest.raises(ValidationError):
            IncidentCreatedEvent(
                incidentId=104,
                title="Valid Title",
                description="",
            )

    def test_invalid_coordinates_rejected(self):
        with pytest.raises(ValidationError):
            IncidentCreatedEvent(
                incidentId=105,
                title="Invalid Lat",
                description="Some description",
                latitude=95.0,  # Max 90
            )

        with pytest.raises(ValidationError):
            IncidentCreatedEvent(
                incidentId=106,
                title="Invalid Lon",
                description="Some description",
                longitude=-185.0,  # Min -180
            )


class TestIncidentAnalyzedModel:
    """Tests for IncidentAnalyzedEvent and enum validations."""

    def test_valid_incident_analyzed(self):
        event = IncidentAnalyzedEvent(
            incidentId=101,
            category=IncidentCategory.ROAD_ACCIDENT,
            severity=IncidentSeverity.CRITICAL,
            summary="Multi-vehicle accident with possible casualties and fire risk.",
            requiredTeams=[ResponseTeam.MEDICAL, ResponseTeam.FIRE, ResponseTeam.POLICE],
            confidence=0.94,
        )
        assert event.incidentId == 101
        assert event.category == IncidentCategory.ROAD_ACCIDENT
        assert event.severity == IncidentSeverity.CRITICAL
        assert len(event.requiredTeams) == 3
        assert event.confidence == 0.94

    def test_all_categories_allowed(self):
        expected_categories = [
            "FIRE",
            "ROAD_ACCIDENT",
            "MEDICAL_EMERGENCY",
            "CRIME",
            "FLOOD",
            "EARTHQUAKE",
            "BUILDING_COLLAPSE",
            "INDUSTRIAL_ACCIDENT",
            "ELECTRICAL_HAZARD",
            "RESCUE",
            "OTHER",
        ]
        for cat in expected_categories:
            assert IncidentCategory(cat) is not None

    def test_invalid_category_rejected(self):
        with pytest.raises(ValidationError):
            IncidentAnalyzedEvent.model_validate({
                "incidentId": 101,
                "category": "CAR_CRASHING_THING",  # Invalid category
                "severity": "CRITICAL",
                "summary": "Some summary",
                "requiredTeams": ["POLICE"],
                "confidence": 0.90,
            })

    def test_invalid_severity_rejected(self):
        with pytest.raises(ValidationError):
            IncidentAnalyzedEvent.model_validate({
                "incidentId": 101,
                "category": "ROAD_ACCIDENT",
                "severity": "EXTREME",  # Invalid severity
                "summary": "Some summary",
                "requiredTeams": ["POLICE"],
                "confidence": 0.90,
            })

    def test_invalid_team_rejected(self):
        with pytest.raises(ValidationError):
            IncidentAnalyzedEvent.model_validate({
                "incidentId": 101,
                "category": "ROAD_ACCIDENT",
                "severity": "HIGH",
                "summary": "Some summary",
                "requiredTeams": ["MILITARY_FORCE"],  # Invalid team
                "confidence": 0.90,
            })

    def test_duplicate_teams_deduped(self):
        event = IncidentAnalyzedEvent.model_validate({
            "incidentId": 101,
            "category": "FIRE",
            "severity": "HIGH",
            "summary": "Building fire with smoke.",
            "requiredTeams": ["FIRE", "MEDICAL", "FIRE"],
            "confidence": 0.88,
        })
        assert event.requiredTeams == [ResponseTeam.FIRE, ResponseTeam.MEDICAL]

    def test_confidence_range_validation(self):
        # Valid bounds
        for conf in [0.0, 0.5, 1.0]:
            event = IncidentAnalyzedEvent(
                incidentId=101,
                category=IncidentCategory.OTHER,
                severity=IncidentSeverity.LOW,
                summary="Summary",
                requiredTeams=[ResponseTeam.POLICE],
                confidence=conf,
            )
            assert event.confidence == conf

        # Greater than 1.0 (e.g. 94 instead of 0.94)
        with pytest.raises(ValidationError):
            IncidentAnalyzedEvent(
                incidentId=101,
                category=IncidentCategory.OTHER,
                severity=IncidentSeverity.LOW,
                summary="Summary",
                requiredTeams=[ResponseTeam.POLICE],
                confidence=94,
            )

        # Less than 0.0
        with pytest.raises(ValidationError):
            IncidentAnalyzedEvent(
                incidentId=101,
                category=IncidentCategory.OTHER,
                severity=IncidentSeverity.LOW,
                summary="Summary",
                requiredTeams=[ResponseTeam.POLICE],
                confidence=-0.1,
            )
