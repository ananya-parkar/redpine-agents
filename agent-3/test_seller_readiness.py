# agent-3/test_seller_readiness.py
from collection.signal_collection import collect_signals
from extraction.signal_extractor import extract_signals
from scoring.seller_readiness import calculate_seller_readiness

signals = collect_signals("Kadey-Krogen Yachts")
extracted = extract_signals(signals["raw_content"])
score = calculate_seller_readiness(extracted)

print("\nEXTRACTED SIGNALS\n")
print(extracted)

print("\nSELLER READINESS\n")
print(score)