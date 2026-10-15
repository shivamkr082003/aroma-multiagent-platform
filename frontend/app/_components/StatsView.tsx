"use client";

import { useEffect, useState } from "react";
import { apiError, workspaceApi, type Stats } from "@/lib/workspace";
import { ErrorNote, ViewShell } from "./ViewShell";

// One series per chart, so one hue: orange-600 passes 3:1 on the white surface
// (orange-500 does not). Text always stays in slate ink, never the bar color.
const BAR = "bg-orange-600";
const TRACK = "bg-orange-100";

const GROUNDING_LABELS: Record<keyof Stats["grounding"], string> = {
  documents: "Your documents",
  web: "The web",
  both: "Documents + web",
  model: "Model knowledge only",
};

const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });

function shortDate(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function StatsView() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    workspaceApi.getStats().then(setStats).catch((err) => setError(apiError(err, "Could not load statistics.")));
  }, []);

  return (
    <ViewShell title="Statistics" subtitle="How you use Aroma: activity, speed and where answers come from.">
      <ErrorNote message={error} />
      {!stats ? (
        !error && <div className="h-64 animate-pulse rounded-2xl border border-slate-200 bg-white" aria-label="Loading statistics" />
      ) : (
        <div className="space-y-5">
          <KpiRow stats={stats} />
          <ActivityChart activity={stats.activity} />
          <div className="grid gap-5 lg:grid-cols-2">
            <Grounding grounding={stats.grounding} />
            <TopDocuments docs={stats.top_documents} />
          </div>
        </div>
      )}
    </ViewShell>
  );
}

function KpiRow({ stats }: { stats: Stats }) {
  const { totals, response_time: rt } = stats;
  const tiles = [
    { label: "Questions asked", value: compact.format(totals.questions) },
    { label: "Chats", value: compact.format(totals.chats) },
    { label: "Documents", value: totals.documents === null ? "—" : compact.format(totals.documents) },
    { label: "Median response", value: rt.median_s === null ? "—" : `${rt.median_s}s`, note: rt.p90_s !== null ? `90% under ${rt.p90_s}s` : undefined },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {tiles.map((t) => (
        <div key={t.label} className="rounded-2xl border border-slate-200 bg-white px-4 py-3.5 shadow-sm">
          <p className="text-[12px] font-medium text-slate-500">{t.label}</p>
          <p className="mt-1 text-[26px] font-semibold tracking-tight text-slate-900">{t.value}</p>
          {t.note && <p className="text-[11.5px] text-slate-400">{t.note}</p>}
        </div>
      ))}
    </div>
  );
}

function ActivityChart({ activity }: { activity: Stats["activity"] }) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(1, ...activity.map((d) => d.questions));
  const total = activity.reduce((sum, d) => sum + d.questions, 0);
  const peak = activity.reduce((best, d, i) => (d.questions > activity[best].questions ? i : best), 0);
  const CHART_H = 160;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-4 flex items-baseline justify-between">
        <h3 className="text-[13px] font-semibold text-slate-800">Questions per day</h3>
        <p className="text-[12px] text-slate-500">{total} in the last {activity.length} days</p>
      </div>

      {/* Headroom above the plot so the tooltip and peak label never collide with the title row. */}
      <div className="relative mt-9" style={{ height: CHART_H + 28 }}>
        {/* Recessive hairline grid: top (max) and baseline */}
        <div className="absolute inset-x-0 top-0 border-t border-slate-100" />
        <span className="absolute -top-2 left-0 bg-white pr-1 text-[10.5px] text-slate-400">{max}</span>
        <div className="absolute inset-x-0 border-t border-slate-200" style={{ top: CHART_H }} />

        <div className="absolute inset-y-0 left-6 right-0 top-0 flex" style={{ height: CHART_H }}>
          {activity.map((d, i) => {
            const height = d.questions ? Math.max(4, (d.questions / max) * CHART_H) : 0;
            const label = `${shortDate(d.date)}: ${d.questions} ${d.questions === 1 ? "question" : "questions"}`;
            return (
              // The whole column is the hit target, much larger than the bar itself.
              <button
                key={d.date}
                type="button"
                aria-label={label}
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
                onFocus={() => setHover(i)}
                onBlur={() => setHover(null)}
                className="relative flex h-full flex-1 items-end justify-center outline-none focus-visible:bg-orange-50/60"
              >
                {height > 0 && (
                  <span
                    className={`w-full max-w-[24px] rounded-t-[4px] transition-opacity ${BAR} ${hover !== null && hover !== i ? "opacity-40" : ""}`}
                    style={{ height }}
                  />
                )}
                {/* Selective direct label: only the busiest day */}
                {i === peak && d.questions > 0 && hover === null && (
                  <span className="absolute text-[11px] font-semibold text-slate-700" style={{ bottom: height + 4 }}>
                    {d.questions}
                  </span>
                )}
                {hover === i && (
                  <span
                    role="tooltip"
                    className="pointer-events-none absolute z-10 whitespace-nowrap rounded-lg bg-slate-900 px-2.5 py-1.5 text-[11.5px] text-white shadow-lg"
                    style={{ bottom: height + 8 }}
                  >
                    <span className="font-semibold">{d.questions}</span> · {shortDate(d.date)}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div className="absolute left-6 right-0 flex" style={{ top: CHART_H + 8 }}>
          {activity.map((d, i) => (
            <span key={d.date} className="flex-1 text-center text-[10.5px] text-slate-400">
              {i % 2 === activity.length % 2 || i === activity.length - 1 ? (i === activity.length - 1 ? "Today" : shortDate(d.date)) : ""}
            </span>
          ))}
        </div>
      </div>

      <details className="mt-2 text-[12px] text-slate-500">
        <summary className="cursor-pointer select-none hover:text-slate-800">View as table</summary>
        <table className="mt-2 w-full max-w-xs text-left">
          <thead>
            <tr className="text-slate-400"><th className="py-1 font-medium">Day</th><th className="py-1 text-right font-medium">Questions</th></tr>
          </thead>
          <tbody>
            {activity.map((d) => (
              <tr key={d.date} className="border-t border-slate-100"><td className="py-1">{shortDate(d.date)}</td><td className="py-1 text-right tabular-nums">{d.questions}</td></tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}

function HorizontalBars({ rows, empty }: { rows: { label: string; value: number; suffix?: string }[]; empty: string }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  if (rows.every((r) => r.value === 0)) return <p className="py-6 text-center text-[13px] text-slate-400">{empty}</p>;
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r.label}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-[12.5px]">
            <span className="truncate text-slate-700">{r.label}</span>
            <span className="shrink-0 tabular-nums text-slate-500">
              <span className="font-semibold text-slate-800">{r.value}</span>
              {r.suffix}
            </span>
          </div>
          <div className={`h-2 rounded-full ${TRACK}`}>
            {r.value > 0 && <div className={`h-2 rounded-full ${BAR}`} style={{ width: `${(r.value / max) * 100}%` }} />}
          </div>
        </li>
      ))}
    </ul>
  );
}

function Grounding({ grounding }: { grounding: Stats["grounding"] }) {
  const total = Object.values(grounding).reduce((a, b) => a + b, 0);
  const rows = (Object.keys(GROUNDING_LABELS) as (keyof Stats["grounding"])[]).map((key) => ({
    label: GROUNDING_LABELS[key],
    value: grounding[key],
    suffix: total ? ` · ${Math.round((grounding[key] / total) * 100)}%` : "",
  }));
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="text-[13px] font-semibold text-slate-800">Where answers came from</h3>
      <p className="mb-4 mt-0.5 text-[12px] text-slate-500">Based on the sources each answer cited.</p>
      <HorizontalBars rows={rows} empty="No answers yet." />
    </section>
  );
}

function TopDocuments({ docs }: { docs: Stats["top_documents"] }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="text-[13px] font-semibold text-slate-800">Most-cited documents</h3>
      <p className="mb-4 mt-0.5 text-[12px] text-slate-500">Number of answers that cited each document.</p>
      <HorizontalBars
        rows={docs.map((d) => ({ label: d.title, value: d.answers, suffix: d.answers === 1 ? " answer" : " answers" }))}
        empty="Upload a document and ask about it to see it here."
      />
    </section>
  );
}
