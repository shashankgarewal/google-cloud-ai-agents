def estimate_transport_cost(distance_km: float, 
                             quantity_kg: float, 
                             mandi_price_per_quintal: float, 
                             vehicle_type: str = "mini_truck"
                             ):
    """
    Estimates transport cost and net price per kg after transportation.

    Args:
        distance_km: Road distance in km (get this from the maps tool first).
        quantity_kg: Total crop quantity in kilograms.
        mandi_price_per_quintal: Current mandi price in Rs per quintal (100kg).
        vehicle_type: One of "bike" (< 200kg), "auto" (< 1000kg), "mini_truck" (< 2000kg), 
                      "truck" (< 10000kg). Defaults to mini_truck.

    Returns:
        A dict with total_transport_cost, cost_per_kg, mandi_price_per_kg,
        net_price_per_kg, and a viability note.
    """
    # Realistic rates (Rs per km, fully loaded)
    rates = {
        "bike":       2.5,   # motorcycle with crate, < 200kg
        "auto":       10.0,  # 3-wheeler autos (rickshaw) < 1 tonnes
        "mini_truck": 18.0,  # Tata Ace / Mahindra, < 2 tonnes
        "truck":      32.0,  # medium truck, < 10 tonnes
    }

    rate = rates.get(vehicle_type, 18.0)
    total_transport_cost = distance_km * rate
    cost_per_kg = total_transport_cost / quantity_kg
    mandi_price_per_kg = mandi_price_per_quintal / 100

    net_price_per_kg = mandi_price_per_kg - cost_per_kg

    return {
        "distance_km": round(distance_km, 1),
        "vehicle_type": vehicle_type,
        "total_transport_cost_rs": round(total_transport_cost, 2),
        "cost_per_kg": round(cost_per_kg, 2),
        "mandi_price_per_kg": round(mandi_price_per_kg, 2),
        "net_price_per_kg": round(net_price_per_kg, 2),
        "viable": net_price_per_kg > 0,
        "note": (
            f"After ₹{round(cost_per_kg,2)}/kg transport cost over {round(distance_km,1)}km, "
            f"net realisation is ₹{round(net_price_per_kg,2)}/kg."
            if net_price_per_kg > 0
            else f"Transport cost (₹{round(cost_per_kg,2)}/kg) exceeds mandi price. Not viable."
        )
    }