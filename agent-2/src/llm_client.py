import json
import re
import time
import os
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Newer Claude models reject non-default `temperature` (400 "deprecated")
# AND reject assistant-message prefill. Probe temperature once, remember.
_SUPPORTS_TEMPERATURE = None  # None=unknown, True/False once probed

# Debug switch: set LLM_DEBUG=1 in the environment to print the raw reply
# whenever JSON parsing fails.
_DEBUG = os.getenv("LLM_DEBUG", "") == "1"

# Anthropic server-side web search tool. This REPLACES Tavily + SearchAPI
# — Claude runs the search itself (via Anthropic's built-in search
# provider) using the same ANTHROPIC_API_KEY, so no separate Tavily /
# SearchAPI vendor account is needed. Note: web search is billed per
# search by Anthropic on top of normal token cost.
WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 5,   # cap searches per request so cost stays bounded
    "user_location": {"type": "approximate", "country": "US"},
}


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
    Concatenate ONLY the visible text blocks. Thinking blocks and
    web_search tool-use / tool-result blocks are skipped — we only want
    the model's final answer text (which holds the JSON).
    """
    parts = []
    for block in resp.content:
        btype = getattr(block, "type", None)
        if btype == "text":
            parts.append(block.text)
        elif btype in ("thinking", "redacted_thinking",
                       "server_tool_use", "web_search_tool_result"):
            continue  # internal reasoning / search machinery — never JSON
        elif hasattr(block, "text") and isinstance(getattr(block, "text"), str):
            parts.append(block.text)
    return "".join(parts)


def _create(system, user_content, max_tokens, temperature, tools=None):
    """
    One raw Claude call. Handles the "`temperature` is deprecated" 400 by
    retrying WITHOUT temperature and caching that fact. Optionally passes
    server-side tools (e.g. web_search).
    """
    global _SUPPORTS_TEMPERATURE
    kwargs = dict(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    if tools:
        kwargs["tools"] = tools
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
    """
    Drop-in replacement for the old
    openai.chat.completions.create(response_format={"type":"json_object"}).
    No web access — pure reasoning over the text you pass in.
    """
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
                if _DEBUG:
                    print(f"      [LLM DEBUG] empty text; stop_reason="
                          f"{getattr(resp,'stop_reason',None)}", flush=True)
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
                print(f"      [LLM DEBUG] JSON parse failed. Raw:\n{text[:800]!r}", flush=True)
            continue
        except Exception as e:
            last_err = e
            if "429" in str(e) or "overloaded" in str(e).lower():
                time.sleep(20 * (attempt + 1))
                continue
            raise
    raise last_err


def call_llm_web_search_json(system: str, user_content: str,
                             max_tokens: int = 2000, temperature: float = 0.0,
                             max_uses: int = 5, max_retries: int = 3) -> dict:
    """
    Claude does a LIVE WEB SEARCH itself (Anthropic's built-in search
    tool) and then returns a JSON object. This is what replaces Tavily
    (current-status verification) and SearchAPI (stakeholder lookup):
    instead of us calling a search vendor and feeding results to the LLM,
    Claude searches and reasons in one shot.

    The web_search tool needs multiple internal turns (search → read →
    answer), so max_tokens is floored generously. The final answer text
    block holds the JSON; search machinery blocks are skipped by
    _text_of.
    """
    effective_max = max(max_tokens, 3000)
    system_json = (system.rstrip()
                   + "\n\nAfter searching, respond with ONLY the JSON object "
                     "as your FINAL message. No explanation, no markdown code "
                     "fences, no text before or after the JSON.")

    tool = {**WEB_SEARCH_TOOL, "max_uses": max_uses}

    last_err = None
    for attempt in range(max_retries):
        try:
            resp = _create(system_json, user_content, effective_max,
                           temperature, tools=[tool])

            # web_search can end a turn in "pause_turn" if it ran out of
            # steps; in practice the final text still carries the answer.
            text = _text_of(resp)
            if not text.strip():
                if _DEBUG:
                    print(f"      [WEBSEARCH DEBUG] empty text; stop_reason="
                          f"{getattr(resp,'stop_reason',None)}; blocks="
                          f"{[getattr(b,'type',None) for b in resp.content]}",
                          flush=True)
                effective_max = min(effective_max * 2, 8000)
                last_err = ValueError("empty text from web-search model")
                continue

            raw = _extract_json(text)
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return json.loads(_repair_truncated_json(raw))
        except json.JSONDecodeError as e:
            last_err = e
            if _DEBUG:
                print(f"      [WEBSEARCH DEBUG] JSON parse failed. Raw:\n{text[:800]!r}", flush=True)
            continue
        except Exception as e:
            last_err = e
            if "429" in str(e) or "overloaded" in str(e).lower():
                time.sleep(20 * (attempt + 1))
                continue
            raise
    raise last_err


def web_search_text(system: str, user_content: str,
                    max_tokens: int = 2000, temperature: float = 0.0,
                    max_uses: int = 5) -> str:
    """
    Like the above but returns Claude's raw TEXT answer (not JSON) plus
    the list of source URLs it cited. Used where the caller wants prose
    findings + citations rather than a strict schema.

    Returns (text, [urls]).
    """
    effective_max = max(max_tokens, 3000)
    tool = {**WEB_SEARCH_TOOL, "max_uses": max_uses}
    try:
        resp = _create(system, user_content, effective_max, temperature, tools=[tool])
    except Exception as e:
        if _DEBUG:
            print(f"      [WEBSEARCH DEBUG] call failed: {e}", flush=True)
        return "", []

    text = _text_of(resp)
    # collect cited URLs from citation objects on text blocks
    urls = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            for cit in (getattr(block, "citations", None) or []):
                u = getattr(cit, "url", None)
                if u and u not in urls:
                    urls.append(u)
    return text, urls