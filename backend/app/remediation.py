"""Remediation - KB-template lookup ONLY for this build.

LLM-drafted remediation is deliberately cut for the demo (architecture-
document.md §7): it's the highest-risk, most prompt-injection-exposed
component in the whole system, and rushing it under time pressure is a worse
look than not shipping it yet. If no template exists for a (vendor, rule_id)
pair, the honest answer is "no remediation available", not an improvised one.
"""
from dataclasses import dataclass
from typing import Optional

# (vendor, rule_id) -> fix command(s). Starter set for the seeded demo rules;
# grows as the cybersecurity teammate authors more rule YAML.
TEMPLATES: dict[tuple[str, str], str] = {
    ("cisco_ios", "CIS-CISCO-3.1"): "line vty 0 4\n transport input ssh",
    ("cisco_ios", "CIS-CISCO-3.2"): "ip ssh version 2",
    ("cisco_ios", "CIS-CISCO-3.3"): "service password-encryption",
    ("cisco_ios", "CIS-CISCO-4.1"): "logging host <your-syslog-server-ip>",
    ("cisco_ios", "CIS-CISCO-3.4"): (
        "access-list 101 deny tcp any any eq 23\n"
        "access-list 101 permit ip any any\n"
        "! ensure the deny line is ABOVE any broader permit line - order matters"
    ),
}


@dataclass
class Remediation:
    text: str
    source: str  # "template" - the only value this build ever produces


def get_remediation(vendor: str, rule_id: str) -> Optional[Remediation]:
    text = TEMPLATES.get((vendor, rule_id))
    if text is None:
        return None
    return Remediation(text=text, source="template")
