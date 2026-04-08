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


class BookingConfirmation(BaseModel):
    """
    Sent to the orchestrator when the user clicks 'Buy Now' in the UI.
    Represents a confirmed (or intent-to-book) train selection.
    The orchestrator routes this to the productivity_agent which will:
      - Create a Google Calendar event for the journey
      - Create a Google Task reminder to book a cab 2 hrs before departure
      - Draft a Gmail reminder email to the user
    """
    intent: str = Field(
        "booking_confirmed",
        description="Fixed marker so the orchestrator recognises this as a booking confirmation, not a search query.",
    )
    # Journey details
    source: str = Field(..., description="Departure station name")
    destination: str = Field(..., description="Arrival station name")
    date: str = Field(..., description="Travel date in YYYY-MM-DD format")
    # Selected train
    train_id: str = Field(..., description="Train number / identifier")
    train_name: str = Field(..., description="Train name")
    departure_time: str = Field(..., description="Scheduled departure time (HH:MM)")
    arrival_time: str = Field(..., description="Scheduled arrival time (HH:MM)")
    reliability_score: float = Field(..., description="Reliability score 0–1 from recommender")
    reason: str = Field(..., description="Why this train was recommended")
    buy_now_link: str = Field(..., description="MakeMyTrip booking URL")