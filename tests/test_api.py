"""Integration tests for FastAPI REST endpoints."""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_service import AIServiceError

client = TestClient(app)


class TestRestAPI:
    """REST API endpoint tests."""

    def test_health_endpoint(self):
        """Test GET /api/ai/health returns status UP."""
        response = client.get("/api/ai/health")
        assert response.status_code == 200
        assert response.json() == {"status": "UP"}

    @patch("app.main.ai_service.analyze_incident")
    def test_analyze_endpoint_success(self, mock_analyze):
        """Test POST /api/ai/analyze with valid incident payload."""
        from app.models.incident_analyzed import IncidentAnalyzedEvent

        mock_analyze.return_value = IncidentAnalyzedEvent(
            incidentId=101,
            category="ROAD_ACCIDENT",
            severity="CRITICAL",
            summary="Multi-vehicle accident with casualties and fire risk.",
            requiredTeams=["MEDICAL", "FIRE", "POLICE"],
            confidence=0.94,
        )

        payload = {
            "incidentId": 101,
            "title": "Major road accident",
            "description": "Three cars crashed. One person appears unconscious and smoke is coming from one vehicle.",
            "latitude": 16.3065,
            "longitude": 80.4375,
        }

        response = client.post("/api/ai/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["incidentId"] == 101
        assert data["category"] == "ROAD_ACCIDENT"
        assert data["severity"] == "CRITICAL"
        assert data["confidence"] == 0.94
        assert "MEDICAL" in data["requiredTeams"]

    def test_analyze_endpoint_invalid_payload(self):
        """Test POST /api/ai/analyze with missing required fields."""
        invalid_payload = {
            "incidentId": None,
            "title": "",
            "description": "",
        }
        response = client.post("/api/ai/analyze", json=invalid_payload)
        assert response.status_code == 422

    @patch("app.main.ai_service.analyze_incident")
    def test_analyze_endpoint_ai_failure(self, mock_analyze):
        """Test POST /api/ai/analyze when AI Service encounters error."""
        mock_analyze.side_effect = AIServiceError("Gemini API connection timeout")

        payload = {
            "incidentId": 102,
            "title": "Building fire",
            "description": "Heavy smoke coming from 3rd floor.",
        }

        response = client.post("/api/ai/analyze", json=payload)
        assert response.status_code == 502
        assert "AI service failure" in response.json()["detail"]
