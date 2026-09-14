"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, ScanSearch, ListChecks, BarChart3, Mail } from "lucide-react";
import { getStats } from "@/lib/api";

const LINKS = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/analyze", label: "Analyze device", icon: ScanSearch },
  { href: "/review-queue", label: "Review queue", icon: ListChecks },
  { href: "/stats", label: "Insights", icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname();
  const [pending, setPending] = useState<number | null>(null);

  useEffect(() => {
    getStats().then((s) => setPending(s.review_queue_pending)).catch(() => {});
  }, [pathname]);

  return (
    <aside className="w-60 shrink-0 bg-slate-900 text-slate-300 flex flex-col h-screen sticky top-0">
      {/* No logo/wordmark here - the top bar already carries the AEGIS
          brand identity at the same height, right next to this sidebar;
          repeating it here just duplicated it. This spacer only keeps the
          nav below aligned with the top bar's bottom edge. */}
      <div className="h-16 shrink-0 border-b border-white/10" />

      <nav className="flex-1 px-3 space-y-0.5 mt-3">
        {LINKS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center justify-between gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                active ? "bg-white/10 text-white" : "text-slate-400 hover:text-white hover:bg-white/5"
              }`}
            >
              <span className="flex items-center gap-2.5">
                <Icon className="size-4" strokeWidth={2} />
                {label}
              </span>
              {href === "/review-queue" && !!pending && (
                <span className="rounded-full bg-amber-500/90 text-slate-950 text-[11px] font-semibold px-1.5 py-0.5 leading-none">
                  {pending}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="px-3 pb-4 pt-3 border-t border-white/10 shrink-0">
        <Link
          href="/contact"
          className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
            pathname === "/contact" ? "bg-white/10 text-white" : "text-slate-400 hover:text-white hover:bg-white/5"
          }`}
        >
          <Mail className="size-4" strokeWidth={2} />
          Contact us
        </Link>
      </div>
    </aside>
  );
}
