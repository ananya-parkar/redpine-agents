import json
import re
import time
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Newer Claude models reject non-default `temperature` (400 "deprecated")
# AND reject assistant-message prefill. Probe temperature once, remember.
_SUPPORTS_TEMPERATURE = None  # None=unknown, True/False once probed

# Debug switch: set LLM_DEBUG=1 in the environment to print the raw reply
# whenever JSON parsing fails, so you can see exactly what came back.
import os
_DEBUG = os.getenv("LLM_DEBUG", "") == "1"


def _repair_truncated_json(raw: str) -> str:
    raw = raw.strip()
    if raw.count('"') % 2 != 0:
        raw += '"'
    ob, cb = raw.count("{"), raw.count("}")
    obr, cbr = raw.count("["), raw.count("]")
    raw += "]" * max(0, obr - cbr)
    raw += "}" * max(0, ob - cb)
    return raw


def _extract_json(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r'^```[a-zA-Z]*\n?', '', t).strip()
    t = re.sub(r'\n?```$', '', t).strip()
    start = t.find("{")
    end   = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        return t[start:end + 1]
    return t


def _text_of(resp) -> str:
    """
    Concatenate ONLY the visible text blocks. Adaptive-thinking models
    return thinking/other blocks too — those must be skipped, we only
    want the final answer text.
    """
    parts = []
    for block in resp.content:
        btype = getattr(block, "type", None)
        if btype == "text":
            parts.append(block.text)
        elif btype in ("thinking", "redacted_thinking"):
            continue  # internal reasoning — never JSON, skip
        elif hasattr(block, "text") and isinstance(getattr(block, "text"), str):
            parts.append(block.text)
    return "".join(parts)


def _create(system: str, user_content: str, max_tokens: int,
            temperature: float):
    global _SUPPORTS_TEMPERATURE
    kwargs = dict(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    if _SUPPORTS_TEMPERATURE is not False:
        kwargs["temperature"] = temperature
    try:
        return client.messages.create(**kwargs)
    except Exception as e:
        msg = str(e).lower()
        if "temperature" in msg and any(w in msg for w in
                ("deprecated", "not supported", "unsupported", "invalid")):
            _SUPPORTS_TEMPERATURE = False
            kwargs.pop("temperature", None)
            return client.messages.create(**kwargs)
        raise


def call_llm_json(system: str, user_content: str,
                   max_tokens: int = 1000, temperature: float = 0.0,
                   max_retries: int = 3) -> dict:
    # Give thinking models headroom: if the caller asked for a small
    # max_tokens, thinking can eat all of it and leave no room for the
    # actual JSON. Floor it so there's always output budget left.
    effective_max = max(max_tokens, 2000)

    system_json = (system.rstrip()
                   + "\n\nIMPORTANT: Respond with ONLY the JSON object. "
                     "No explanation, no markdown code fences, no text "
                     "before or after the JSON.")

    last_err = None
    for attempt in range(max_retries):
        try:
            resp = _create(system_json, user_content, effective_max, temperature)
            text = _text_of(resp)

            if not text.strip():
                # Empty visible text — usually means thinking consumed the
                # whole token budget (stop_reason=max_tokens). Bump budget
                # and retry.
                if _DEBUG:
                    print(f"      [LLM DEBUG] empty text; stop_reason="
                          f"{getattr(resp,'stop_reason',None)}; "
                          f"blocks={[getattr(b,'type',None) for b in resp.content]}",
                          flush=True)
                effective_max = min(effective_max * 2, 8000)
                last_err = ValueError("empty text from model")
                continue

            raw = _extract_json(text)
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return json.loads(_repair_truncated_json(raw))

        except json.JSONDecodeError as e:
            last_err = e
            if _DEBUG:
                print(f"      [LLM DEBUG] JSON parse failed. Raw text was:\n"
                      f"{text[:800]!r}", flush=True)
            continue
        except Exception as e:
            last_err = e
            if "429" in str(e) or "overloaded" in str(e).lower():
                time.sleep(20 * (attempt + 1))
                continue
            raise
    raise last_err