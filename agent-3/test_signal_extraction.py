# agent-3/test_signal_extraction.py
from collection.signal_collection import collect_signals
from extraction.signal_extractor import extract_signals

signals = collect_signals("Kadey-Krogen Yachts")
result = extract_signals(signals["raw_content"])

print(result)