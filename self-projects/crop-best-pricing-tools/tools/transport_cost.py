from mandi_agent.mcp_tools import get_distance

def estimate_transport_cost(from_farmer: str, to_mandi: str):
    distance = get_distance(from_farmer, to_mandi)
    
    cost_per_km = 10  # simple assumption
    return distance * cost_per_km