"""Pytest fixtures and configuration."""

import json
from typing import Dict, Any, Optional
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.models.incident_created import IncidentCreatedEvent
from app.models.incident_analyzed import (
    IncidentAnalysisResult,
    IncidentAnalyzedEvent,
    IncidentCategory,
    IncidentSeverity,
    ResponseTeam,
)
from app.services.ai_service import AIService


class MockGeminiClient:
    """Mock Gemini client returning configured JSON responses."""

    def __init__(self, response_data: Optional[Dict[str, Any]] = None):
        self.response_data = response_data or {
            "category": "ROAD_ACCIDENT",
            "severity": "CRITICAL",
            "summary": "Multi-vehicle accident with possible casualties and fire risk.",
            "requiredTeams": ["MEDICAL", "FIRE", "POLICE"],
            "confidence": 0.94,
        }
        self.last_prompt = None

    def analyze_text(self, prompt: str) -> str:
        self.last_prompt = prompt
        return json.dumps(self.response_data)


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        GEMINI_API_KEY="test-mock-api-key",
        GEMINI_MODEL="gemini-2.5-flash",
        KAFKA_BOOTSTRAP_SERVERS="localhost:9092",
        KAFKA_INPUT_TOPIC="incident.created",
        KAFKA_OUTPUT_TOPIC="incident.analyzed",
        KAFKA_CONSUMER_GROUP="ai-service-test",
        KAFKA_ENABLED=False,
    )


@pytest.fixture
def mock_gemini_client() -> MockGeminiClient:
    return MockGeminiClient()


@pytest.fixture
def mock_ai_service(test_settings: Settings, mock_gemini_client: MockGeminiClient) -> AIService:
    return AIService(settings=test_settings, gemini_client=mock_gemini_client)


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)
