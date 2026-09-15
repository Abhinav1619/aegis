"""Fingerprinting - signature/banner match only for this build
(architecture-document.md §7: no embedding-based file-level fallback yet).

Also does the format split (cli text vs JSON vs XML) that step 3c
(structured-config normalizer) needs downstream - this is the one place in
the pipeline that has to look at the raw shape of the file before anything
else can run.
"""
import json
import re

_SONIC_TABLE_MARKERS = {"PORT", "VLAN", "ACL_RULE", "DEVICE_METADATA", "MGMT_INTERFACE"}


def fingerprint(raw_text: str) -> dict:
    """Returns {vendor, version_family, format, confidence}.
    format is one of "json" | "xml" | "cli" - tells the caller how to split
    the file into units for resolve_unit (§3, step 4)."""
    stripped = raw_text.strip()

    # SONiC config_db.json - structured JSON, identified by its table keys.
    try:
        obj = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        obj = None
    if isinstance(obj, dict):
        if _SONIC_TABLE_MARKERS & set(obj.keys()):
            return {"vendor": "sonic", "version_family": "sonic", "format": "json", "confidence": "high"}
        return {"vendor": "unknown_json", "version_family": None, "format": "json", "confidence": "low"}

    # pfSense config.xml - gated on the actual <pfsense> root tag, not just
    # "this is XML" (a bug: any other vendor's XML export, e.g. Juniper's
    # XML API output, was getting labeled "pfsense" at high confidence -
    # wrong vendor identification AND wrong (pfSense) remediation text
    # shown for a non-pfSense device).
    head = stripped[:2000]
    if "<pfsense>" in head:
        return {"vendor": "pfsense", "version_family": "netgate", "format": "xml", "confidence": "high"}
    if stripped.startswith("<?xml"):
        return {"vendor": "unknown_xml", "version_family": None, "format": "xml", "confidence": "low"}

    # Cisco IOS - version banner + vty lines is a strong signal together;
    # either alone is a weaker (medium-confidence) signal.
    has_version_banner = bool(re.search(r"^version \d+\.\d+", stripped, re.MULTILINE))
    has_vty = "line vty" in stripped
    if has_version_banner and has_vty:
        return {"vendor": "cisco_ios", "version_family": "ios", "format": "cli", "confidence": "high"}
    if has_version_banner or has_vty:
        return {"vendor": "cisco_ios", "version_family": "ios", "format": "cli", "confidence": "medium"}

    # No signature matched - a partial/truncated config with no clean banner.
    # Per architecture-document.md §3 step 3a, this degrades gracefully: every
    # unit just routes through Tier 2/3 more often, it doesn't fail outright.
    return {"vendor": "unknown", "version_family": None, "format": "cli", "confidence": "low"}
