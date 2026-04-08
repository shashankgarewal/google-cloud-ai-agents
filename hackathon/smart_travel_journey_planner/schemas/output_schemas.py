"""
output schemas — used for agent-to-agent communication.
TrainDataAgent → OrchestratorAgent boundary.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


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
