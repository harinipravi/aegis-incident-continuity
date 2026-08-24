# Aegis Incident Continuity - Backend Service

This is the minimal FastAPI-based backend foundation for Aegis. It provides a structured, extensible architecture for executing BigQuery telemetry extraction, Gemini-based AI reasoning, and persistent structured Root Cause Analysis (RCA).

---

## Project Structure

The project code is organized as follows:

```text
aegis-incident-continuity/
├── aegis/                         # Core aegis package
│   ├── models/                    # Pydantic schemas and DB entities
│   │   ├── __init__.py
│   │   └── schemas.py             # API schemas (including Health, Evidence & RCA models)
│   ├── routers/                   # API endpoints
│   │   ├── __init__.py
│   │   ├── health.py              # Health check router (/health)
│   │   └── incidents.py           # RCA/Incidents router placeholder (/incidents)
│   ├── services/                  # Business logic and integrations
│   │   ├── __init__.py
│   │   ├── bigquery.py            # BigQuery evidence extractor (placeholder)
│   │   ├── gemini.py              # Gemini model reasoning (placeholder)
│   │   └── rca.py                 # Coordinator service for BQ + Gemini flows (placeholder)
│   ├── __init__.py
│   ├── config.py                  # Pydantic Settings configuration loader
│   └── database.py                # State persistence client and session setup (placeholder)
├── data/                          # Telemetry CSV files (unchanged)
├── .env.example                   # Template for backend configuration
├── app.py                         # FastAPI application entry point
├── generate_data.py               # Data generation script
├── requirements.txt               # Backend Python dependencies
└── verify_data.py                 # Telemetry validation script
```

---

## Setup & Running the Server

### 1. Create a Virtual Environment

Initialize and activate a virtual environment:

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate
```

### 2. Install Dependencies

Install the packages from `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file from the example template:

```bash
cp .env.example .env
```

Review `.env` and fill in necessary configuration parameters as required by future integration steps.

### 4. Run the API Server

Start the development server with live reload:

```bash
python app.py
```

Or run via Uvicorn:

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

---

## Health Check Endpoint

### GET `/health`

Verifies that the service is running and correctly responding.

**Request:**

```bash
curl -X GET http://localhost:8000/health
```

**Response:**

```json
{
  "status": "ok",
  "service": "aegis-incident-continuity"
}
```
