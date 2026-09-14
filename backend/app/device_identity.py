"""Device identity extraction - architecture-document.md §3 step 3b: runs
independently of whether the vendor's security-relevant syntax resolves, so
even a wholly unknown vendor's report still has device info in it.

Honest limitation, stated up front rather than discovered later: a plain
`show running-config` style export very often does NOT contain a serial
number at all - that typically comes from `show version` / `show
inventory`, a different command entirely. Fields we can't find are None, not
guessed or fabricated.
"""
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional


@dataclass
class DeviceIdentity:
    hostname: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    serial_number: Optional[str] = None


def extract(raw_text: str, fmt: str) -> DeviceIdentity:
    if fmt == "json":
        return _extract_json(raw_text)
    if fmt == "xml":
        return _extract_xml(raw_text)
    return _extract_cli(raw_text)


def _extract_cli(raw_text: str) -> DeviceIdentity:
    hostname = _search(r"^hostname\s+(\S+)", raw_text)
    firmware_version = _search(r"^version\s+(\S+)", raw_text)
    # Best-effort only - real running-config exports rarely carry these;
    # covers the rare case a comment/banner does (e.g. "! Model: WS-C3560").
    model = _search(r"^!\s*Model:\s*(\S+)", raw_text, extra=re.IGNORECASE)
    serial = _search(r"^!\s*Serial(?:\s*Number)?:\s*(\S+)", raw_text, extra=re.IGNORECASE)
    return DeviceIdentity(hostname=hostname, model=model, firmware_version=firmware_version, serial_number=serial)


def _search(pattern: str, text: str, extra: int = 0) -> Optional[str]:
    m = re.search(pattern, text, re.MULTILINE | extra)
    return m.group(1) if m else None


def _extract_json(raw_text: str) -> DeviceIdentity:
    try:
        obj = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError):
        return DeviceIdentity()
    meta = (obj.get("DEVICE_METADATA") or {}).get("localhost") or {}
    return DeviceIdentity(
        hostname=meta.get("hostname"),
        # SONiC config_db.json commonly carries hwsku/platform on
        # DEVICE_METADATA - the closest thing to a "model" this file format
        # actually contains; still no serial number (that's a runtime/EEPROM
        # concept, not part of config_db.json).
        model=meta.get("hwsku") or meta.get("platform"),
        firmware_version=None,
        serial_number=None,
    )


def _extract_xml(raw_text: str) -> DeviceIdentity:
    try:
        root = ET.fromstring(raw_text)
    except ET.ParseError:
        return DeviceIdentity()
    system = root.find("system")
    hostname = system.findtext("hostname") if system is not None else None
    version = root.findtext("version")
    return DeviceIdentity(hostname=hostname, firmware_version=version, model=None, serial_number=None)
