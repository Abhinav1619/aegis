"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Database, Clock, ShieldCheck, ScanSearch, Download, Inbox } from "lucide-react";
import { Stats, RecentConfig, getStats, getRecentConfigs, reportUrl } from "@/lib/api";
import { Panel, PageHeader, SectionLabel, KpiTile, Button, Table, Thead, Th, Td, Tr, EmptyState } from "@/components/ui";

export default function OverviewPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [recent, setRecent] = useState<RecentConfig[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getStats(), getRecentConfigs()])
      .then(([s, r]) => {
        setStats(s);
        setRecent(r);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  return (
    <div>
      <PageHeader
        title="Overview"
        description="How much AEGIS has learned so far, how findings were decided, and what still needs a human."
        actions={
          <Link href="/analyze">
            <Button variant="primary">
              <ScanSearch className="size-4" /> Analyze a device
            </Button>
          </Link>
        }
      />

      {error && <Panel className="p-4 border-rose-300 bg-rose-50 text-rose-800 text-sm mb-6">{error}</Panel>}

      {stats && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <KpiTile icon={ScanSearch} value={stats.devices_analyzed} label="Devices analyzed" color="slate" />
          <KpiTile icon={Database} value={stats.kb_entries_total} label="Patterns learned" color="indigo" />
          <KpiTile icon={Clock} value={stats.review_queue_pending} label="Waiting for review" color="amber" />
          <KpiTile
            icon={ShieldCheck}
            value={Object.values(stats.findings_by_tier).reduce((a, b) => a + b, 0)}
            label="Findings evaluated"
            color="emerald"
          />
        </div>
      )}

      <Panel>
        <div className="px-5 pt-5">
          <SectionLabel>Recent activity</SectionLabel>
        </div>
        {recent && recent.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="No devices analyzed yet"
            description="Upload a configuration from Analyze device to see it appear here."
          />
        ) : (
          <Table>
            <Thead>
              <tr>
                <Th>Device</Th>
                <Th>Vendor</Th>
                <Th>Analyzed</Th>
                <Th>Parse coverage</Th>
                <Th className="text-right">Report</Th>
              </tr>
            </Thead>
            <tbody>
              {recent?.map((c) => (
                <Tr key={c.config_id}>
                  <Td className="font-medium text-slate-900">{c.hostname ?? "—"}</Td>
                  <Td className="font-mono text-xs">{c.vendor}</Td>
                  <Td className="text-slate-500">
                    {c.created_at ? new Date(c.created_at).toLocaleString() : "—"}
                  </Td>
                  <Td>{c.parse_coverage_pct != null ? `${c.parse_coverage_pct}%` : "—"}</Td>
                  <Td className="text-right">
                    <a
                      href={reportUrl(c.config_id)}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-900"
                    >
                      <Download className="size-3.5" /> PDF
                    </a>
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Panel>
    </div>
  );
}
