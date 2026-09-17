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
# `\S+` (any non-whitespace) is the wrong boundary for a value-capturing
# group here: in XML/JSON-embedded values, the value is often immediately
# followed by a structural delimiter with NO separating whitespace (e.g.
# `password=CANARY_NUTPASS</upsd_users></config></nut>`, `secret="x"`).
# `\S+` greedily swallows those delimiters as part of the "secret," and
# replacing that whole match deletes real closing tags/quotes from the file -
# found via a real pfSense config where this silently destroyed three closing
# tags and produced a file that no longer parses as XML at all (0 units, no
# error surfaced). `[^\s<>"']+` stops at whitespace or any of the delimiter
# characters that matter across CLI/XML/JSON, so only the actual value is
# captured and structure around it survives untouched.
_VALUE = r"[^\s<>\"']+"

_RULES = [
    ("TYPE7_PASSWORD", re.compile(r"\bpassword 7 ([0-9A-Fa-f]+)\b"), None, 1),
    # Was hardcoded to type "5" only - types 8 and 9 (the ones CIS-1.4.1
    # actually wants: PBKDF2/SHA-256 and scrypt respectively) matched
    # nothing and their hashes went completely unredacted to the LLM/review
    # queue. Broadened to any type digit; the digit itself stays visible
    # (it's what AC.privileged_password_type needs to read) while only the
    # hash (group 2) is redacted.
    ("ENABLE_SECRET_HASH", re.compile(r"\benable secret (\d+) (" + _VALUE + r")"), None, 2),
    # "public"/"private" are the well-known CIS-flagged DEFAULT community
    # strings (CIS-1.5.2/1.5.3) - not real secrets, so there's nothing to
    # protect by hiding them, and doing so was actively breaking those two
    # checks: once redacted to a generic placeholder, the compliance check
    # can never again tell a default string apart from a real custom one.
    # Any other community string still gets redacted normally.
    ("SNMP_COMMUNITY", re.compile(r"\bsnmp-server community (" + _VALUE + r")"), {"public", "private"}, 1),
    ("PRE_SHARED_KEY", re.compile(r"\bpre-shared-key\s+(" + _VALUE + r")", re.IGNORECASE), None, 1),
    ("AAA_KEY", re.compile(r"\b(?:tacacs-server|radius-server)\s+key\s+(" + _VALUE + r")", re.IGNORECASE), None, 1),
    # Generic fallback for flattened JSON-style "key/secret/password: value" -
    # deliberately broad, applied last so specific rules above take priority.
    ("GENERIC_SECRET_FIELD", re.compile(r"\b(?:secret|password|psk|shared_key)\s*[:=]\s*(" + _VALUE + r")", re.IGNORECASE), None, 1),
    # XML *elements* use a completely different separator than the rule
    # above assumes ("<password>x</password>", not "password=x" or
    # "password: x") - found live on a real pfSense config:
    # <ppps><ppp><password>CANARY_PPPOEPASS</password></ppp></ppps> matched
    # NOTHING above, even though "password" is exactly the keyword the rule
    # is supposed to catch, because the character after it is ">", not
    # ":"/"=". Same keyword vocabulary, same "don't try to catch every
    # possible tag name" scope (a tag like <passphrase> or <ipsecpsk> is
    # still a disclosed gap, same as before) - this only closes the
    # separator gap, not the keyword-coverage one.
    ("XML_ELEMENT_SECRET",
     re.compile(r"<(\w*(?:secret|password|psk|shared_key)\w*)>([^<]+)</\1>", re.IGNORECASE),
     None, 2),
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
            # Square brackets, not angle brackets: this placeholder gets
            # inserted into whatever format the raw file is (CLI text, JSON
            # string values, or XML text content) - redaction runs before
            # fingerprinting even knows the format. A literal "<" here reads
            # as the start of a new element to an XML parser (found via a
            # real "unbound prefix" ParseError on a real pfSense config with
            # a redacted secret - the whole file silently produced 0 units,
            # no error surfaced). "[...]" has no special meaning in any of
            # the three formats this pipeline handles.
            placeholder = f"[REDACTED:{type_name}]"
            if len(secret) >= 2 and secret[0] == secret[-1] and secret[0] in ("'", '"'):
                # `\S+` greedily swallowed a surrounding quote pair too (an
                # XML/JSON-style quoted attribute value, e.g. secret="x") -
                # replacing the whole quoted token with an unquoted
                # placeholder breaks XML attribute syntax (found via the same
                # real pfSense config: secret="..." became secret=[REDACTED:
                # ...], invalid). Keep the same quote marks around it.
                placeholder = f"{secret[0]}{placeholder}{secret[0]}"
            return m.group(0).replace(secret, placeholder)

        text = pattern.sub(_sub, text)
        if redacted_count:
            hits.append({"type": type_name, "count": redacted_count})
    return RedactionResult(text=text, hits=hits)
