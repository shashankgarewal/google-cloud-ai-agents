from pydantic import BaseModel, Field
from typing import List, Optional


class MandiRecord(BaseModel):
    state: str = Field(alias="state")
    district: str = Field(alias="district")
    market: str = Field(alias="market")
    commodity: str = Field(alias="commodity")
    variety: str = Field(alias="variety")
    arrival_date: str = Field(alias="arrival_date")
    min_price: float = Field(alias="min_price")
    max_price: float = Field(alias="max_price")
    modal_price: float = Field(alias="modal_price")

class MandiResponse(BaseModel):
    records: List[MandiRecord]
    total_fetched: int
    total_records: int

class ErrorResponse(BaseModel):
    error: str
    
class DistanceRecord(BaseModel):
    mandi: str
    distance_km: float


class TransportInsight(BaseModel):
    mandi: str
    distance_km: float
    vehicle_type: str

    total_transport_cost_rs: float
    cost_per_kg: float

    mandi_price_per_kg: float
    net_price_per_kg: float

    viable: bool
    note: str


class StructuredData(BaseModel):
    original_user_message: str

    mandi_prices: Optional[List[MandiRecord]] = None
    transport_insights: Optional[List[TransportInsight]] = None
    map_data: Optional[list] = None

    notes: Optional[List[str]] = None
    assumptions: Optional[List[str]] = None