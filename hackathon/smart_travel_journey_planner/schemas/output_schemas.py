"""
output schemas — used for agent-to-agent communication.
TrainDataAgent → OrchestratorAgent boundary.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class _TrainInfo(BaseModel):
    train_id: str = Field(..., description="Unique train identifier / number")
    train_name: str = Field(..., description="Train name")
    departure_time: str = Field(..., description="Scheduled departure time (ISO-8601 or HH:MM)")
    arrival_time: str = Field(..., description="Scheduled arrival time (ISO-8601 or HH:MM)")
    delay_minutes: Optional[int] = Field(None, description="Current delay in minutes (None = unknown)")
    stations: Optional[List[str]] = Field(None, description="Intermediate halt stations")


class TrainDataResponse(BaseModel):
    trains: List[_TrainInfo] = Field(..., description="List of available trains")
    source: str = Field(..., description="Queried source station")
    destination: str = Field(..., description="Queried destination station")
    date: str = Field(..., description="Queried travel date")

class _Recommendation(BaseModel):
    train_id: str = Field(..., description="Train identifier")
    train_name: str = Field(..., description="Train name")
    reliability_score: float = Field(
        ..., ge=0.0, le=1.0, description="LLM-assigned reliability score between 0 and 1"
    )
    reason: str = Field(..., description="Short LLM-generated reason for the ranking")

    @field_validator("reliability_score")
    @classmethod
    def clamp_score(cls, v: float) -> float:
        return round(max(0.0, min(1.0, v)), 4)


class TrainRecommendationResponse(BaseModel):
    recommended_train: _Recommendation = Field(..., description="Top-ranked train")
    alternatives: List[_Recommendation] = Field(
        ..., description="Up to 2 alternative trains"
    )
    insights: Dict[str, Any] = Field(
        ..., description="Additional LLM-generated insights about the route / options"
    )
