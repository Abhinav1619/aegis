// Plain-language copy for internal engineering terms. The underlying
// concepts (tiers, redaction, provenance) stay real and technically precise
// in the API/data model - this file exists so the UI can lead with language
// a non-specialist can say out loud, while the technical terms stay
// available as secondary/expandable detail for anyone (an auditor, a
// technical judge) who wants them.

// Shown per-finding, so a viewer can tell "instantly recognized" apart from
// "AI guessed" apart from "a person confirmed this" - the thing an auditor
// needs to weigh how much to trust a given PASS (architecture-document.md §5).
export const CONFIDENCE_TIER_LABELS: Record<string, string> = {
  tier1: "Instantly recognized",
  tier2_accepted: "AI-classified",
  tier3_human_confirmed: "Human-confirmed",
};

export const REDACTION_TYPE_LABELS: Record<string, string> = {
  TYPE7_PASSWORD: "an encoded password",
  ENABLE_SECRET_HASH: "a hashed admin password",
  SNMP_COMMUNITY: "an SNMP community string",
  PRE_SHARED_KEY: "a VPN/IPsec pre-shared key",
  AAA_KEY: "a RADIUS/TACACS+ shared secret",
  GENERIC_SECRET_FIELD: "a secret-looking value",
};
