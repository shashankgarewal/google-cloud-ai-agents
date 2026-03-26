import os
import requests
from dotenv import load_dotenv
from .mcp_tools import get_distance
from pydantic import BaseModel, Field
from typing import List

load_dotenv("../.env")
api_key = os.getenv("MANDI_DATA_API_KEY")
primary_url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
fallback_url = "https://api.data.gov.in/resource/35985678-0d79-46b4-9ed6-6f13308a1d24"

# ------------------------------- output schema ------------------------------ #
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

class ErrorResponse(BaseModel):
    error: str
    
# ---------------------------------- helper ---------------------------------- #

def _build_params(crop: str, state: str, district: str, mandi: str, extra_filters: dict) -> dict:

    params = {
        "api-key": api_key,
        "format": "json",
        "filters[commodity]": crop,
    }

    if state:
        params["filters[state.keyword]"] = state
    if district:
        params["filters[district]"] = district
    if mandi:
        params["filters[market]"] = mandi

    if extra_filters:
        params.update(extra_filters)

    return params

# ------------------------------- main function ------------------------------ #
def get_mandi_prices(crop: str, state: str = None, district: str = None, mandi: str = None):
    """
    Fetches latest prices of a crop at different mandis (markets) from India's Agmarknet database.

    Args:
        crop (str): crop name e.g., "onion", "wheat" in api supported format
        state: Optional state name, e.g. "Madhya Pradesh", "Maharashtra".
        district: Optional district name, e.g. "Dewas", "Indore", "Nashik".
        mandi: Optional specific market/mandi name, e.g. "Dewas", "Azadpur".
    """
    primary_params = _build_params(crop, state, district, mandi, {})
    
    try:
        response = requests.get(primary_url, params=primary_params)
        
        if response.status_code != 200:
            return ErrorResponse(error="API request failed")
        
        data = response.json()
        raw_records = data.get("records", [])
        
        if not raw_records:
            return ErrorResponse(error="No data found for given filters today")
        
        records = [MandiRecord(**r) for r in raw_records]
    except Exception as e:
        return ErrorResponse(error=str(e))

    return MandiResponse(records=records)

def estimate_transport_cost(from_farmer: str, to_mandi: str):
    distance = get_distance(from_farmer, to_mandi)
    
    cost_per_km = 10  # simple assumption
    return distance * cost_per_km