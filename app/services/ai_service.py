"""AI Service for emergency incident analysis using Google Gemini API."""

import json
import logging
import re
from typing import Optional, Protocol, Union

from app.config import Settings, get_settings
from app.models.incident_created import IncidentCreatedEvent
from app.models.incident_analyzed import (
    IncidentAnalysisResult,
    IncidentAnalyzedEvent,
    IncidentCategory,
    IncidentSeverity,
    ResponseTeam,
)

logger = logging.getLogger("ai_service")

SYSTEM_INSTRUCTION = """You are an emergency incident analysis system for a Smart Emergency Response Platform.
Analyze the provided emergency incident details and generate structured intelligence.

Allowed Categories:
- FIRE: Fires in buildings, structures, forests, vehicles with active fire.
- ROAD_ACCIDENT: Traffic collisions, car crashes, pile-ups, vehicle rollovers.
- MEDICAL_EMERGENCY: Sudden illness, cardiac arrest, collapse, poisoning, trauma.
- CRIME: Armed robbery, active violence, assault, shooting, theft.
- FLOOD: Water inundation, flash floods, dam breaks, river overflow.
- EARTHQUAKE: Seismic activity, ground shaking, structural collapse from tremors.
- BUILDING_COLLAPSE: Structural failures, building caving in.
- INDUSTRIAL_ACCIDENT: Factory explosions, machinery accidents, boiler bursts.
- ELECTRICAL_HAZARD: Fallen high-voltage wires, transformer explosions, power line fires.
- RESCUE: People trapped in elevators, heights, confined spaces, water bodies.
- OTHER: Incidents not covered by above categories.

Allowed Severity:
- LOW: Minor issues, no injuries, low risk of escalation.
- MEDIUM: Moderate damage or minor injuries, contained risk.
- HIGH: Serious injuries, major property risk, potential casualties.
- CRITICAL: Multiple casualties, life-threatening situation, active disaster, severe fire/collapse.

Allowed Response Teams:
- MEDICAL: Ambulances, paramedics, EMTs for injuries and trauma.
- FIRE: Firefighters and fire trucks for fires, smoke, vehicle extraction.
- POLICE: Law enforcement for traffic control, crime, security, crowd control.
- RESCUE: Search and rescue, confined space, cliff/water rescue.
- DISASTER_RESPONSE: Large-scale disaster response for earthquakes, major floods, severe structural collapse.
- HAZMAT: Hazardous materials, chemical leaks, toxic gas, radioactive materials.

Strict Output Rules:
1. Return ONLY a valid JSON object matching the requested schema.
2. Category must be EXACTLY one of the allowed categories.
3. Severity must be EXACTLY one of the allowed severities.
4. Required teams must be a list containing ONLY valid response teams from the allowed list.
5. Summary must be 1-2 factual sentences summarizing the incident. Do NOT include markdown formatting, advice, instructions to victims, or chain-of-thought explanations.
6. Confidence must be a float between 0.0 and 1.0 representing classification confidence.
"""


class AIServiceError(Exception):
    """Base exception for AI Service errors."""
    pass


class GeminiClientProtocol(Protocol):
    """Protocol defining the interface expected from a Gemini client."""

    def analyze_text(self, prompt: str) -> str:
        ...


class GoogleGenAIClient:
    """Client utilizing the Google GenAI SDK (google-genai / google-generativeai)."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model_name = model_name
        self._client = None
        self._init_client()

    def _init_client(self):
        # First attempt google.genai (new SDK)
        try:
            from google import genai
            from google.genai import types
            self._genai = genai
            self._types = types
            self._client = genai.Client(api_key=self.api_key)
            self._sdk_type = "google-genai"
            logger.info("Initialized Google GenAI modern SDK client with model: %s", self.model_name)
            return
        except ImportError:
            pass

        # Fallback to google.generativeai (legacy SDK)
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._legacy_genai = genai
            self._sdk_type = "google-generativeai"
            logger.info("Initialized Google GenerativeAI legacy SDK client with model: %s", self.model_name)
            return
        except ImportError as exc:
            raise AIServiceError(
                "Neither 'google-genai' nor 'google-generativeai' package is available."
            ) from exc

    def analyze_text(self, prompt: str) -> str:
        """Call Gemini API with structured JSON output enforcement and fallback resilience."""
        if not self.api_key:
            raise AIServiceError("Gemini API key is missing or not configured.")

        # Candidate models to try in order of preference
        candidate_models = [self.model_name]
        for fallback in ["gemini-flash-latest", "gemini-flash-lite-latest", "gemini-3.1-flash-lite"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        last_error = None
        for model_to_use in candidate_models:
            try:
                if self._sdk_type == "google-genai":
                    from google.genai import types
                    config = types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        response_mime_type="application/json",
                        response_schema=IncidentAnalysisResult,
                        temperature=0.1,
                    )
                    response = self._client.models.generate_content(
                        model=model_to_use,
                        contents=prompt,
                        config=config,
                    )
                    if not response or not response.text:
                        raise AIServiceError("Empty response received from Gemini API.")
                    return response.text

                elif self._sdk_type == "google-generativeai":
                    model = self._legacy_genai.GenerativeModel(
                        model_name=model_to_use,
                        generation_config={
                            "response_mime_type": "application/json",
                            "response_schema": IncidentAnalysisResult,
                            "temperature": 0.1,
                        },
                        system_instruction=SYSTEM_INSTRUCTION,
                    )
                    response = model.generate_content(prompt)
                    if not response or not response.text:
                        raise AIServiceError("Empty response received from Gemini API.")
                    return response.text

            except Exception as exc:
                last_error = exc
                logger.warning("Attempt with model '%s' failed: %s. Trying next candidate...", model_to_use, exc)
                continue

        logger.error("All Gemini model attempts failed: %s", str(last_error), exc_info=True)
        raise AIServiceError(f"Gemini API request failed: {str(last_error)}") from last_error


class AIService:
    """Core AI Service that coordinates incident analysis and validation."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        gemini_client: Optional[Union[GoogleGenAIClient, GeminiClientProtocol]] = None,
    ):
        self.settings = settings or get_settings()
        self._gemini_client = gemini_client

    @property
    def gemini_client(self) -> GeminiClientProtocol:
        if self._gemini_client is None:
            if not self.settings.GEMINI_API_KEY:
                logger.warning("GEMINI_API_KEY is not set in environment or config.")
            self._gemini_client = GoogleGenAIClient(
                api_key=self.settings.GEMINI_API_KEY or "",
                model_name=self.settings.GEMINI_MODEL,
            )
        return self._gemini_client

    def build_prompt(self, incident: IncidentCreatedEvent) -> str:
        """Construct the analysis prompt from the input incident."""
        location_info = ""
        if incident.latitude is not None and incident.longitude is not None:
            location_info = f"\nLocation: Latitude {incident.latitude}, Longitude {incident.longitude}"

        return (
            f"Incident Analysis Request:\n"
            f"Incident ID: {incident.incidentId}\n"
            f"Title: {incident.title}\n"
            f"Description: {incident.description}"
            f"{location_info}\n\n"
            f"Perform the analysis and return the structured JSON object."
        )

    def _extract_json(self, raw_text: str) -> dict:
        """Extract JSON dictionary from text with markdown codeblock stripping."""
        text = raw_text.strip()
        # Strip markdown ```json ... ``` wrapper if present
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("Failed to decode JSON from Gemini output: %s", raw_text)
            raise AIServiceError(f"Invalid JSON returned by AI model: {exc}") from exc

    def analyze_incident(self, incident: IncidentCreatedEvent) -> IncidentAnalyzedEvent:
        """Analyze an incident and return the validated IncidentAnalyzedEvent.

        Args:
            incident: Validated incident creation event.

        Returns:
            IncidentAnalyzedEvent: Validated AI analysis results.

        Raises:
            AIServiceError: If the AI API fails or output validation fails.
        """
        logger.info("Analyzing incident: incidentId=%s title='%s'", incident.incidentId, incident.title)

        prompt = self.build_prompt(incident)
        try:
            raw_response = self.gemini_client.analyze_text(prompt)
        except AIServiceError:
            raise
        except Exception as exc:
            logger.error("Gemini client error for incidentId=%s: %s", incident.incidentId, exc, exc_info=True)
            raise AIServiceError(f"Gemini API request failed: {str(exc)}") from exc

        parsed_data = self._extract_json(raw_response)

        # Inject original incidentId for full event validation
        parsed_data["incidentId"] = incident.incidentId

        try:
            analyzed_event = IncidentAnalyzedEvent.model_validate(parsed_data)
        except Exception as exc:
            logger.error(
                "Pydantic output validation failed for incidentId=%s: %s | Raw: %s",
                incident.incidentId,
                str(exc),
                raw_response,
            )
            raise AIServiceError(f"AI output failed schema validation: {str(exc)}") from exc

        logger.info(
            "AI analysis completed: incidentId=%s category=%s severity=%s confidence=%.2f",
            analyzed_event.incidentId,
            analyzed_event.category.value,
            analyzed_event.severity.value,
            analyzed_event.confidence,
        )

        return analyzed_event
