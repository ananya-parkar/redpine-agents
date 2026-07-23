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

    PROMPT CACHING (this version):
    `system` is now sent as a content-block list with a `cache_control`
    breakpoint instead of a plain string. Every call site in this file
    (batch_classify's BATCH_PROMPT, deep_analyze's DEEP_PROMPT,
    verify_current_status's VERIFY_PROMPT, rescue's RESCUE_PROMPT,
    stakeholder enrichment's EXTRACT_PROMPT) sends the SAME system text
    repeatedly across many venues/leads within one run — previously each
    of those calls paid full input-token price for that multi-hundred-
    to-multi-thousand-token prompt every single time.

    With cache_control marked, Anthropic caches everything up to that
    block for 5 minutes: the FIRST call in a series pays a ~25% premium
    to write the cache, every subsequent call within the window reads it
    back at ~10% of normal input-token cost. Since batch_classify runs
    15-20+ times per run and deep_analyze/verify_current_status/
    stakeholder-enrichment each run dozens of times with an unchanged
    system prompt, this amortizes to a large net reduction in input-
    token spend over a full run.

    CAVEATS (read before assuming this "just works" everywhere):
      - Minimum cacheable length: Claude requires the cached prefix to
        be at least ~1024 tokens (Sonnet-class models) to actually take
        effect. Below that, cache_control is silently ignored — no
        error, no benefit, but also no harm. All the prompts in this
        codebase are comfortably above that threshold.
      - The tuning_block dynamic text (from tuning_prompt.py) is
        appended to `system` by the CALLER (reasoning_agent.py /
        stakeholder_enrichment.py) before it ever reaches this function
        — so from here it's just part of one opaque `system` string.
        That's fine: tuning_block is built ONCE per run_reasoning() call
        and stays identical for every batch_classify/deep_analyze call
        within that run, so the combined string still matches call-to-
        call and still caches correctly. It only changes between runs
        (when a new tuning trigger gets logged), which correctly busts
        the cache — that's the desired behavior, not a bug.
      - Different call TYPES (BATCH_PROMPT vs DEEP_PROMPT vs
        VERIFY_PROMPT etc.) never share a cache entry with each other —
        each has its own distinct system text, so each builds its own
        cache lazily on first use within a run. That's expected; caching
        only helps repeated calls of the SAME prompt type, which is
        exactly the majority of this pipeline's call volume.
      - A cache entry lives 5 minutes from last use. If a stage's calls
        are spaced further apart than that (e.g. a very slow run with
        long delays), some calls will miss the cache and pay full price
        again — still no worse than before caching existed.
      - Tool definitions (web_search_20250305 with a given max_uses) are
        part of the cached prefix too. Calls with a DIFFERENT max_uses
        (Stage 3 verify=3 vs stakeholder enrichment=4, for example) do
        not share a cache entry — but calls of the SAME type in the same
        run always use the same max_uses, so this doesn't reduce the
        benefit in practice.
    """
    global _SUPPORTS_TEMPERATURE
    kwargs = dict(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=[{
            "type": "text",
            "text": system,
            "cache_control": {"type": "ephemeral"},
        }],
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