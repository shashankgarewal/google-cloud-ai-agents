import requests
from .mcp_tools import get_distance

def get_mandi_prices(crop: str, location: str):
    """
    Fetches current crop prices at APMC mandis.

    Args:
        crop (str): crop name e.g., "onion", "wheat" in api supported format
        location (str): city, state, district, pincode information in api supported format
    """
    data = [
        {"mandi": "Indore", "price": 2200},
        {"mandi": "Bhopal", "price": 2100},
        {"mandi": "Ujjain", "price": 2250},
    ]

    return sorted(data, key=lambda x: x["price"], reverse=True)

def estimate_transport_cost(from_farmer: str, to_mandi: str):
    distance = get_distance(from_farmer, to_mandi)
    
    cost_per_km = 10  # simple assumption
    return distance * cost_per_km