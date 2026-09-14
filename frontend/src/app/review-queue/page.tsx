"use client";

import { useEffect, useState } from "react";
import { Check, X, HelpCircle, Sparkles, CheckCheck } from "lucide-react";
import {
  ReviewQueueItem,
  FieldMeta,
  confirmReviewItem,
  getCanonicalFields,
  listReviewQueue,
  rejectReviewItem,
} from "@/lib/api";
import {
  Panel,
  PageHeader,
  SectionLabel,
  Button,
  Badge,
  TechnicalDetails,
  Spinner,
  EmptyState,
  InlineToast,
  useToast,
} from "@/components/ui";

const REVIEWER_ID = "lead"; // single-reviewer demo; RBAC is schema-only for now (architecture-document.md §4)

export default function ReviewQueuePage() {
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [fieldMeta, setFieldMeta] = useState<Record<string, FieldMeta>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [toast, setToast] = useToast();

  useEffect(() => {
    Promise.all([listReviewQueue("pending"), getCanonicalFields()])
      .then(([q, f]) => {
        setItems(q);
        setFieldMeta(f);
        setSelectedId((prev) => prev ?? q[0]?.id ?? null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  function handleResolved(id: string, message: string) {
    setItems((prev) => {
      const next = prev.filter((i) => i.id !== id);
      setSelectedId((current) => (current === id ? next[0]?.id ?? null : current));
      return next;
    });
    setToast({ type: "success", text: message });
  }

  const selected = items.find((i) => i.id === selectedId) ?? null;

  return (
    <div>
      <PageHeader
        title="Review queue"
        description="Settings AEGIS couldn't classify on its own. Confirm the AI's guess, correct it, or say it isn't security-relevant — once resolved, AEGIS recognizes it instantly next time, on any device."
        actions={
          !loading && <Badge color={items.length > 0 ? "amber" : "emerald"}>{items.length} pending</Badge>
        }
      />

      <InlineToast toast={toast} />

      {error && <Panel className="p-4 border-rose-300 bg-rose-50 text-rose-800 text-sm mb-6">{error}</Panel>}

      {loading && (
        <div className="flex items-center gap-2 text-slate-500 text-sm">
          <Spinner className="size-4" /> Loading…
        </div>
      )}

      {!loading && items.length === 0 && !error && (
        <Panel>
          <EmptyState
            icon={CheckCheck}
            title="Nothing to review right now"
            description="Every setting AEGIS has seen so far was either recognized instantly or already confirmed."
          />
        </Panel>
      )}

      {!loading && items.length > 0 && (
        <div className="grid lg:grid-cols-[340px_1fr] gap-4 items-start">
          <Panel className="divide-y divide-slate-200 overflow-hidden">
            {items.map((item, i) => {
              const hasSuggestion = !!item.candidate_mapping && item.candidate_mapping.canonical_field !== "UNKNOWN";
              const isSelected = item.id === selectedId;
              return (
                <button
                  key={item.id}
                  onClick={() => setSelectedId(item.id)}
                  className={`w-full text-left px-4 py-3 flex gap-3 transition-colors border-l-4 ${
                    isSelected
                      ? "bg-slate-100 border-l-slate-900"
                      : "border-l-transparent hover:bg-slate-50"
                  }`}
                >
                  <span
                    className={`shrink-0 mt-0.5 flex items-center justify-center size-5 rounded-full text-[11px] font-semibold ${
                      isSelected ? "bg-slate-900 text-white" : "bg-slate-200 text-slate-600"
                    }`}
                  >
                    {i + 1}
                  </span>
                  <div className="min-w-0">
                    <div className="font-mono text-xs text-slate-700 truncate">{item.raw_unit}</div>
                    <div className="mt-1.5 flex items-center gap-1.5 text-xs">
                      {hasSuggestion ? (
                        <span className="flex items-center gap-1 text-indigo-600">
                          <Sparkles className="size-3" /> AI suggestion
                        </span>
                      ) : (
                        <span className="text-slate-400">No suggestion</span>
                      )}
                    </div>
                  </div>
                </button>
              );
            })}
          </Panel>

          {selected && (
            <ReviewDetail
              key={selected.id}
              item={selected}
              fieldMeta={fieldMeta}
              onResolved={handleResolved}
            />
          )}
        </div>
      )}
    </div>
  );
}

function ReviewDetail({
  item,
  fieldMeta,
  onResolved,
}: {
  item: ReviewQueueItem;
  fieldMeta: Record<string, FieldMeta>;
  onResolved: (id: string, message: string) => void;
}) {
  const suggestion = item.candidate_mapping;
  const hasRealSuggestion = !!suggestion && suggestion.canonical_field !== "UNKNOWN";
  const [mode, setMode] = useState<"default" | "manual">("default");
  const [canonicalField, setCanonicalField] = useState("");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(field: string, val: unknown) {
    setBusy(true);
    setErr(null);
    try {
      await confirmReviewItem(item.id, {
        canonical_field: field,
        value: val,
        reviewer_id: REVIEWER_ID,
        pattern_type: "exact",
        syntax_pattern: item.raw_unit,
      });
      onResolved(item.id, `Confirmed — AEGIS will recognize "${item.raw_unit.slice(0, 40)}" instantly next time.`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  async function handleNotApplicable() {
    setBusy(true);
    setErr(null);
    try {
      await rejectReviewItem(item.id, { reviewer_id: REVIEWER_ID, reason: "not_applicable" });
      onResolved(item.id, "Marked as not security-relevant — removed from the queue.");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <Panel className="p-5 space-y-4">
      <div>
        <SectionLabel>Raw configuration line</SectionLabel>
        <pre className="font-mono text-sm bg-slate-50 border border-slate-300 rounded-md p-3 whitespace-pre-wrap">
          {item.raw_unit}
        </pre>
      </div>

      {hasRealSuggestion && mode === "default" && (
        <div className="rounded-md bg-indigo-50 border border-indigo-300 p-4">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-indigo-700 uppercase tracking-wide">
            <Sparkles className="size-3.5" /> AI suggestion
          </div>
          <div className="mt-1.5 text-sm text-slate-800">
            This looks like it sets{" "}
            <span className="font-semibold">{fieldMeta[suggestion!.canonical_field]?.label ?? suggestion!.canonical_field}</span>{" "}
            to <span className="font-semibold">{String(suggestion!.value)}</span>.
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="success" disabled={busy} onClick={() => submit(suggestion!.canonical_field, suggestion!.value)}>
              {busy ? <Spinner className="size-4" /> : <Check className="size-4" />}
              Yes, that&apos;s right
            </Button>
            <Button variant="secondary" disabled={busy} onClick={() => setMode("manual")}>
              <HelpCircle className="size-4" />
              Not quite — let me fix it
            </Button>
          </div>
          <TechnicalDetails label="Why the AI thinks this">
            <p className="text-xs text-slate-600">{suggestion!.reasoning}</p>
            <p className="text-xs text-slate-400 mt-1">
              Confidence {Math.round(suggestion!.confidence * 100)}% · maps to <span className="font-mono">{suggestion!.canonical_field}</span>
            </p>
          </TechnicalDetails>
        </div>
      )}

      {!hasRealSuggestion && mode === "default" && (
        <div className="rounded-md bg-slate-50 border border-slate-300 p-4">
          <div className="text-sm text-slate-700">This doesn&apos;t look like a security-relevant setting to the AI.</div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="secondary" disabled={busy} onClick={handleNotApplicable}>
              {busy ? <Spinner className="size-4" /> : <X className="size-4" />}
              Correct, not a security setting
            </Button>
            <Button variant="secondary" disabled={busy} onClick={() => setMode("manual")}>
              Actually, it does — let me classify it
            </Button>
          </div>
          {suggestion?.reasoning && (
            <TechnicalDetails label="Why the AI thinks this">
              <p className="text-xs text-slate-600">{suggestion.reasoning}</p>
            </TechnicalDetails>
          )}
        </div>
      )}

      {mode === "manual" && (
        <ManualForm
          fieldMeta={fieldMeta}
          canonicalField={canonicalField}
          value={value}
          busy={busy}
          onFieldChange={setCanonicalField}
          onValueChange={setValue}
          onCancel={() => setMode("default")}
          onSubmit={() => submit(canonicalField, value)}
        />
      )}

      {err && <div className="text-rose-700 text-xs">{err}</div>}

      {item.similar_kb_entries && item.similar_kb_entries.length > 0 && (
        <TechnicalDetails label="Similar patterns already learned">
          <ul className="text-xs text-slate-500 space-y-0.5">
            {item.similar_kb_entries.slice(0, 3).map((s, i) => (
              <li key={i}>
                <span className="font-mono">{s.syntax_pattern}</span> → {s.canonical_field} ({s.similarity})
              </li>
            ))}
          </ul>
        </TechnicalDetails>
      )}
    </Panel>
  );
}

function ManualForm({
  fieldMeta,
  canonicalField,
  value,
  busy,
  onFieldChange,
  onValueChange,
  onCancel,
  onSubmit,
}: {
  fieldMeta: Record<string, FieldMeta>;
  canonicalField: string;
  value: string;
  busy: boolean;
  onFieldChange: (v: string) => void;
  onValueChange: (v: string) => void;
  onCancel: () => void;
  onSubmit: () => void;
}) {
  const selected = fieldMeta[canonicalField];
  return (
    <div className="rounded-md border border-slate-300 p-4 space-y-3">
      <SectionLabel>What does this actually control?</SectionLabel>
      <select
        value={canonicalField}
        onChange={(e) => onFieldChange(e.target.value)}
        className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900"
      >
        <option value="">— choose what this sets —</option>
        {Object.entries(fieldMeta).map(([field, meta]) => (
          <option key={field} value={field}>
            {meta.label}
          </option>
        ))}
      </select>
      {selected && <p className="text-xs text-slate-500">{selected.description}</p>}
      <input
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        placeholder="Value (e.g. true, 2, 10.0.0.5)"
        className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900"
      />
      <div className="flex gap-2">
        <Button variant="success" disabled={busy || !canonicalField} onClick={onSubmit}>
          {busy ? <Spinner className="size-4" /> : <Check className="size-4" />}
          Confirm
        </Button>
        <Button variant="ghost" disabled={busy} onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
