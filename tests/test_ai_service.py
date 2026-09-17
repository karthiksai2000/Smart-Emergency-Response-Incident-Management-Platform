"""Unit tests for AIService and Gemini integration."""

import json
import pytest

from app.models.incident_created import IncidentCreatedEvent
from app.models.incident_analyzed import (
    IncidentCategory,
    IncidentSeverity,
    ResponseTeam,
)
from app.services.ai_service import AIService, AIServiceError


class TestAIServiceScenarios:
    """Tests covering the standard scenario requirements."""

    def test_scenario_1_road_accident(self, test_settings):
        """Test 1 — Major road accident scenario."""
        mock_client = type("MockClient", (), {})()
        mock_client.analyze_text = lambda prompt: json.dumps({
            "category": "ROAD_ACCIDENT",
            "severity": "CRITICAL",
            "summary": "Multi-vehicle collision with an unconscious victim and active vehicle smoke.",
            "requiredTeams": ["MEDICAL", "FIRE", "POLICE"],
            "confidence": 0.95,
        })

        service = AIService(settings=test_settings, gemini_client=mock_client)
        incident = IncidentCreatedEvent(
            incidentId=101,
            title="Major road accident",
            description="Three cars crashed. One person appears unconscious and smoke is coming from one vehicle.",
            latitude=16.3065,
            longitude=80.4375,
        )

        result = service.analyze_incident(incident)

        assert result.incidentId == 101
        assert result.category == IncidentCategory.ROAD_ACCIDENT
        assert result.severity == IncidentSeverity.CRITICAL
        assert ResponseTeam.MEDICAL in result.requiredTeams
        assert ResponseTeam.FIRE in result.requiredTeams
        assert ResponseTeam.POLICE in result.requiredTeams
        assert 0.0 <= result.confidence <= 1.0

    def test_scenario_2_building_fire(self, test_settings):
        """Test 2 — Building fire scenario."""
        mock_client = type("MockClient", (), {})()
        mock_client.analyze_text = lambda prompt: json.dumps({
            "category": "FIRE",
            "severity": "CRITICAL",
            "summary": "Large building fire on three floors with occupants trapped.",
            "requiredTeams": ["FIRE", "RESCUE", "MEDICAL"],
            "confidence": 0.98,
        })

        service = AIService(settings=test_settings, gemini_client=mock_client)
        incident = IncidentCreatedEvent(
            incidentId=102,
            title="Building fire",
            description="A large fire has started inside a three-storey building. People are trapped on the second floor.",
        )

        result = service.analyze_incident(incident)

        assert result.incidentId == 102
        assert result.category == IncidentCategory.FIRE
        assert result.severity in [IncidentSeverity.HIGH, IncidentSeverity.CRITICAL]
        assert ResponseTeam.FIRE in result.requiredTeams
        assert ResponseTeam.RESCUE in result.requiredTeams

    def test_scenario_3_medical_emergency(self, test_settings):
        """Test 3 — Medical emergency scenario."""
        mock_client = type("MockClient", (), {})()
        mock_client.analyze_text = lambda prompt: json.dumps({
            "category": "MEDICAL_EMERGENCY",
            "severity": "HIGH",
            "summary": "Elderly individual collapsed and unresponsive.",
            "requiredTeams": ["MEDICAL"],
            "confidence": 0.92,
        })

        service = AIService(settings=test_settings, gemini_client=mock_client)
        incident = IncidentCreatedEvent(
            incidentId=103,
            title="Medical emergency",
            description="An elderly person has collapsed and is unconscious.",
        )

        result = service.analyze_incident(incident)

        assert result.incidentId == 103
        assert result.category == IncidentCategory.MEDICAL_EMERGENCY
        assert ResponseTeam.MEDICAL in result.requiredTeams

    def test_scenario_4_low_severity(self, test_settings):
        """Test 4 — Low severity minor collision."""
        mock_client = type("MockClient", (), {})()
        mock_client.analyze_text = lambda prompt: json.dumps({
            "category": "ROAD_ACCIDENT",
            "severity": "LOW",
            "summary": "Minor fender-bender with no injuries reported.",
            "requiredTeams": ["POLICE"],
            "confidence": 0.89,
        })

        service = AIService(settings=test_settings, gemini_client=mock_client)
        incident = IncidentCreatedEvent(
            incidentId=104,
            title="Minor accident",
            description="A minor collision occurred. No injuries were reported.",
        )

        result = service.analyze_incident(incident)

        assert result.incidentId == 104
        assert result.severity == IncidentSeverity.LOW

    def test_markdown_wrapped_response_handling(self, test_settings):
        """Verify markdown code fence stripping from Gemini response."""
        mock_client = type("MockClient", (), {})()
        mock_client.analyze_text = lambda prompt: """```json
{
  "category": "ELECTRICAL_HAZARD",
  "severity": "HIGH",
  "summary": "Downed high voltage wire creating sparking hazard on road.",
  "requiredTeams": ["FIRE", "POLICE"],
  "confidence": 0.91
}
```"""

        service = AIService(settings=test_settings, gemini_client=mock_client)
        incident = IncidentCreatedEvent(
            incidentId=105,
            title="Fallen power line",
            description="High voltage cable fell across street and is sparking.",
        )

        result = service.analyze_incident(incident)
        assert result.category == IncidentCategory.ELECTRICAL_HAZARD
        assert result.severity == IncidentSeverity.HIGH

    def test_gemini_api_failure_raises_ai_service_error(self, test_settings):
        """Verify exception handling when Gemini API raises an error."""
        mock_client = type("MockClient", (), {})()
        def fail_call(prompt):
            raise Exception("API rate limit exceeded")
        mock_client.analyze_text = fail_call

        service = AIService(settings=test_settings, gemini_client=mock_client)
        incident = IncidentCreatedEvent(
            incidentId=106,
            title="Test failure",
            description="Test description",
        )

        with pytest.raises(AIServiceError) as exc_info:
            service.analyze_incident(incident)
        assert "API rate limit exceeded" in str(exc_info.value) or "AI" in str(exc_info.value)

    def test_invalid_gemini_output_schema_raises_ai_service_error(self, test_settings):
        """Verify invalid output from Gemini is rejected by Pydantic."""
        mock_client = type("MockClient", (), {})()
        mock_client.analyze_text = lambda prompt: json.dumps({
            "category": "INVALID_UNKNOWN_CATEGORY",
            "severity": "CRITICAL",
            "summary": "Invalid category test.",
            "requiredTeams": ["POLICE"],
            "confidence": 0.85,
        })

        service = AIService(settings=test_settings, gemini_client=mock_client)
        incident = IncidentCreatedEvent(
            incidentId=107,
            title="Test Bad Output",
            description="Test description",
        )

        with pytest.raises(AIServiceError) as exc_info:
            service.analyze_incident(incident)
        assert "AI output failed schema validation" in str(exc_info.value)
