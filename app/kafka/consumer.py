"""Kafka consumer for subscribing to incident.created events."""

import asyncio
import json
import logging
import threading
from typing import Optional

from confluent_kafka import Consumer, KafkaError, KafkaException
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.kafka.producer import IncidentKafkaProducer
from app.models.incident_created import IncidentCreatedEvent
from app.services.ai_service import AIService, AIServiceError

logger = logging.getLogger("kafka_consumer")


class IncidentKafkaConsumer:
    """Consumes IncidentCreatedEvent messages from Kafka and triggers AI analysis."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        ai_service: Optional[AIService] = None,
        producer: Optional[IncidentKafkaProducer] = None,
    ):
        self.settings = settings or get_settings()
        self.ai_service = ai_service or AIService(settings=self.settings)
        self.producer = producer or IncidentKafkaProducer(settings=self.settings)

        self._consumer: Optional[Consumer] = None
        self._is_running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        """Initialize consumer and start background listening thread."""
        if not self.settings.KAFKA_ENABLED:
            logger.info("Kafka consumer is disabled via KAFKA_ENABLED=false.")
            return False

        if not self.producer._is_connected:
            self.producer.start()

        conf = {
            "bootstrap.servers": self.settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": self.settings.KAFKA_CONSUMER_GROUP,
            "auto.offset.reset": self.settings.KAFKA_AUTO_OFFSET_RESET,
            "enable.auto.commit": True,
            "session.timeout.ms": 30000,
            "max.poll.interval.ms": 300000,
        }

        try:
            self._consumer = Consumer(conf)
            self._consumer.subscribe([self.settings.KAFKA_INPUT_TOPIC])
            self._is_running = True

            # Start worker thread
            self._thread = threading.Thread(target=self._consume_loop, daemon=True, name="KafkaConsumerWorker")
            self._thread.start()

            logger.info(
                "Kafka consumer started. Subscribed to topic '%s' with group '%s'",
                self.settings.KAFKA_INPUT_TOPIC,
                self.settings.KAFKA_CONSUMER_GROUP,
            )
            return True
        except KafkaException as exc:
            logger.error("Failed to initialize Kafka consumer: %s", exc)
            self._is_running = False
            return False
        except Exception as exc:
            logger.error("Unexpected error initializing Kafka consumer: %s", exc)
            self._is_running = False
            return False

    def process_message_payload(self, raw_value: str) -> bool:
        """Process a single JSON message payload from Kafka.

        Args:
            raw_value: Raw string from Kafka message.

        Returns:
            bool: True if processing succeeded and result published, False otherwise.
        """
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse Kafka message as JSON: %s | Payload: %s", exc, raw_value)
            return False

        try:
            incident = IncidentCreatedEvent.model_validate(payload)
        except ValidationError as exc:
            logger.error("Validation error for incident.created message: %s | Payload: %s", exc, payload)
            return False

        logger.info("Received incident.created: incidentId=%s", incident.incidentId)

        try:
            analyzed_event = self.ai_service.analyze_incident(incident)
        except AIServiceError as exc:
            logger.error("ERROR AI analysis failed: incidentId=%s | Reason: %s", incident.incidentId, exc)
            return False
        except Exception as exc:
            logger.error("ERROR Unexpected error during AI analysis: incidentId=%s | Reason: %s", incident.incidentId, exc)
            return False

        try:
            published = self.producer.publish_incident_analyzed(analyzed_event)
            return published
        except Exception as exc:
            logger.error("Failed to publish analyzed event for incidentId=%s: %s", incident.incidentId, exc)
            return False

    def _consume_loop(self):
        """Continuous polling loop running in background thread."""
        logger.info("Kafka consumer poll loop active.")
        while self._is_running and self._consumer:
            try:
                msg = self._consumer.poll(timeout=self.settings.KAFKA_POLL_TIMEOUT_SECONDS)
                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        # Reached end of partition, normal state
                        continue
                    else:
                        logger.error("Kafka consumer error: %s", msg.error())
                        continue

                raw_value = msg.value().decode("utf-8")
                self.process_message_payload(raw_value)

            except Exception as exc:
                if self._is_running:
                    logger.error("Error in Kafka consumer loop: %s", exc, exc_info=True)

        logger.info("Kafka consumer poll loop terminated.")

    def stop(self):
        """Stop background consumption and close consumer cleanly."""
        logger.info("Stopping Kafka consumer...")
        self._is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        if self._consumer:
            try:
                self._consumer.close()
            except Exception as exc:
                logger.error("Error closing Kafka consumer: %s", exc)
            self._consumer = None
        logger.info("Kafka consumer stopped.")
