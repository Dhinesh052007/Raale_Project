"""Pydantic schemas for data validation and API responses."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


class BranchBase(BaseModel):
    branch_id: str = Field(..., description="Unique branch identifier (e.g., B001)")
    name: str = Field(..., description="Human-readable branch name")
    region: str = Field(..., description="Geographical or operational region")
    wan_type: str = Field(default="MPLS Primary", description="Branch WAN connectivity profile")


class BranchResponse(BranchBase):
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EventBase(BaseModel):
    event_id: str = Field(..., description="Globally unique identifier for the event")
    event_time: datetime = Field(..., description="Timestamp when event occurred at source")
    arrival_time: Optional[datetime] = Field(default=None, description="Timestamp when event reached collector")
    branch_id: str = Field(..., description="Originating branch identifier")
    source: str = Field(..., description="Event origin: ACTIVE_PROBE, WIFI, APPLICATION, USER_REPORT")

    # Probe metrics
    latency_ms: Optional[float] = Field(default=None, description="Round-trip network latency in ms")
    jitter_ms: Optional[float] = Field(default=None, description="Latency jitter variation in ms")
    packet_loss_percent: Optional[float] = Field(default=None, description="Observed packet loss percentage (0-100)")
    dns_response_ms: Optional[float] = Field(default=None, description="DNS lookup response time in ms")

    # Wi-Fi metrics
    wifi_rssi: Optional[float] = Field(default=None, description="Wi-Fi Received Signal Strength Indicator in dBm")
    wifi_retry_rate: Optional[float] = Field(default=None, description="Wi-Fi frame retry rate in percentage (0-100)")
    channel_utilisation: Optional[float] = Field(default=None, description="Wi-Fi radio channel utilisation (0-100)")

    # Application metrics
    application_response_ms: Optional[float] = Field(default=None, description="End-to-end app response time in ms")
    http_status: Optional[int] = Field(default=None, description="HTTP response code (e.g., 200, 500, 503)")
    transaction_duration_ms: Optional[float] = Field(default=None, description="Database or backend transaction duration in ms")

    # Contextual
    user_report: Optional[str] = Field(default=None, description="User complaint text if applicable")
    sequence_number: Optional[int] = Field(default=None, description="Monotonically increasing sequence number")

    @field_validator("latency_ms", "jitter_ms", "dns_response_ms", "application_response_ms", "transaction_duration_ms")
    @classmethod
    def validate_non_negative(cls, v, info):
        if v is not None and v < 0:
            raise ValueError(f"{info.field_name} cannot be negative (got {v})")
        return v

    @field_validator("packet_loss_percent", "wifi_retry_rate", "channel_utilisation")
    @classmethod
    def validate_percentage(cls, v, info):
        if v is not None and (v < 0 or v > 100):
            raise ValueError(f"{info.field_name} must be between 0 and 100 percent (got {v})")
        return v

    @field_validator("http_status")
    @classmethod
    def validate_http_status(cls, v):
        if v is not None and (v < 100 or v > 599):
            raise ValueError(f"HTTP status code must be between 100 and 599 (got {v})")
        return v


class EventCreate(EventBase):
    pass


class EventResponse(EventBase):
    id: int
    arrival_time: datetime
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IncidentResponse(BaseModel):
    id: int
    incident_id: str
    branch_id: str
    start_time: datetime
    end_time: Optional[datetime]
    status: str
    probable_cause: str
    peak_latency: Optional[float]
    peak_packet_loss: Optional[float]
    peak_application_response: Optional[float]
    user_report_count: int
    severity: str
    supporting_evidence: Optional[str]
    duration_seconds: Optional[float]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IncidentDetailResponse(IncidentResponse):
    """Incident with complete forensic evidence window (2-min before + incident + 2-min after)."""
    evidence_events: List[EventResponse] = []
    associated_user_reports: List[Dict[str, Any]] = []


class UserReportCreate(BaseModel):
    report_id: Optional[str] = None
    branch_id: str
    event_time: datetime
    location: str
    description: str
    severity: str = "HIGH"


class UserReportResponse(BaseModel):
    id: int
    report_id: str
    branch_id: str
    event_time: datetime
    location: str
    description: str
    severity: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProcessingLogResponse(BaseModel):
    id: int
    event_id: str
    processing_status: str
    reason: Optional[str]
    processed_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IngestionResult(BaseModel):
    success: bool
    status: str
    event_id: str
    message: str


class BatchIngestionResult(BaseModel):
    total_received: int
    accepted: int
    duplicates_ignored: int
    out_of_order_accepted: int
    delayed_accepted: int
    rejected: int
    details: List[IngestionResult] = []


class IntegrityStats(BaseModel):
    total_events: int
    valid_events: int
    duplicate_events: int
    delayed_events: int
    out_of_order_events: int
    rejected_events: int
    recovered_events: int


class ExperimentScenarioRequest(BaseModel):
    num_incidents: int = Field(default=100, ge=10, le=500, description="Total injected incidents to evaluate")
    random_seed: int = Field(default=42, description="Random seed for reproducibility")
    inject_duplicate_rate: float = Field(default=0.05, ge=0.0, le=0.5)
    inject_out_of_order_rate: float = Field(default=0.05, ge=0.0, le=0.5)
    inject_delayed_rate: float = Field(default=0.05, ge=0.0, le=0.5)
