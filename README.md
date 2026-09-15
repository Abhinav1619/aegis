# AEGIS

**A**utomated **E**valuation & **G**overnance for **I**nfrastructure **S**ecurity

An AI-augmented, vendor-agnostic network device compliance engine, built for Smart India Hackathon 2026 under NTRO's problem statement on multi-vendor network configuration compliance.

AEGIS reads a network device's configuration — any vendor, any format — automatically identifies its security-relevant settings using a tiered deterministic/AI pipeline, and checks them against real compliance frameworks: **CIS, NIST 800-53, DISA STIG, and ISO/IEC 27001 — all four named in the brief, all four with real cited rule content**, not placeholders. When it encounters syntax it hasn't seen before, it asks a human once via an in-app review queue, then recognizes it instantly on every device afterward — no code redeployment required to support a new vendor's syntax.

Full technical design: [`docs/architecture-document.md`](docs/architecture-document.md) (condensed 2-page version: [`docs/architecture-document-2page.md`](docs/architecture-document-2page.md)).

## Architecture at a glance

- **Backend**: FastAPI (Python), SQLite, a tiered resolution pipeline (deterministic pattern match → LLM classification with schema validation → human review queue with knowledge-base write-back), a 6-predicate-type deterministic rule engine, ReportLab PDF generation, Langfuse LLM observability.
- **Frontend**: Next.js 16 / React 19 / Tailwind v4 — a sidebar-shell console (Overview, Analyze device, Review queue, Insights, Contact) rather than a single upload form.
- **Frameworks**: control-family schema backed by NIST 800-53 (AC/AU/IA/SC/CM), so CIS/NIST/STIG/ISO rules all map onto one shared canonical model — 39 rules across all 4 as of this writing. Citations were checked against the real source document where one was available to us (CIS, STIG); pfSense and ISO content is wired in but not yet independently source-verified the same way — stated plainly, not glossed over (see `docs/architecture-document.md` §9/§10).

## Project structure

```
backend/            FastAPI app, rule engine, PDF generation
  app/
    rules/          Per-framework rule YAML: CIS (Cisco IOS XE + pfSense), NIST,
                     STIG, ISO 27001 - real cited content, see each file's own
                     header comment for verification status
  requirements.txt
  .env.example       Copy to .env and fill in real API keys
frontend/            Next.js app
  src/
  .env.local.example Copy to .env.local
samples/             Synthetic sample configs (Cisco IOS, pfSense, SONiC) for trying the app
docs/                Architecture documents + diagram
```

## Running it locally

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env       # then fill in GROQ_API_KEY / GEMINI_API_KEY / LANGFUSE_* keys
python -m uvicorn app.main:app --port 8000
```

The backend loads its embedding model and rule YAML files on startup and serves on `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open `http://localhost:3000`.

### Trying it out

Upload any file from `samples/` on the **Analyze device** page:
- `cisco_ios_sample.txt` — Cisco IOS `running-config` style
- `pfsense_config_sample.xml` — pfSense/Netgate XML export
- `sonic_config_db_sample.json` — SONiC `config_db.json`

Settings AEGIS can't classify automatically land in the **Review queue** — confirming one there teaches the system that pattern permanently (no redeploy).

## Known limitations

Stated honestly, not discovered by a judge first — see `docs/architecture-document.md` §10 ("Honest constraints") for the full list, including: rule/remediation content is a starter set pending domain-expert review, cross-referencing between related config lines is deferred (concrete example in the doc), and multi-tenancy is schema-ready but not enforcement-ready in this build.

## License

Built for Smart India Hackathon 2026. Not currently licensed for reuse outside the competition context.
