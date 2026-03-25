def get_distance(from_farmer, to_mandi):
    """
    Determine the distance between from_farmer to to_mandi

    Args:
        from_farmer (_type_): _description_
        to_mandi (_type_): _description_

    Returns:
        distance: return the best distance between 
    """
    distances = {
        ("Bhopal", "Indore"): 190,
        ("Bhopal", "Ujjain"): 180,
    }
    return distances.get((from_farmer, to_mandi), 200)