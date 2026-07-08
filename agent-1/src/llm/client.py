# agent-1/src/llm/client.py
from anthropic import Anthropic
from src.core.config import ANTHROPIC_API_KEY

client = Anthropic(api_key=ANTHROPIC_API_KEY)
