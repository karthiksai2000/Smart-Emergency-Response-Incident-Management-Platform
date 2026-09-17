"""FastAPI Application for AI Service in Emergency Response Platform."""

from contextlib import asynccontextmanager
import logging
import sys
from typing import Dict

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.kafka.consumer import IncidentKafkaConsumer
from app.kafka.producer import IncidentKafkaProducer
from app.models.incident_analyzed import IncidentAnalyzedEvent
from app.models.incident_created import IncidentCreatedEvent
from app.services.ai_service import AIService, AIServiceError

# Setup structured logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ai_service_app")

# Shared service instances
ai_service = AIService(settings=settings)
kafka_producer = IncidentKafkaProducer(settings=settings)
kafka_consumer = IncidentKafkaConsumer(
    settings=settings,
    ai_service=ai_service,
    producer=kafka_producer,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager to initialize and teardown background services."""
    logger.info("Starting AI Service (Environment: %s)...", settings.APP_ENV)

    # Initialize Kafka if enabled
    if settings.KAFKA_ENABLED:
        try:
            kafka_producer.start()
            kafka_consumer.start()
        except Exception as exc:
            logger.warning("Kafka initialization failed on startup: %s. Continuing in standalone mode.", exc)
    else:
        logger.info("Kafka integration is disabled (KAFKA_ENABLED=false).")

    yield

    logger.info("Shutting down AI Service...")
    if settings.KAFKA_ENABLED:
        try:
            kafka_consumer.stop()
            kafka_producer.close()
        except Exception as exc:
            logger.error("Error during Kafka teardown: %s", exc)
    logger.info("AI Service shutdown complete.")


app = FastAPI(
    title="Smart Emergency Response — AI Service",
    description=(
        "Consumes emergency incidents, applies Google Gemini AI for structured "
        "classification, severity rating, factual summary generation, and response team recommendations, "
        "and publishes intelligence events via Kafka."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for cross-service development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/api/ai/health",
    summary="Service Health Check",
    response_model=Dict[str, str],
    tags=["Health"],
)
def health_check() -> Dict[str, str]:
    """Return health status of the AI Service."""
    return {"status": "UP"}


@app.post(
    "/api/ai/analyze",
    summary="Analyze Emergency Incident",
    response_model=IncidentAnalyzedEvent,
    status_code=status.HTTP_200_OK,
    tags=["Analysis"],
)
def analyze_incident(incident: IncidentCreatedEvent) -> IncidentAnalyzedEvent:
    """Analyze an incident payload synchronously and return structured intelligence.

    Primarily used for testing and local development.
    Production events flow through Kafka `incident.created` -> `incident.analyzed`.
    """
    logger.info("Received REST analysis request: incidentId=%s", incident.incidentId)
    try:
        analyzed_event = ai_service.analyze_incident(incident)
        return analyzed_event
    except AIServiceError as exc:
        logger.error("AI analysis error for incidentId=%s: %s", incident.incidentId, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI service failure: {str(exc)}",
        )
    except Exception as exc:
        logger.error("Unexpected error analyzing incidentId=%s: %s", incident.incidentId, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during incident analysis",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
