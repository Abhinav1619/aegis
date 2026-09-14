"""Canonical Security Baseline Model - starter field set, organized around
NIST 800-53 control families per architecture-document.md §3 step 5. This
grows as rule authoring (cybersecurity teammate) covers more controls - this
is the Day-1 minimum needed to get the three demo devices' chosen controls
end-to-end.

Each field carries a human-readable label + description alongside its code.
This exists because the review-queue UI is meant to be usable by someone who
doesn't already know NIST control-family naming - the label/description are
what render there; the code (e.g. "IA.ssh_version") stays visible as
secondary detail for anyone who does want the technical mapping (an auditor,
or the rule engine itself).
"""

# family prefix -> meaning, for reference / for the technical-detail view
CONTROL_FAMILIES = {
    "AC": "Access Control",
    "AU": "Audit and Accountability",
    "IA": "Identification and Authentication",
    "SC": "System and Communications Protection",
    "CM": "Configuration Management",
}

FIELD_METADATA = {
    "AC.telnet_enabled": {
        "type": "scalar",
        "label": "Telnet access",
        "description": "Whether unencrypted Telnet remote-access is enabled on this device.",
    },
    "IA.ssh_version": {
        "type": "scalar",
        "label": "SSH version",
        "description": "Which version of SSH is required for encrypted remote access (should be 2, not 1).",
    },
    "IA.password_encryption_enabled": {
        "type": "scalar",
        "label": "Password encryption",
        "description": "Whether stored passwords/secrets in the config are encrypted rather than plain text.",
    },
    "AU.logging_enabled": {
        "type": "scalar",
        "label": "Logging enabled",
        "description": "Whether administrative activity logging is turned on.",
    },
    "AU.logging_host": {
        "type": "list",
        "label": "Remote logging server",
        "description": "Address(es) of the remote server(s) logs are sent to, for audit trail purposes.",
    },
    "AC.acl_rules": {
        "type": "list",
        "label": "Access control rules",
        "description": "Firewall/ACL rules controlling what traffic is allowed or denied.",
    },
    "SC.enabled_ciphers": {
        "type": "list",
        "label": "Allowed encryption ciphers",
        "description": "Which cryptographic cipher suites this device is configured to accept.",
    },
}

# Back-compat: field -> value type, used by resolve.py / llm_client.py.
CANONICAL_FIELDS = {field: meta["type"] for field, meta in FIELD_METADATA.items()}


def is_valid_field(name: str) -> bool:
    return name in FIELD_METADATA


def label_for(name: str) -> str:
    meta = FIELD_METADATA.get(name)
    return meta["label"] if meta else name
