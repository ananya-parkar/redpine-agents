# agent-3/llm/client.py
from anthropic import Anthropic
from dotenv import load_dotenv
import os

load_dotenv(override=True)

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))