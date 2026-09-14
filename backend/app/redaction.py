"""Redaction pass - regex-only for this build (architecture-document.md §7:
entropy-based fallback is deferred, disclosed as a residual risk in §10).

Runs BEFORE anything reaches an LLM call or a review-queue UI. Every secret
value is replaced with a typed placeholder, never just deleted, so downstream
code (and a human reviewer) can still see THAT something was there without
seeing WHAT it was.

Deliberately includes one known-gap demo hook (see `DEMO_UNCAUGHT_EXAMPLE`
below) - architecture-document.md §7 asks the demo to show a failure case,
not just the happy path.
"""
import re
from dataclasses import dataclass, field


@dataclass
class RedactionResult:
    text: str
    hits: list = field(default_factory=list)  # [{"type": ..., "count": ...}]


# Each rule: (type_name, compiled regex with the secret value in group 1)
_RULES = [
    ("TYPE7_PASSWORD", re.compile(r"\bpassword 7 ([0-9A-Fa-f]+)\b")),
    ("ENABLE_SECRET_HASH", re.compile(r"\benable secret 5 (\S+)")),
    ("SNMP_COMMUNITY", re.compile(r"\bsnmp-server community (\S+)")),
    ("PRE_SHARED_KEY", re.compile(r"\bpre-shared-key\s+(\S+)", re.IGNORECASE)),
    ("AAA_KEY", re.compile(r"\b(?:tacacs-server|radius-server)\s+key\s+(\S+)", re.IGNORECASE)),
    # Generic fallback for flattened JSON-style "key/secret/password: value" -
    # deliberately broad, applied last so specific rules above take priority.
    ("GENERIC_SECRET_FIELD", re.compile(r"\b(?:secret|password|psk|shared_key)\s*[:=]\s*(\S+)", re.IGNORECASE)),
]

# A secret shape neither the regex rules above nor (in this build) an entropy
# check would catch: a vendor-proprietary obfuscated blob with no recognizable
# keyword next to it. Used deliberately in rehearsal (architecture-document.md
# §7/§11) to show the gap honestly rather than only the happy path.
DEMO_UNCAUGHT_EXAMPLE = "set system root-authentication encrypted-password \"$6$abcXYZ123$notReallyRedacted\""


def redact(text: str) -> RedactionResult:
    hits = []
    for type_name, pattern in _RULES:
        def _sub(m, type_name=type_name):
            return m.group(0).replace(m.group(1), f"<REDACTED:{type_name}>")

        text, count = pattern.subn(_sub, text)
        if count:
            hits.append({"type": type_name, "count": count})
    return RedactionResult(text=text, hits=hits)
