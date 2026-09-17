"""Kafka package for AI Service."""

from app.kafka.producer import IncidentKafkaProducer
from app.kafka.consumer import IncidentKafkaConsumer

__all__ = ["IncidentKafkaProducer", "IncidentKafkaConsumer"]
