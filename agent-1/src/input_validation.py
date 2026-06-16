# agent-1/src/input_validation.py

def validate_inputs(data):
    if not data["location"]:
        raise ValueError("Location is required")

    radius = float(data["radius_miles"])
    if radius <= 0:
        raise ValueError("Radius must be greater than 0")

    if (data.get("min_rooms") and data.get("max_rooms")):
        if int(data["min_rooms"]) > int(data["max_rooms"]):
            raise ValueError(
                "Min rooms cannot exceed max rooms"
            )

    if data.get("year_built_range"):
        try:
            start, end = data["year_built_range"].split("-")
        except ValueError:
            raise ValueError(
                "Year range must be YYYY-YYYY"
            )

        if int(start) > int(end):
            raise ValueError("Invalid year range")

    valid_tiers = [
        "Economy",
        "Midscale",
        "Upscale"
    ]

    if data.get("price_tier"):
        if data["price_tier"] not in valid_tiers:
            raise ValueError("Invalid price tier")

    return True