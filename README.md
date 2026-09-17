# Smart Emergency Response & Incident Management Platform

## Service 8 — AI Service

### 1. Service Purpose

The **AI Service** is a core component of the Smart Emergency Response & Incident Management Platform. It asynchronously consumes newly created emergency incidents, applies Google Gemini AI to analyze the situation, and produces structured, validated intelligence for other downstream microservices (such as Dispatch, Response, and Notification services).

#### Key Responsibilities:
1. **Classify the incident** into a strictly normalized category enum.
2. **Estimate severity** (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
3. **Generate a concise, factual summary** (1–2 sentences, no markdown, no reasoning explanations).
4. **Recommend required response teams** (`MEDICAL`, `FIRE`, `POLICE`, `RESCUE`, `DISASTER_RESPONSE`, `HAZMAT`).
5. **Compute confidence score** (normalized float between `0.0` and `1.0`).
6. **Publish structured analysis** as a language-independent JSON event to Kafka topic `incident.analyzed`.
7. **Expose REST API** for development, health checks, and direct testing.

---

### 2. Technology Stack

* **Language**: Python 3.11+ (Tested on Python 3.12)
* **Web Framework**: FastAPI & Starlette
* **Server**: Uvicorn ASGI
* **Validation & Settings**: Pydantic v2 & Pydantic-Settings
* **AI Provider**: Google Gemini API (`google-genai` / `google-generativeai`)
* **Message Broker**: Apache Kafka via `confluent-kafka`
* **Testing**: Pytest, Pytest-Asyncio, HTTPX

---

### 3. Project Structure

```text
ai-service/
├── app/
│   ├── __init__.py                # Package declaration
│   ├── main.py                    # FastAPI application & lifespan lifecycle
│   ├── config.py                  # Pydantic Settings & environment variables
│   │
│   ├── models/                    # Pydantic domain models & contracts
│   │   ├── __init__.py
│   │   ├── incident_created.py    # Input event contract (IncidentCreatedEvent)
│   │   └── incident_analyzed.py   # Output event contract (IncidentAnalyzedEvent & Enums)
│   │
│   ├── kafka/                     # Kafka messaging components
│   │   ├── __init__.py
│   │   ├── consumer.py            # Consumer for 'incident.created' (group: ai-service)
│   │   └── producer.py            # Producer for 'incident.analyzed'
│   │
│   └── services/                  # Business & AI processing
│       ├── __init__.py
│       └── ai_service.py          # Gemini AI integration with structured JSON output & model fallback
│
├── tests/                         # Pytest test suite
│   ├── __init__.py
│   ├── conftest.py                # Fixtures and mock Gemini client
│   ├── test_models.py             # Validation and enum boundary tests
│   ├── test_ai_service.py         # Standard scenarios & AI fallback tests
│   ├── test_api.py                # REST endpoints (/health, /analyze)
│   └── test_kafka.py              # Kafka serialization & pipeline tests
│
├── .env                           # Local environment configuration (git ignored)
├── .env.example                   # Template environment configuration
├── .gitignore                     # Git ignore rules
├── Dockerfile                     # Containerization definition
├── requirements.txt               # Dependencies
└── README.md                      # Service documentation
```

---

### 4. Environment Variables

Configure application settings via `.env` file or environment variables:

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | String | `""` | Google Gemini API Key |
| `GEMINI_MODEL` | String | `gemini-flash-latest` | Primary Gemini model name |
| `KAFKA_BOOTSTRAP_SERVERS` | String | `localhost:9092` | Kafka broker address |
| `KAFKA_INPUT_TOPIC` | String | `incident.created` | Topic to consume new incidents from |
| `KAFKA_OUTPUT_TOPIC` | String | `incident.analyzed` | Topic to publish analyzed intelligence to |
| `KAFKA_CONSUMER_GROUP` | String | `ai-service` | Consumer group ID |
| `KAFKA_ENABLED` | Boolean | `true` | Set to `false` for standalone REST development |
| `APP_ENV` | String | `development` | `development`, `staging`, or `production` |
| `LOG_LEVEL` | String | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `PORT` | Integer | `8000` | HTTP server port |

---

### 5. Event Contracts

#### Input Event: `incident.created`

Published when a citizen or operator reports an incident.

```json
{
  "incidentId": 101,
  "title": "Major road accident",
  "description": "Three cars crashed. One person appears unconscious and smoke is coming from one vehicle.",
  "latitude": 16.3065,
  "longitude": 80.4375
}
```

| Field | Type | Required | Notes |
| :--- | :--- | :--- | :--- |
| `incidentId` | Integer/Long | Yes | Unique incident identifier |
| `title` | String | Yes | Non-empty summary title |
| `description` | String | Yes | Detailed description of the event |
| `latitude` | Float | No | Geographic coordinate (-90 to +90) |
| `longitude` | Float | No | Geographic coordinate (-180 to +180) |

---

#### Output Event: `incident.analyzed`

Published to Kafka after Gemini AI analysis and Pydantic validation.

```json
{
  "incidentId": 101,
  "category": "ROAD_ACCIDENT",
  "severity": "CRITICAL",
  "summary": "Multi-vehicle accident with possible casualties and fire risk.",
  "requiredTeams": [
    "MEDICAL",
    "FIRE",
    "POLICE"
  ],
  "confidence": 0.94
}
```

#### Allowed Enum Values:

- **Categories (`category`)**:
  `FIRE`, `ROAD_ACCIDENT`, `MEDICAL_EMERGENCY`, `CRIME`, `FLOOD`, `EARTHQUAKE`, `BUILDING_COLLAPSE`, `INDUSTRIAL_ACCIDENT`, `ELECTRICAL_HAZARD`, `RESCUE`, `OTHER`
- **Severities (`severity`)**:
  `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- **Response Teams (`requiredTeams`)**:
  `MEDICAL`, `FIRE`, `POLICE`, `RESCUE`, `DISASTER_RESPONSE`, `HAZMAT`

---

### 6. Kafka Event Publishing & Consumption

The AI Service is fully integrated with Apache Kafka:

```text
incident.created (Kafka Topic)
       ↓
[IncidentKafkaConsumer] (Group: ai-service)
       ↓
[AIService] (Google Gemini API Structured JSON)
       ↓
[IncidentKafkaProducer] (Publish IncidentAnalyzedEvent)
       ↓
incident.analyzed (Kafka Topic)
```

#### 1. Consuming from `incident.created`
- The consumer subscribes to `incident.created` with consumer group `ai-service`.
- When a new incident message arrives, it is parsed, validated against `IncidentCreatedEvent`, and sent to the Gemini AI pipeline.

#### 2. Publishing to `incident.analyzed`
- Upon successful AI analysis, the `IncidentKafkaProducer` publishes the validated `IncidentAnalyzedEvent` to `incident.analyzed` with:
  - **Key**: String `incidentId` (e.g., `"101"`) for partition key consistency.
  - **Value**: UTF-8 encoded JSON string matching `IncidentAnalyzedEvent`.

#### 3. How to Test Kafka End-to-End via Command Line

##### Produce a test incident to Kafka:
```powershell
.venv\Scripts\python.exe -c "import json; from confluent_kafka import Producer; p = Producer({'bootstrap.servers': 'localhost:9092'}); event = {'incidentId': 101, 'title': 'Major road accident', 'description': 'Three cars crashed. One person appears unconscious and smoke is coming from one vehicle.'}; p.produce('incident.created', key='101', value=json.dumps(event)); p.flush(); print('Published incident.created event!')"
```

##### Read analyzed intelligence from Kafka:
```powershell
.venv\Scripts\python.exe -c "from confluent_kafka import Consumer; c = Consumer({'bootstrap.servers': 'localhost:9092', 'group.id': 'test-reader', 'auto.offset.reset': 'earliest'}); c.subscribe(['incident.analyzed']); msg = c.poll(timeout=10.0); print(msg.value().decode('utf-8') if msg else 'No message'); c.close()"
```

---
Here is the streamlined, Windows-only version of your setup and startup guide for the `README.md`:

---

### 🚀 Setup and Running Instructions (Windows)

#### 1. Create and Activate the Virtual Environment




* **Command Prompt (CMD):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat

```



#### 2. Install Dependencies

```cmd
pip install --upgrade pip
pip install -r requirements.txt

```

#### 3. Start the Application Service




```cmd
.venv\Scripts\uvicorn app.main:app --reload --port 8000

```



#### 4. Run Apache Kafka (Docker)

If your platform requires event streaming, spin up a local Kafka instance using Docker:

```cmd
docker run -d -p 9092:9092 --name my-kafka apache/kafka:latest

```

---

### 8. REST API Endpoints

Once the service is started, visit the interactive Swagger UI documentation at:
👉 **http://localhost:8000/docs**

#### `GET /api/ai/health`
Health check endpoint.
* **Response**: `200 OK`
```json
{
  "status": "UP"
}
```

#### `POST /api/ai/analyze`
Direct testing endpoint for synchronous incident analysis.

##### Example Request:
```bash
curl -X POST http://localhost:8000/api/ai/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "incidentId": 101,
    "title": "Major road accident",
    "description": "Three cars crashed. One person appears unconscious and smoke is coming from one vehicle.",
    "latitude": 16.3065,
    "longitude": 80.4375
  }'
```

##### Example Response:
```json
{
  "incidentId": 101,
  "category": "ROAD_ACCIDENT",
  "severity": "CRITICAL",
  "summary": "A multi-vehicle collision involving three cars has resulted in at least one unconscious person and smoke emanating from one of the vehicles.",
  "requiredTeams": [
    "MEDICAL",
    "FIRE",
    "POLICE",
    "RESCUE"
  ],
  "confidence": 0.98
}
```

---

### 9. Testing Instructions

Run the automated test suite with pytest:

```powershell
.venv\Scripts\pytest -v
```

The test suite covers:
* **Model Validation**: Field constraints, category & severity enums, required team deduplication, confidence bounds.
* **Standard Scenarios**: Road accident, building fire, medical emergency, low severity collision.
* **AI Service Resilience**: Gemini structured output parsing, markdown fence stripping, API timeout/rate limit handling, invalid schema rejections.
* **REST Endpoints**: Health status, analysis requests, validation error HTTP 422, gateway error HTTP 502.
* **Kafka Integration**: Message deserialization, producer payload validation, duplicate message tolerance.

---

### 10. Error Handling & Resilience

- **Automatic Model Fallback**: If Google's free-tier encounters temporary high-demand spikes (503 Service Unavailable) or rate limits, the AI Service automatically attempts fallback models (`gemini-flash-latest`, `gemini-flash-lite-latest`, `gemini-3.1-flash-lite`) before failing.
- **Invalid AI Output**: Validated through Pydantic `IncidentAnalysisResult`. Any malformed category or field causes schema rejection and logs a detailed warning.
- **Kafka Resilience**: Kafka initialization failures during startup log a warning and fallback gracefully so the REST API remains fully operational in standalone mode.
- **Security**: API keys and credentials are never logged to console or committed to version control.
