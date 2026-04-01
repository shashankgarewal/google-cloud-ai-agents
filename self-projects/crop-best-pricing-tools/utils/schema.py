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


class TransportCostRecord(BaseModel):
    mandi: str
    cost: float


class NetPriceRecord(BaseModel):
    mandi: str
    net_price: float
    
class StructuredData(BaseModel):
    user_query: str
    crop: Optional[str]
    location: Optional[str]

    mandi_prices: List[MandiRecord]

    distance_data: Optional[List[DistanceRecord]] = None
    transport_costs: Optional[List[TransportCostRecord]] = None
    net_prices: Optional[List[NetPriceRecord]] = None

    assumptions: Optional[List[str]] = None