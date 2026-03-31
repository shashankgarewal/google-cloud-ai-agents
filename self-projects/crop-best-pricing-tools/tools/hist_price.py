import os
import math
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List, Optional
from itertools import product
from datetime import datetime, timedelta

load_dotenv("../.env")
api_key = os.getenv("MANDI_DATA_API_KEY")

primary_url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
fallback_url = "https://api.data.gov.in/resource/35985678-0d79-46b4-9ed6-6f13308a1d24"

# guardrail
BATCH_SIZE = 100
MAX_PAGES = 10
MAX_COMBINATIONS = 10


# ------------------------------- output schema ------------------------------ #
class MandiRecord(BaseModel):
    state: str = Field(alias="State")
    district: str = Field(alias="District")
    market: str = Field(alias="Market")
    commodity: str = Field(alias="Commodity")
    variety: str = Field(alias="Variety")
    arrival_date: str = Field(alias="Arrival_Date")
    min_price: float = Field(alias="Min_Price")
    max_price: float = Field(alias="Max_Price")
    modal_price: float = Field(alias="Modal_Price")


class MandiResponse(BaseModel):
    records: List[MandiRecord]
    total_fetched: int
    total_records: int


class ErrorResponse(BaseModel):
    error: str


# ---------------------------------- helper ---------------------------------- #

def _build_fallback_params(crop, state, district, mandi,
                          arrival_date=None,
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
        params["filters[state]"] = state
    if district:
        params["filters[district]"] = district
    if mandi:
        params["filters[market]"] = mandi
    if arrival_date:
        params["filters[arrival_date]"] = arrival_date  # DD/MM/YYYY

    return params


# ------------------------------- main function ------------------------------ #
def get_historical_mandi_prices(
    crops: Optional[List[str]] = None,
    states: Optional[List[str]] = None,
    districts: Optional[List[str]] = None,
    mandis: Optional[List[str]] = None,
    days_back: int = 3
):
    """
    Fetch mandi price data from fallback API for last N days.
    """

    crop_list = crops or [None]
    state_list = states or [None]
    district_list = districts or [None]
    mandi_list = mandis or [None]
    
    today = datetime.today().date()
    # fetch record for these dates
    date_list = [
        (today - timedelta(days=i+1)).strftime("%d/%m/%Y")
        for i in range(days_back)
    ]
    print("list of dates: ", date_list)

    # Guardrail
    total_combinations = (
        len(crop_list) *
        len(state_list) *
        len(district_list) *
        len(mandi_list) *
        len(date_list)
    )

    if total_combinations > MAX_COMBINATIONS:
        return ErrorResponse(error="Too many filter combinations requested")

    fetched_records = []
    available_records = 0

    # --------------------- Iterate combinations --------------------- #
    for crop, state, district, mandi, date in product(
        crop_list, state_list, district_list, mandi_list, date_list
    ):

        # ---------------- probe total ---------------- #
        try:
            probe_params = _build_fallback_params(
                crop, state, district, mandi,
                arrival_date=date,
                offset=0,
                limit=1
            )
            print("probes:", probe_params)
            
            response = requests.get(fallback_url, params=probe_params, timeout=8)

            if response.status_code != 200 or not response.content:
                continue

            data = response.json()
            total = int(data.get("total", 0))
            available_records += total

        except Exception:
            continue

        if total == 0:
            continue

        # ---------------- pagination ---------------- #
        pages = math.ceil(total / BATCH_SIZE)
        pages = min(pages, MAX_PAGES)

        for page in range(pages):
            offset = page * BATCH_SIZE

            params = _build_fallback_params(
                crop, state, district, mandi,
                arrival_date=date,
                offset=offset
            )
            print("fetch params:", params)
            

            try:
                response = requests.get(fallback_url, params=params, timeout=8)

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

    return MandiResponse(
        records=fetched_records,
        total_fetched=len(fetched_records),
        total_records=available_records
    )