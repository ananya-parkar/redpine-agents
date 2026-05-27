# agent-1/src/llm/client.py

from openai import OpenAI
from src.config import OPENAI_API_KEY

print(f"[LLM CONFIG] OPENAI KEY PRESENT: {bool(OPENAI_API_KEY)}",flush=True)
if OPENAI_API_KEY:
    print(f"[LLM CONFIG] KEY PREFIX: {OPENAI_API_KEY[:7]}",flush=True)

client = OpenAI(api_key=OPENAI_API_KEY)

# from openai import OpenAI
# from src.config import GROK_API_KEY

# print(
#     f"[LLM CONFIG] GROK KEY PRESENT: {bool(GROK_API_KEY)}",
#     flush=True
# )

# if GROK_API_KEY:
#     print(
#         f"[LLM CONFIG] KEY PREFIX: {GROK_API_KEY[:5]}",
#         flush=True
#     )

# client = OpenAI(
#     api_key=GROK_API_KEY,
#     base_url="https://api.x.ai/v1"
# )