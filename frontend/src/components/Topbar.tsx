"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Logo } from "@/components/ui";

/** Local time is read straight from the browser's own clock and its
 * Intl-reported IANA zone (e.g. "Asia/Kolkata") - no IP lookup, no location
 * permission, nothing sent anywhere. It just reflects whatever timezone the
 * viewer's own machine is already set to. */
function useLocalClock() {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    // Deferred via setTimeout(0), not called synchronously here - `now`
    // starts null so the server-rendered and first-client-rendered markup
    // match exactly (real Date() output would differ between the two and
    // trigger a hydration mismatch).
    const kickoff = setTimeout(() => setNow(new Date()), 0);
    const id = setInterval(() => setNow(new Date()), 30000);
    return () => {
      clearTimeout(kickoff);
      clearInterval(id);
    };
  }, []);
  return now;
}

export function Topbar() {
  const now = useLocalClock();
  const timeStr = now
    ? now.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
    : "--:--";
  let zoneAbbr = "";
  try {
    zoneAbbr = now
      ? new Intl.DateTimeFormat(undefined, { timeZoneName: "short" })
          .formatToParts(now)
          .find((p) => p.type === "timeZoneName")?.value ?? ""
      : "";
  } catch {
    zoneAbbr = "";
  }

  return (
    <header className="h-16 shrink-0 border-b-2 border-slate-300 bg-white flex items-center justify-between px-8 sticky top-0 z-20">
      <div className="flex items-center gap-3 min-w-0">
        <Logo size={26} className="text-slate-900 shrink-0" />
        <div className="min-w-0">
          <div className="text-lg font-bold tracking-tight text-slate-900 leading-none">AEGIS</div>
          <div className="text-[11px] text-slate-500 truncate leading-tight mt-0.5">
            Automated Evaluation &amp; Governance for Infrastructure Security
          </div>
        </div>
      </div>
      <div className="flex items-center gap-5 shrink-0">
        <div className="text-right hidden sm:block">
          <div className="text-sm font-semibold text-slate-800 tabular-nums leading-none">{timeStr}</div>
          <div className="text-[11px] text-slate-400 leading-tight mt-0.5">{zoneAbbr}</div>
        </div>
        <Link href="/contact" className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">
          Contact us
        </Link>
      </div>
    </header>
  );
}
