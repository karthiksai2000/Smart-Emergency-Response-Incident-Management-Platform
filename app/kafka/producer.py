"""Kafka producer for publishing analyzed incident events."""

import json
import logging
from typing import Optional

from confluent_kafka import KafkaError, KafkaException, Producer

from app.config import Settings, get_settings
from app.models.incident_analyzed import IncidentAnalyzedEvent

logger = logging.getLogger("kafka_producer")


class IncidentKafkaProducer:
    """Publishes IncidentAnalyzedEvent messages to Kafka topic."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._producer: Optional[Producer] = None
        self._is_connected = False

    def start(self) -> bool:
        """Initialize the Kafka Producer client."""
        if not self.settings.KAFKA_ENABLED:
            logger.info("Kafka producer is disabled via KAFKA_ENABLED=false.")
            return False

        conf = {
            "bootstrap.servers": self.settings.KAFKA_BOOTSTRAP_SERVERS,
            "client.id": "ai-service-producer",
            "acks": "all",
            "retries": 3,
            "retry.backoff.ms": 250,
            "linger.ms": 5,
        }

        try:
            self._producer = Producer(conf)
            self._is_connected = True
            logger.info(
                "Kafka producer initialized for topic '%s' (bootstrap: %s)",
                self.settings.KAFKA_OUTPUT_TOPIC,
                self.settings.KAFKA_BOOTSTRAP_SERVERS,
            )
            return True
        except KafkaException as exc:
            logger.error("Failed to initialize Kafka producer: %s", exc)
            self._is_connected = False
            return False

    def _delivery_report(self, err: Optional[KafkaError], msg):
        """Callback invoked on delivery success or permanent failure."""
        if err is not None:
            logger.error("Kafka message delivery failed: %s", err)
        else:
            logger.info(
                "incident.analyzed published successfully: incidentId key=%s topic=%s partition=%s offset=%s",
                msg.key().decode("utf-8") if msg.key() else "none",
                msg.topic(),
                msg.partition(),
                msg.offset(),
            )

    def publish_incident_analyzed(self, event: IncidentAnalyzedEvent) -> bool:
        """Publish an IncidentAnalyzedEvent to Kafka.

        Args:
            event: The validated incident analyzed event.

        Returns:
            bool: True if queued for delivery, False otherwise.
        """
        if not self._producer or not self._is_connected:
            logger.warning("Kafka producer not active. Skipping event publication for incidentId=%s", event.incidentId)
            return False

        try:
            payload = event.model_dump_json()
            key = str(event.incidentId).encode("utf-8")
            topic = self.settings.KAFKA_OUTPUT_TOPIC

            logger.info("Publishing incident.analyzed: incidentId=%s", event.incidentId)

            self._producer.produce(
                topic=topic,
                key=key,
                value=payload.encode("utf-8"),
                on_delivery=self._delivery_report,
            )
            # Serve delivery callback queue
            self._producer.poll(0)
            return True
        except KafkaException as exc:
            logger.error("Error queueing Kafka message for incidentId=%s: %s", event.incidentId, exc)
            return False
        except Exception as exc:
            logger.error("Unexpected error publishing to Kafka for incidentId=%s: %s", event.incidentId, exc)
            return False

    def flush(self, timeout: float = 5.0) -> int:
        """Flush outstanding messages."""
        if self._producer:
            return self._producer.flush(timeout=timeout)
        return 0

    def close(self):
        """Cleanly close the Kafka producer."""
        if self._producer:
            logger.info("Flushing and closing Kafka producer...")
            self.flush(timeout=5.0)
            self._producer = None
            self._is_connected = False
