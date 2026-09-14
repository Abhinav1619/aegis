"use client";

import { useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  AlertTriangle,
  Lock,
  UploadCloud,
  ArrowRight,
  XCircle,
  HelpCircle,
  Download,
  Eye,
  Check,
} from "lucide-react";
import {
  ingestConfig,
  getCanonicalFields,
  getFrameworks,
  evaluateConfig,
  reportUrl,
  downloadPdf,
  IngestResult,
  EvaluateResult,
  FieldMeta,
} from "@/lib/api";
import { REDACTION_TYPE_LABELS } from "@/lib/copy";
import {
  Panel,
  PageHeader,
  SectionLabel,
  Button,
  Badge,
  TechnicalDetails,
  Spinner,
  PipelineTrail,
  SourceBadge,
  Table,
  Thead,
  Th,
  Td,
  Tr,
  StepState,
} from "@/components/ui";

const TAB_LABELS = ["Upload", "What we understood", "Check compliance", "Download report"];

// Session-only, not durable storage: this is purely so switching to another
// sidebar page and back doesn't wipe an in-progress analysis (Next.js
// unmounts this page's component on route change, which would otherwise
// reset every useState here). Closing the tab/browser clears it - the
// database, not this, is the durable record (see the Overview/Insights
// pages and each device's own PDF for that).
const STORAGE_KEY = "aegis:analyze-session";

type PersistedSession = {
  result: IngestResult | null;
  evaluation: EvaluateResult | null;
  selectedFrameworks: string[];
  activeTab: number;
};

export default function AnalyzePage() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IngestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fieldMeta, setFieldMeta] = useState<Record<string, FieldMeta>>({});
  const [frameworks, setFrameworks] = useState<string[]>([]);
  const [selectedFrameworks, setSelectedFrameworks] = useState<string[]>([]);
  const [evaluation, setEvaluation] = useState<EvaluateResult | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [evalError, setEvalError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [hydrated, setHydrated] = useState(false);
  const restoredFrameworksRef = useRef(false);

  // Restore a session left behind by navigating away, before the frameworks
  // fetch below would otherwise overwrite it with the "select everything"
  // default - and, critically, before the persist effect further down is
  // allowed to write anything at all. Without the `hydrated` gate there,
  // that effect fires on this same initial mount with the still-blank
  // starting state and overwrites the saved session with nulls a tick
  // before this restore callback gets to read it back.
  useEffect(() => {
    // Deferred a tick (not called synchronously here) so this reads as an
    // async subscription callback rather than a direct setState-in-effect -
    // same reasoning as the top bar clock above.
    const id = setTimeout(() => {
      try {
        const raw = sessionStorage.getItem(STORAGE_KEY);
        if (raw) {
          const saved: PersistedSession = JSON.parse(raw);
          if (saved.result) setResult(saved.result);
          if (saved.evaluation) setEvaluation(saved.evaluation);
          if (saved.selectedFrameworks?.length) {
            setSelectedFrameworks(saved.selectedFrameworks);
            restoredFrameworksRef.current = true;
          }
          if (typeof saved.activeTab === "number") setActiveTab(saved.activeTab);
        }
      } catch {
        // Corrupt or inaccessible sessionStorage - fall through to a fresh session.
      } finally {
        setHydrated(true);
      }
    }, 0);
    return () => clearTimeout(id);
  }, []);

  useEffect(() => {
    getCanonicalFields().then(setFieldMeta).catch(() => {});
    getFrameworks().then((fws) => {
      setFrameworks(fws);
      if (!restoredFrameworksRef.current) {
        setSelectedFrameworks(fws); // default: every loaded framework selected
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    // Not safe to write until the restore attempt above has finished - see
    // the comment on that effect.
    if (!hydrated) return;
    try {
      const session: PersistedSession = { result, evaluation, selectedFrameworks, activeTab };
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } catch {
      // Storage full/unavailable (private browsing, etc.) - losing the
      // draft on navigation is an acceptable fallback, not a hard failure.
    }
  }, [hydrated, result, evaluation, selectedFrameworks, activeTab]);

  // Only a single named framework or "no filter" (= every loaded framework)
  // is meaningful to the backend today - with exactly the frameworks that
  // exist right now, any selected set is either "all of them" or "exactly
  // one", so this mapping is always exact, not an approximation.
  const effectiveFramework = selectedFrameworks.length === frameworks.length ? undefined : selectedFrameworks[0];
  const frameworkLabel = selectedFrameworks.length === frameworks.length
    ? "All loaded frameworks"
    : selectedFrameworks.join(", ") || "None selected";

  async function handleCheckCompliance() {
    if (!result || selectedFrameworks.length === 0) return;
    setEvaluating(true);
    setEvalError(null);
    try {
      setEvaluation(await evaluateConfig(result.config_id, effectiveFramework));
    } catch (err) {
      setEvalError(err instanceof Error ? err.message : String(err));
    } finally {
      setEvaluating(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setEvaluation(null);
    try {
      const r = await ingestConfig(file);
      setResult(r);
      setActiveTab(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  const understood = result ? result.tier_counts.tier1 + result.tier_counts.tier2_accepted : 0;
  const needsReview = result?.tier_counts.tier3_pending ?? 0;

  const stepStates: StepState[] = [
    result ? "done" : "active",
    !result ? "upcoming" : "done",
    !result ? "upcoming" : evaluation ? "done" : "active",
    evaluation ? "active" : "upcoming",
  ];
  const steps = TAB_LABELS.map((label, i) => ({ label, state: stepStates[i] }));

  return (
    <div>
      <PageHeader
        title="Analyze device"
        description="Upload a network device configuration — any vendor, any format — to identify its security settings and check them against a compliance framework."
      />

      <Panel className="p-5 mb-6">
        <PipelineTrail steps={steps} activeIndex={activeTab} onSelect={setActiveTab} />
      </Panel>

      {error && <Panel className="p-4 border-rose-300 bg-rose-50 text-rose-800 text-sm mb-6">{error}</Panel>}

      {activeTab === 0 && (
        <Panel className="p-6">
          <form onSubmit={handleSubmit} className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 rounded-md border border-dashed border-slate-400 px-4 py-2.5 text-sm text-slate-600 cursor-pointer hover:border-slate-600 hover:bg-slate-50 transition-colors">
              <UploadCloud className="size-4.5 text-slate-400" />
              {file ? file.name : "Choose a file…"}
              <input type="file" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </label>
            <Button type="submit" variant="primary" disabled={!file || loading}>
              {loading && <Spinner className="size-4" />}
              {loading ? "Processing…" : "Upload & analyze"}
            </Button>
          </form>
          <p className="text-xs text-slate-500 mt-3">
            Any vendor, any format — a Cisco/pfSense-style text config, or a JSON config like SONiC.
          </p>
        </Panel>
      )}

      {activeTab === 1 && result && (
        <div className="space-y-5">
          <Panel
            className={`p-4 flex items-center justify-between gap-4 ${
              needsReview === 0 ? "bg-emerald-50 border-emerald-300" : "bg-amber-50 border-amber-300"
            }`}
          >
            <div className="flex items-center gap-3">
              {needsReview === 0 ? (
                <CheckCircle2 className="size-5 text-emerald-600 shrink-0" />
              ) : (
                <AlertTriangle className="size-5 text-amber-600 shrink-0" />
              )}
              <div className="text-sm font-medium text-slate-800">
                Detected as <span className="font-semibold">{result.vendor}</span> — understood{" "}
                {understood} of {result.total_units} settings automatically
                {needsReview > 0 && `, ${needsReview} need your review`}.
              </div>
            </div>
            {needsReview > 0 && (
              <a href="/review-queue">
                <Button variant="primary" className="!bg-amber-600 hover:!bg-amber-700 shrink-0">
                  Go review them <ArrowRight className="size-3.5" />
                </Button>
              </a>
            )}
          </Panel>

          {result.redaction_hits.length > 0 && (
            <Panel className="p-5">
              <div className="flex items-center gap-2 font-medium text-slate-800 text-sm">
                <Lock className="size-4 text-slate-500" />
                Secrets automatically hidden before any AI saw this file
              </div>
              <ul className="mt-2 text-sm text-slate-600 space-y-1">
                {result.redaction_hits.map((h) => (
                  <li key={h.type}>
                    {h.count}× {REDACTION_TYPE_LABELS[h.type] ?? h.type}
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          <Panel>
            <div className="px-5 pt-5">
              <SectionLabel>What we found</SectionLabel>
            </div>
            {Object.keys(result.fields).length === 0 ? (
              <div className="text-sm text-slate-500 px-5 pb-5">
                Nothing understood automatically yet — check the review queue.
              </div>
            ) : (
              <Table>
                <Thead>
                  <tr>
                    <Th className="w-1/3">Setting</Th>
                    <Th>Value</Th>
                  </tr>
                </Thead>
                <tbody>
                  {Object.entries(result.fields).map(([field, value]) => (
                    <Tr key={field}>
                      <Td>
                        <div className="text-sm font-medium text-slate-900">{fieldMeta[field]?.label ?? field}</div>
                        <div className="text-xs text-slate-400 font-mono mt-0.5">{field}</div>
                      </Td>
                      <Td className="font-mono text-xs break-words max-w-md">
                        {Array.isArray(value) ? (
                          <ul className="space-y-1">
                            {value.map((v, i) => (
                              <li key={i}>{String(v)}</li>
                            ))}
                          </ul>
                        ) : (
                          String(value)
                        )}
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Panel>

          <div className="flex justify-end">
            <Button variant="primary" onClick={() => setActiveTab(2)}>
              Continue to compliance check <ArrowRight className="size-4" />
            </Button>
          </div>
        </div>
      )}

      {activeTab === 2 && result && (
        <div className="space-y-5">
          <Panel className="p-5">
            <div className="flex items-center justify-between mb-3">
              <SectionLabel>Choose frameworks to check against</SectionLabel>
              <label className="flex items-center gap-2 text-sm font-medium text-slate-700 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={selectedFrameworks.length === frameworks.length && frameworks.length > 0}
                  onChange={(e) => setSelectedFrameworks(e.target.checked ? frameworks : [])}
                  className="size-4 rounded border-slate-400 accent-slate-900"
                />
                Select all
              </label>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {frameworks.map((fw) => {
                const active = selectedFrameworks.includes(fw);
                return (
                  <button
                    key={fw}
                    type="button"
                    onClick={() =>
                      setSelectedFrameworks((prev) =>
                        active ? prev.filter((f) => f !== fw) : [...prev, fw]
                      )
                    }
                    className={`relative aspect-square flex flex-col items-center justify-center gap-1.5 rounded-lg border-2 p-4 text-center transition-colors ${
                      active
                        ? "border-slate-900 bg-slate-900 text-white shadow-sm"
                        : "border-slate-300 bg-white text-slate-700 hover:border-slate-500"
                    }`}
                  >
                    {active && (
                      <span className="absolute top-2 right-2 flex items-center justify-center size-4 rounded-full bg-white text-slate-900">
                        <Check className="size-3" strokeWidth={3} />
                      </span>
                    )}
                    <span className="text-base font-bold">{fw}</span>
                    <span className={`text-[11px] ${active ? "text-slate-300" : "text-slate-500"}`}>Framework</span>
                  </button>
                );
              })}
            </div>
            <div className="flex items-center justify-between mt-4">
              <span className="text-xs text-slate-500">{frameworkLabel}</span>
              <Button variant="primary" disabled={evaluating || selectedFrameworks.length === 0} onClick={handleCheckCompliance}>
                {evaluating && <Spinner className="size-4" />}
                {evaluating ? "Checking…" : "Check compliance"}
              </Button>
            </div>
          </Panel>

          {evalError && <Panel className="p-4 border-rose-300 bg-rose-50 text-rose-800 text-sm">{evalError}</Panel>}

          {evaluation && <FindingsPanel evaluation={evaluation} frameworkLabel={frameworkLabel} onGoToReport={() => setActiveTab(3)} />}

          <TechnicalDetails>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <Stat label="Format" value={result.format} />
              <Stat label="Fingerprint confidence" value={result.fingerprint_confidence} />
              <Stat label="Total units" value={String(result.total_units)} />
              <Stat label="Parse coverage" value={`${result.parse_coverage_pct}%`} />
            </div>
          </TechnicalDetails>
        </div>
      )}

      {activeTab === 3 && (
        <ReportTab evaluation={evaluation} frameworkParam={effectiveFramework} />
      )}
    </div>
  );
}

function FindingsPanel({
  evaluation,
  frameworkLabel,
  onGoToReport,
}: {
  evaluation: EvaluateResult;
  frameworkLabel: string;
  onGoToReport: () => void;
}) {
  const { counts, findings } = evaluation;
  return (
    <Panel>
      <div className="flex items-center justify-between gap-2 px-5 pt-5">
        <div>
          <SectionLabel>Compliance findings</SectionLabel>
          <span className="text-xs text-slate-500">{frameworkLabel}</span>
        </div>
        <Button variant="primary" onClick={onGoToReport}>
          <Eye className="size-4" /> View full report
        </Button>
      </div>
      <div className="flex flex-wrap gap-4 text-sm px-5 pt-3">
        <span className="flex items-center gap-1.5 text-emerald-700 font-medium">
          <CheckCircle2 className="size-4" /> {counts.PASS} passed
        </span>
        <span className="flex items-center gap-1.5 text-rose-700 font-medium">
          <XCircle className="size-4" /> {counts.FAIL} need fixing
        </span>
        {counts.NOT_EVALUATED > 0 && (
          <span className="flex items-center gap-1.5 text-slate-500 font-medium">
            <HelpCircle className="size-4" /> {counts.NOT_EVALUATED} couldn&apos;t be checked
          </span>
        )}
      </div>

      <div className="mt-4">
        <Table>
          <Thead>
            <tr>
              <Th>Result</Th>
              <Th>Control</Th>
              <Th>Framework / ID</Th>
              <Th>Severity</Th>
              <Th>Source</Th>
            </tr>
          </Thead>
          <tbody>
            {findings.map((f) => (
              <Tr key={f.rule_id}>
                <Td>
                  <ResultBadge result={f.result} />
                </Td>
                <Td>
                  <div className="font-medium text-slate-900">{f.title ?? f.rule_id}</div>
                  {f.result === "FAIL" && f.remediation && (
                    <pre className="mt-1.5 font-mono text-xs bg-slate-50 border border-slate-300 rounded-md p-2 whitespace-pre-wrap">
                      {f.remediation}
                    </pre>
                  )}
                  {f.result === "FAIL" && !f.remediation && (
                    <div className="mt-1 text-xs text-slate-500 italic">No remediation template available yet.</div>
                  )}
                  {f.result === "NOT_EVALUATED" && (
                    <div className="mt-1 text-xs text-slate-500">
                      Not enough information to check this — reported as unknown, never assumed to pass.
                    </div>
                  )}
                </Td>
                <Td className="font-mono text-xs">
                  {f.framework} / {f.rule_id}
                </Td>
                <Td>{f.severity}</Td>
                <Td>
                  <SourceBadge tier={f.confidence_tier} />
                </Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      </div>
    </Panel>
  );
}

function ReportTab({ evaluation, frameworkParam }: { evaluation: EvaluateResult | null; frameworkParam: string | undefined }) {
  const [downloading, setDownloading] = useState(false);

  if (!evaluation) {
    return (
      <Panel className="p-8 text-center text-sm text-slate-500">
        Check compliance first — the report is built from those findings.
      </Panel>
    );
  }

  const deviceId = evaluation.device_id;
  const url = reportUrl(evaluation.config_id, frameworkParam);

  async function handleDownload() {
    setDownloading(true);
    try {
      await downloadPdf(url, `aegis-report-${deviceId}.pdf`);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="space-y-4">
      <Panel className="p-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <CheckCircle2 className="size-4 text-emerald-600" /> This is the exact PDF AEGIS will hand
          you — rendered on screen before you save it.
        </div>
        <Button variant="primary" onClick={handleDownload} disabled={downloading}>
          {downloading ? <Spinner className="size-4" /> : <Download className="size-4" />}
          {downloading ? "Preparing…" : "Download PDF"}
        </Button>
      </Panel>
      <Panel className="p-2 overflow-hidden">
        <iframe src={url} title="AEGIS compliance report preview" className="w-full h-[85vh] rounded-md" />
      </Panel>
    </div>
  );
}

function ResultBadge({ result }: { result: "PASS" | "FAIL" | "NOT_EVALUATED" }) {
  if (result === "PASS") return <Badge color="emerald">Pass</Badge>;
  if (result === "FAIL") return <Badge color="rose">Fail</Badge>;
  return <Badge color="slate">Unknown</Badge>;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-300 bg-slate-50 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-sm font-medium mt-0.5">{value}</div>
    </div>
  );
}
