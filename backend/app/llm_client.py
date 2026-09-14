"""Tier-2 LLM classification - Groq primary, Gemini fallback
(architecture-document.md §3 step 4 / §2).

Every response is schema-validated before it's trusted (the Sept-12
hardening): malformed JSON, an out-of-range confidence, or a
`canonical_field` the model invented rather than one that's actually in our
enum are all treated identically to "the LLM is unavailable" by the caller
(resolve.py) - routed to Tier 3, never crashed on, never silently accepted.

Missing API keys are just one more reason this returns None rather than a
special case - the graceful-degradation design already covers "Tier 2 isn't
available right now" regardless of why.
"""
import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

# Import order matters here (Langfuse skill's own "Common Mistakes" list):
# env vars must be loaded before the Langfuse client reads them.
load_dotenv()

from langfuse import get_client  # noqa: E402

from .canonical_schema import CANONICAL_FIELDS, is_valid_field  # noqa: E402

langfuse = get_client()

PROMPT_VERSION = "v1-2026-09-13"

# Model choices as of 2026-09-13 - both Llama-3.3-70B-versatile (Groq) and
# Gemini 2.0 Flash were decommissioned earlier this year (Groq: announced
# June 2026, off free/dev tier by August; Gemini 2.0 Flash: retired June 1
# 2026). Verified current via web search before wiring these in - see
# architecture-document.md §2 changelog note. Re-check before the grand
# finale: Gemini 2.5 Flash itself is slated to retire ~Oct 16 2026.
GROQ_MODEL = "qwen/qwen3.8-27b"
GEMINI_MODEL = "gemini-2.5-flash"
# openai/gpt-oss-120b is also live on this account but is a reasoning model -
# it spends tokens on hidden reasoning before the answer, so it needs a much
# larger max_tokens budget (1500+, empirically) and is slower per call.
# qwen3.8-27b returned clean, correctly-enumerated JSON in <0.5s at
# max_tokens=300 with no thinking-token overhead - better fit for a
# free-tier-rate-limit-constrained live classifier. Re-benchmark if either
# model's behavior changes.

def _build_system_prompt() -> str:
    # Built from the actual CANONICAL_FIELDS enum, not hand-copied, so this
    # can never silently drift out of sync with what the validator accepts -
    # a live bug (Gemini invented "Logging and Monitoring" as a field name)
    # showed this needs to be explicit, not implied.
    field_list = ", ".join(CANONICAL_FIELDS.keys())
    return (
        "You classify a single line or config unit from a network device "
        "configuration file into ONE canonical security field. Only ever "
        "respond with a single JSON object, no other text, matching exactly: "
        '{"canonical_field": string, "value": string|boolean|number, '
        '"confidence": number between 0 and 1, "reasoning": string}. '
        f"canonical_field MUST be exactly one of these existing values: "
        f"{field_list}. Never invent a new field name. If the unit does not "
        'map to any of these, set canonical_field to "UNKNOWN" and '
        "confidence to 0."
    )


_SYSTEM_PROMPT = _build_system_prompt()


@dataclass
class LLMCandidate:
    canonical_field: str
    value: object
    confidence: float
    reasoning: str
    provider: str
    model_version: str
    prompt_version: str = PROMPT_VERSION
    # Persisted so a human confirm/reject decision made LATER (in the review
    # queue, a separate request entirely) can attach as a score on THIS exact
    # trace - the mechanism architecture-document.md §5 describes.
    langfuse_trace_id: Optional[str] = None
    langfuse_observation_id: Optional[str] = None


def _extract_json(text: str) -> Optional[dict]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None


def _validate(raw: dict) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    field = raw.get("canonical_field")
    conf = raw.get("confidence")
    if field is None or "value" not in raw:
        return None
    if field != "UNKNOWN" and not is_valid_field(field):
        return None  # hallucinated field name - reject, don't trust
    if not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
        return None
    return raw


def _user_prompt(unit_text: str, context: str, similar_kb_entries: list) -> str:
    hints = ""
    if similar_kb_entries:
        hints = "\nSimilar previously-confirmed patterns (for context only):\n" + "\n".join(
            f"- {e['syntax_pattern']!r} -> {e['canonical_field']}" for e in similar_kb_entries[:5]
        )
    return f"Config unit to classify:\n{unit_text}\n\nSurrounding context:\n{context or '(none)'}{hints}"


def _try_groq(unit_text: str, context: str, similar_kb_entries: list) -> Optional[LLMCandidate]:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    user_prompt = _user_prompt(unit_text, context, similar_kb_entries)
    try:
        with langfuse.start_as_current_observation(
            as_type="generation",
            name="tier2-classify-groq",
            model=GROQ_MODEL,
            input={"unit": unit_text, "context": context},
            metadata={"prompt_version": PROMPT_VERSION, "feature": "tier2-classification"},
        ) as gen:
            from groq import Groq
            client = Groq(api_key=api_key)
            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                max_tokens=300,
            )
            raw_text = resp.choices[0].message.content
            parsed = _validate(_extract_json(raw_text) or {})
            usage = resp.usage
            gen.update(
                output=parsed if parsed is not None else {"raw": raw_text, "validation": "rejected"},
                usage_details={
                    "input": usage.prompt_tokens,
                    "output": usage.completion_tokens,
                    "total": usage.total_tokens,
                } if usage else None,
            )
            trace_id = langfuse.get_current_trace_id()
            observation_id = langfuse.get_current_observation_id()
            if parsed is None:
                return None
            return LLMCandidate(
                canonical_field=parsed["canonical_field"],
                value=parsed["value"],
                confidence=float(parsed["confidence"]),
                reasoning=parsed.get("reasoning", ""),
                provider="groq",
                model_version=GROQ_MODEL,
                langfuse_trace_id=trace_id,
                langfuse_observation_id=observation_id,
            )
    except Exception:
        return None
    finally:
        langfuse.flush()  # short-lived request handler, not a long process - flush explicitly


def _try_gemini(unit_text: str, context: str, similar_kb_entries: list) -> Optional[LLMCandidate]:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    user_prompt = _user_prompt(unit_text, context, similar_kb_entries)
    try:
        with langfuse.start_as_current_observation(
            as_type="generation",
            name="tier2-classify-gemini",
            model=GEMINI_MODEL,
            input={"unit": unit_text, "context": context},
            metadata={"prompt_version": PROMPT_VERSION, "feature": "tier2-classification", "fallback": True},
        ) as gen:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=_SYSTEM_PROMPT)
            resp = model.generate_content(user_prompt)
            parsed = _validate(_extract_json(resp.text) or {})
            usage_meta = getattr(resp, "usage_metadata", None)
            gen.update(
                output=parsed if parsed is not None else {"raw": resp.text, "validation": "rejected"},
                usage_details={
                    "input": usage_meta.prompt_token_count,
                    "output": usage_meta.candidates_token_count,
                    "total": usage_meta.total_token_count,
                } if usage_meta else None,
            )
            trace_id = langfuse.get_current_trace_id()
            observation_id = langfuse.get_current_observation_id()
            if parsed is None:
                return None
            return LLMCandidate(
                canonical_field=parsed["canonical_field"],
                value=parsed["value"],
                confidence=float(parsed["confidence"]),
                reasoning=parsed.get("reasoning", ""),
                provider="gemini",
                model_version=GEMINI_MODEL,
                langfuse_trace_id=trace_id,
                langfuse_observation_id=observation_id,
            )
    except Exception:
        return None
    finally:
        langfuse.flush()


def classify(unit_text: str, context: str = "", similar_kb_entries: list = None) -> Optional[LLMCandidate]:
    """Returns None if both providers are unavailable/invalid - the caller
    (resolve.py) treats that identically to any other Tier-3 routing reason."""
    similar_kb_entries = similar_kb_entries or []
    result = _try_groq(unit_text, context, similar_kb_entries)
    if result is not None:
        return result
    return _try_gemini(unit_text, context, similar_kb_entries)
