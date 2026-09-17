"""Integration tests for Kafka producer and consumer message pipelines."""

import json
from unittest.mock import MagicMock
import pytest

from app.kafka.consumer import IncidentKafkaConsumer
from app.kafka.producer import IncidentKafkaProducer
from app.models.incident_analyzed import IncidentAnalyzedEvent
from app.models.incident_created import IncidentCreatedEvent
from app.services.ai_service import AIService, AIServiceError


class TestKafkaPipeline:
    """Tests for Kafka message parsing, processing, and producer output."""

    def test_consumer_successful_processing_pipeline(self, test_settings):
        """Test full consume -> AI analysis -> produce pipeline."""
        mock_ai_service = MagicMock(spec=AIService)
        mock_ai_service.analyze_incident.return_value = IncidentAnalyzedEvent(
            incidentId=101,
            category="ROAD_ACCIDENT",
            severity="CRITICAL",
            summary="Multi-vehicle accident with casualties.",
            requiredTeams=["MEDICAL", "FIRE", "POLICE"],
            confidence=0.95,
        )

        mock_producer = MagicMock(spec=IncidentKafkaProducer)
        mock_producer.publish_incident_analyzed.return_value = True

        consumer = IncidentKafkaConsumer(
            settings=test_settings,
            ai_service=mock_ai_service,
            producer=mock_producer,
        )

        sample_message = json.dumps({
            "incidentId": 101,
            "title": "Major road accident",
            "description": "Three cars crashed. One person appears unconscious.",
            "latitude": 16.3065,
            "longitude": 80.4375,
        })

        success = consumer.process_message_payload(sample_message)
        assert success is True
        mock_ai_service.analyze_incident.assert_called_once()
        mock_producer.publish_incident_analyzed.assert_called_once()

    def test_consumer_handles_invalid_json(self, test_settings):
        """Verify non-JSON message does not crash consumer."""
        mock_ai_service = MagicMock(spec=AIService)
        mock_producer = MagicMock(spec=IncidentKafkaProducer)

        consumer = IncidentKafkaConsumer(
            settings=test_settings,
            ai_service=mock_ai_service,
            producer=mock_producer,
        )

        success = consumer.process_message_payload("NOT_VALID_JSON_STRING {{{")
        assert success is False
        mock_ai_service.analyze_incident.assert_not_called()
        mock_producer.publish_incident_analyzed.assert_not_called()

    def test_consumer_handles_invalid_event_schema(self, test_settings):
        """Verify payload missing required fields is rejected without crashing."""
        mock_ai_service = MagicMock(spec=AIService)
        mock_producer = MagicMock(spec=IncidentKafkaProducer)

        consumer = IncidentKafkaConsumer(
            settings=test_settings,
            ai_service=mock_ai_service,
            producer=mock_producer,
        )

        invalid_event = json.dumps({
            "incidentId": 102,
            # Missing title and description
        })

        success = consumer.process_message_payload(invalid_event)
        assert success is False
        mock_ai_service.analyze_incident.assert_not_called()

    def test_consumer_handles_ai_service_error_gracefully(self, test_settings):
        """Verify AI failure does not crash consumer."""
        mock_ai_service = MagicMock(spec=AIService)
        mock_ai_service.analyze_incident.side_effect = AIServiceError("Gemini unavailable")

        mock_producer = MagicMock(spec=IncidentKafkaProducer)

        consumer = IncidentKafkaConsumer(
            settings=test_settings,
            ai_service=mock_ai_service,
            producer=mock_producer,
        )

        sample_message = json.dumps({
            "incidentId": 103,
            "title": "Flood alert",
            "description": "Rising water levels near bridge.",
        })

        success = consumer.process_message_payload(sample_message)
        assert success is False
        mock_ai_service.analyze_incident.assert_called_once()
        mock_producer.publish_incident_analyzed.assert_not_called()

    def test_duplicate_events_resilience(self, test_settings):
        """Verify processing the same incidentId repeatedly executes cleanly."""
        mock_ai_service = MagicMock(spec=AIService)
        mock_ai_service.analyze_incident.return_value = IncidentAnalyzedEvent(
            incidentId=104,
            category="OTHER",
            severity="LOW",
            summary="Minor incident.",
            requiredTeams=["POLICE"],
            confidence=0.85,
        )

        mock_producer = MagicMock(spec=IncidentKafkaProducer)
        mock_producer.publish_incident_analyzed.return_value = True

        consumer = IncidentKafkaConsumer(
            settings=test_settings,
            ai_service=mock_ai_service,
            producer=mock_producer,
        )

        sample_message = json.dumps({
            "incidentId": 104,
            "title": "Lost pet in tree",
            "description": "Cat stuck in tall tree.",
        })

        # Process first time
        assert consumer.process_message_payload(sample_message) is True
        # Process duplicate event
        assert consumer.process_message_payload(sample_message) is True
        assert mock_ai_service.analyze_incident.call_count == 2
