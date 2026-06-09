# agent-1/src/llm/client.py

from openai import OpenAI
from src.core.config import OPENAI_API_KEY

# print(f"[LLM CONFIG] OPENAI KEY PRESENT: {bool(OPENAI_API_KEY)}",flush=True)
# if OPENAI_API_KEY:
#     print(f"[LLM CONFIG] KEY PREFIX: {OPENAI_API_KEY[:7]}",flush=True)

client = OpenAI(api_key=OPENAI_API_KEY)
