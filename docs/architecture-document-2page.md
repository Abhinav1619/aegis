# Sentra — Architecture Document

**AI-Augmented, Vendor-Agnostic Network Compliance Engine**

*(Condensed to the 2-page submission limit. The full engineering reference —
data model, threat model, evaluation methodology, MVP scope — lives in
`architecture-document.md` in this same repository.)*

## The problem, and the one design decision that answers it

Network devices from dozens of vendors must each be checked against CIS,
NIST 800-53, DISA STIG, and ISO 27001 — but every vendor's CLI syntax is
different, and a hardcoded parser per vendor breaks the moment a new vendor,
firmware version, or device class shows up. **Sentra's core design decision:
there is exactly one parser, and it is a lookup against one knowledge base
(KB).** A "known vendor" is not a different code path from an "unknown
vendor" — it's a cache hit against the same KB that unknown-vendor handling
writes into. Adding a vendor is new database rows, never new code. This is
what makes "learns a new vendor without backend redeployment" a literal,
verifiable fact about the system rather than a marketing claim.

## Pipeline

A config (CLI text or structured JSON — AWS/Azure/SONiC) is redacted of
secret-shaped values before anything leaves the trust boundary, fingerprinted
for vendor/version, and every config unit is resolved through a **confidence-
tiered pipeline**: Tier 1 is a direct KB pattern/embedding match (free,
instant, deterministic — this *is* what "known vendor" means); Tier 2, on
lower confidence, has an LLM (Groq primary, Gemini fallback) propose a
mapping with its reasoning, schema-validated against our canonical fields —
any malformed or hallucinated response routes to Tier 3 automatically, never
silently accepted; Tier 3 is a human reviewer, whose confirmation is written
back into the KB as a new, versioned, append-only entry. That write-back
*is* the "learning" — RAG-style knowledge growth, not model fine-tuning, which
is both the right scope for a no-GPU build and the literal mechanism that
satisfies "no redeployment."

Resolved fields populate a canonical schema organized around **NIST 800-53
control families**, so CIS/STIG/ISO controls map onto one shared backbone
instead of four independent rule silos. A deterministic rule engine (no LLM
in the verdict path, by design) evaluates the schema with six generic
predicate types — including an **ordered/first-match evaluator** for ACLs
and security-group rules, because real firewall rules are evaluated in
sequence; a naive membership check would score a config as safe even when an
earlier permissive rule makes a later deny rule dead code. Every finding is
`PASS`, `FAIL`, or `NOT_EVALUATED` — a control whose required field never
resolved is never silently marked compliant. Remediation is looked up from a
KB template first; any LLM-drafted fallback is always human-gated before
being shown or persisted, since a wrong CLI command applied to a live device
is the single highest-consequence failure mode in the system. Output is a
per-device PDF with severity, remediation, and **evidence** — the exact
source line and KB entry that produced each finding, for a defensible audit
trail — plus a batch rollup for bulk uploads.

## What makes this defensible, not just functional

- **Fail-closed by construction**, not by convention: `NOT_EVALUATED` is a
  first-class verdict state, so an unparsed control can never present as a
  false PASS — the dangerous failure mode for a compliance tool.
- **Three separate ground truths, not one**: parsing accuracy is measured
  against a hand-labeled golden set from vendor documentation; compliance
  correctness is measured against the standards' own text (and, where DISA/
  NIST publish machine-readable SCAP/OVAL references, against those
  directly); both are re-measured on a schedule, not asserted once. The
  headline metric is **false-negative rate**, not aggregate accuracy.
- **Redaction before inference**: secret-shaped values (reversible Cisco
  type-7 passwords, SNMP strings, PSKs) never reach an LLM call. Free-tier
  Groq/Gemini is an explicit hackathon stand-in; a real deployment runs a
  self-hosted model inside the customer's own perimeter — the provider is an
  interface choice, not hardcoded.
- **Observability as a designed layer, not an afterthought**: Langfuse traces
  every LLM call and attaches the human review decision as a score on that
  exact trace; pipeline-level metrics (tier distribution per vendor, parse
  coverage by severity, review-queue age) make "is the system still learning
  as designed" a number, not an assumption.
- **Governance with teeth**: KB entries are append-only and versioned, not
  mutated in place; a fixed percentage of auto-applied (Tier 1) mappings are
  periodically re-surfaced for human spot-check, bounding how long a bad
  mapping can go undetected.

## Tech stack

FastAPI (async) · Next.js + Tailwind · SQLite for the current build (Postgres
is the stated production choice) · brute-force cosine similarity for the
current build (Chroma/pgvector at production scale) · `sentence-transformers`
embeddings · Groq (`qwen/qwen3.8-27b`) + Gemini (`gemini-2.5-flash`) · ReportLab
for PDF generation (pure Python, no system dependencies) · Langfuse for LLM
observability.

## Honestly out of scope for this build stage

Live device polling (Netmiko), full RBAC enforcement and multi-tenant
isolation beyond a schema field, LLM-drafted remediation, the cross-reference
linking stage for controls split across non-adjacent lines by name (e.g.
Cisco AAA method-lists), and entropy-based redaction beyond regex matching
are all designed in the full reference document but deliberately not built
at this stage — cut for time, not silently dropped, and none of them are the
part of the system that answers the core brief.
