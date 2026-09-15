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


# Each rule: (type_name, compiled regex, optional case-insensitive set of
# captured values that should NOT be redacted for this rule even though they
# matched, which capture group holds the actual secret to redact (default 1
# - only ENABLE_SECRET_HASH differs, see below)).
_RULES = [
    ("TYPE7_PASSWORD", re.compile(r"\bpassword 7 ([0-9A-Fa-f]+)\b"), None, 1),
    # Was hardcoded to type "5" only - types 8 and 9 (the ones CIS-1.4.1
    # actually wants: PBKDF2/SHA-256 and scrypt respectively) matched
    # nothing and their hashes went completely unredacted to the LLM/review
    # queue. Broadened to any type digit; the digit itself stays visible
    # (it's what AC.privileged_password_type needs to read) while only the
    # hash (group 2) is redacted.
    ("ENABLE_SECRET_HASH", re.compile(r"\benable secret (\d+) (\S+)"), None, 2),
    # "public"/"private" are the well-known CIS-flagged DEFAULT community
    # strings (CIS-1.5.2/1.5.3) - not real secrets, so there's nothing to
    # protect by hiding them, and doing so was actively breaking those two
    # checks: once redacted to a generic placeholder, the compliance check
    # can never again tell a default string apart from a real custom one.
    # Any other community string still gets redacted normally.
    ("SNMP_COMMUNITY", re.compile(r"\bsnmp-server community (\S+)"), {"public", "private"}, 1),
    ("PRE_SHARED_KEY", re.compile(r"\bpre-shared-key\s+(\S+)", re.IGNORECASE), None, 1),
    ("AAA_KEY", re.compile(r"\b(?:tacacs-server|radius-server)\s+key\s+(\S+)", re.IGNORECASE), None, 1),
    # Generic fallback for flattened JSON-style "key/secret/password: value" -
    # deliberately broad, applied last so specific rules above take priority.
    ("GENERIC_SECRET_FIELD", re.compile(r"\b(?:secret|password|psk|shared_key)\s*[:=]\s*(\S+)", re.IGNORECASE), None, 1),
]

# A secret shape neither the regex rules above nor (in this build) an entropy
# check would catch: a vendor-proprietary obfuscated blob with no recognizable
# keyword next to it. Used deliberately in rehearsal (architecture-document.md
# §7/§11) to show the gap honestly rather than only the happy path.
DEMO_UNCAUGHT_EXAMPLE = "set system root-authentication encrypted-password \"$6$abcXYZ123$notReallyRedacted\""


def redact(text: str) -> RedactionResult:
    hits = []
    for type_name, pattern, keep_values, value_group in _RULES:
        redacted_count = 0

        def _sub(m, type_name=type_name, keep_values=keep_values, value_group=value_group):
            nonlocal redacted_count
            secret = m.group(value_group)
            if keep_values and secret.lower() in keep_values:
                return m.group(0)  # matched, but a known-safe value - leave as-is
            redacted_count += 1
            return m.group(0).replace(secret, f"<REDACTED:{type_name}>")

        text = pattern.sub(_sub, text)
        if redacted_count:
            hits.append({"type": type_name, "count": redacted_count})
    return RedactionResult(text=text, hits=hits)
