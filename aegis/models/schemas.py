from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict, Any

# --- Health Schema ---
class HealthResponse(BaseModel):
    status: str
    service: str

# --- Incident Schemas (Placeholders for Future Use) ---
class IncidentBase(BaseModel):
    incident_id: str
    timestamp: datetime
    severity: str
    service_name: str
    symptoms: str

class IncidentCreate(IncidentBase):
    pass

class Incident(IncidentBase):
    actual_root_cause: Optional[str] = None
    resolution: Optional[str] = None
    duration_minutes: Optional[int] = None

    class Config:
        from_attributes = True

# --- Evidence & RCA Schemas (Placeholders for Future Use) ---
class EvidencePacket(BaseModel):
    incident_id: str
    service_name: str
    start_time: datetime
    metrics: List[Dict[str, Any]] = []
    logs: List[Dict[str, Any]] = []
    deployments: List[Dict[str, Any]] = []
    dependencies: List[Dict[str, Any]] = []

class RCAMetricsAnalysis(BaseModel):
    anomalies_detected: List[str]
    correlation_notes: str

class RCALogsAnalysis(BaseModel):
    error_patterns: List[str]
    suspect_traces: List[str]

class RCADeploymentAnalysis(BaseModel):
    suspect_deployments: List[str]
    configuration_changes: List[str]

class RCAResponse(BaseModel):
    incident_id: str
    service_name: str
    suspected_root_cause: str
    evidence_summary: str
    recommended_mitigation: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    metrics_analysis: Optional[RCAMetricsAnalysis] = None
    logs_analysis: Optional[RCALogsAnalysis] = None
    deployment_analysis: Optional[RCADeploymentAnalysis] = None
