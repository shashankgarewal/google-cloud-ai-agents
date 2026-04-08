"""
Input schema — the API-layer request body.
"""
from typing import Optional
from pydantic import BaseModel, Field


class TrainQuery(BaseModel):
    source: str = Field(..., description="Departure station name or code")
    destination: str = Field(..., description="Arrival station name or code")
    date: str = Field(..., description="Travel date in YYYY-MM-DD format")
    preference: Optional[str] = Field(
        None,
        description="Optional user preference, e.g. 'fastest', 'least delay', 'earliest arrival'",
    )