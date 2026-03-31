import os
import math
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from itertools import product

load_dotenv("../.env")
api_key = os.getenv("MANDI_DATA_API_KEY")

primary_url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
fallback_url = "https://api.data.gov.in/resource/35985678-0d79-46b4-9ed6-6f13308a1d24"

# guardrail - prevent from extreme api calls 
BATCH_SIZE = 100
MAX_PAGES = 5
MAX_COMBINATIONS = 10

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
    total_fetched: int
    total_records: int

class ErrorResponse(BaseModel):
    error: str
    
# ---------------------------------- helper ---------------------------------- #

def _build_params(crop, state, district, mandi, 
                  offset=0, limit=BATCH_SIZE):

    params = {
        "api-key": api_key,
        "format": "json",
        "limit": limit,
        "offset": offset,

    }
    
    if crop:
        params["filters[commodity]"] = crop
    if state:
        params["filters[state.keyword]"] = state
    if district:
        params["filters[district]"] = district
    if mandi:
        params["filters[market]"] = mandi

    return params


# ------------------------------- main function ------------------------------ #
def get_current_mandi_prices(crops: Optional[List[str]] = None,
                             states: Optional[List[str]] = None,
                             districts: Optional[List[str]] = None,
                             mandis: Optional[List[str]] = None
                             ):
    """
    Fetches latest price data with support for multiple filters
    """
    crop_list = crops or [None]
    state_list = states or [None]
    district_list = districts or [None]
    mandi_list = mandis or [None]
    
    # Guardrail
    total_combinations = (len(crop_list) * 
                          len(state_list) *
                          len(district_list) * 
                          len(mandi_list)
                          )
    
    if total_combinations > MAX_COMBINATIONS:
        return ErrorResponse(error="Too many filter combinations requested")

    fetched_records = []    # combine records list fetched for filter combination
    available_records = 0     # total records in api database - may not fetch all record 
    
    # --------------------- Iterate over filter combinations --------------------- #
    for crop, state, district, mandi in product(
        crop_list, state_list, district_list, mandi_list
        ):
        # ---------------------------- probe total record ---------------------------- #
        try:
            probe_params = _build_params(
                crop, state, district, mandi, offset=0, limit=1
                )
            response = requests.get(primary_url, params=probe_params, timeout=8)
            if response.status_code != 200 or not response.content:
                continue
            
            data = response.json()
            total = int(data.get("total", 0))
            available_records += total
            
        except Exception:
            continue
        
        # skip this filters combo - no record
        if total == 0:
            continue
                    
        # -------------------------- fetch record in batches ------------------------- #
        
        # guardrail - prevent too many api requests
        pages = math.ceil(total / BATCH_SIZE)
        pages = min(pages, MAX_PAGES)
        
        for page in range(pages):
            offset = page * BATCH_SIZE
                
            primary_params = _build_params(
                crop, state, district, mandi, offset=offset
                )
            
            try:
                response = requests.get(primary_url, params=primary_params, timeout=8)
                
                if response.status_code != 200 or not response.content:
                    break
                
                data = response.json()
                raw_records = data.get("records", [])
                
                if not raw_records:
                    break
                
                fetched_records.extend(
                    [MandiRecord(**r) for r in raw_records]
                    )
            except Exception:
                continue
            

    return MandiResponse(records=fetched_records,
                         total_fetched = len(fetched_records),
                         total_records = available_records
                         )