"""Splits a raw config into resolve_unit-sized pieces, depending on the
format fingerprint.py detected. This is the pre-processor from
architecture-document.md §3 step 3c: JSON/XML get flattened into path-like
pseudo-lines so the SAME resolve_unit pipeline applies uniformly - not a
second parser.

Cross-reference preservation (§3 step 3.5) is explicitly deferred this week
(architecture-document.md §7) - this flattening does NOT preserve references
between units (e.g. an AAA method-list name, or one security-group rule
pointing at another). Demo control sets are chosen to not need it.
"""
import json
import xml.etree.ElementTree as ET


def split_into_units(raw_text: str, fmt: str) -> list:
    if fmt == "json":
        return _flatten_json(json.loads(raw_text))
    if fmt == "xml":
        return _flatten_xml(raw_text)
    return _split_cli(raw_text)


def _split_cli(raw_text: str) -> list:
    units = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("!"):
            continue
        units.append(stripped)
    return units


def _flatten_json(obj, prefix: str = "") -> list:
    units = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            child_units = _flatten_json(v, path)
            if not child_units:
                # v is {} or [] - the key's existence IS the data point.
                # SONiC's config_db.json does this constantly (e.g. a syslog
                # server table keyed by IP with an empty settings body) -
                # without this, that fact would silently vanish instead of
                # becoming a resolvable unit.
                units.append(f"{path}=<present>")
            else:
                units.extend(child_units)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            units.extend(_flatten_json(v, f"{prefix}[{i}]"))
    else:
        units.append(f"{prefix}={obj}")
    return units


def _flatten_xml(raw_text: str) -> list:
    """Sibling elements sharing a tag (e.g. two <rule> entries under one
    <filter>) get an index suffix, same convention as JSON list flattening -
    without it, both rules' children would silently collide onto the exact
    same path (both "filter.rule.type") and become indistinguishable. Found
    via real testing against a pfSense-style two-rule filter block, not
    theoretical."""
    units = []
    try:
        root = ET.fromstring(raw_text)
    except ET.ParseError:
        return units

    def walk(elem, path):
        text = (elem.text or "").strip()
        if text and len(list(elem)) == 0:
            units.append(f"{path}={text}")

        seen: dict = {}
        for child in elem:
            same_tag_count = sum(1 for c in elem if c.tag == child.tag)
            if same_tag_count > 1:
                idx = seen.get(child.tag, 0)
                seen[child.tag] = idx + 1
                child_path = f"{path}.{child.tag}[{idx}]"
            else:
                child_path = f"{path}.{child.tag}"
            walk(child, child_path)

    walk(root, root.tag)
    return units
