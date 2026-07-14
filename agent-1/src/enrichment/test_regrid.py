from src.enrichment.owner_details import detect_owner_details

print(
    detect_owner_details(
        address="5818 Diana Dr, Garland, TX",
        latitude=32.89,
        longitude=-96.64
    )
)