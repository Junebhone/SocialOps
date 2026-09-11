"use client";

import { useMemo, useState } from "react";

import type { AgentRun, AgentTotals } from "@/lib/api";
import { cn } from "@/lib/utils";

const PAD = { top: 10, right: 12, bottom: 26, left: 40 };
const GAP = 2; // surface gap between adjacent bars/segments

function niceCeiling(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const normalized = value / magnitude;
  const step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return step * magnitude;
}

/**
 * p50 vs p95 latency per agent — the two series are the same unit and the
 * same underlying metric at two percentiles, so they share one hue at two
 * intensities rather than two categorical colors (dataviz: sequential
 * encoding for magnitude, not identity).
 */
export function LatencyChart({ totals }: { totals: AgentTotals[] }) {
  const width = 640;
  const height = 220;
  const plotW = width - PAD.left - PAD.right;
  const plotH = height - PAD.top - PAD.bottom;

  const [hover, setHover] = useState<{ agent: string; series: "p50" | "p95"; value: number } | null>(null);

  const rows = totals.filter((t) => t.runs > 0);
  const niceMax = niceCeiling(Math.max(1, ...rows.map((t) => Math.max(t.p50_latency_ms, t.p95_latency_ms))));
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(niceMax * f));
  const yFor = (v: number) => PAD.top + plotH - (v / niceMax) * plotH;
  const baseline = yFor(0);

  const slot = rows.length ? plotW / rows.length : plotW;
  const barW = Math.min(20, (slot - GAP * 3) / 2);

  if (rows.length === 0) {
    return <EmptyChart label="No completed runs yet — latency appears once an agent has run." />;
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <p className="text-sm font-medium">Latency by agent</p>
        <Legend items={[{ label: "p50", opacity: 0.9 }, { label: "p95", opacity: 0.4 }]} />
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label="p50 and p95 latency per agent, in milliseconds">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={width - PAD.right} y1={yFor(t)} y2={yFor(t)} className="stroke-border" strokeWidth={1} />
            <text x={PAD.left - 8} y={yFor(t)} textAnchor="end" dominantBaseline="middle" className="fill-muted-foreground text-[9px]">
              {t.toLocaleString()}
            </text>
          </g>
        ))}
        {rows.map((row, i) => {
          const slotX = PAD.left + i * slot;
          const x50 = slotX + (slot - barW * 2 - GAP) / 2;
          const x95 = x50 + barW + GAP;
          const h50 = Math.max(baseline - yFor(row.p50_latency_ms), 1);
          const h95 = Math.max(baseline - yFor(row.p95_latency_ms), 1);
          return (
            <g key={row.agent}>
              <rect
                x={x50}
                y={yFor(row.p50_latency_ms)}
                width={barW}
                height={h50}
                rx={3}
                className="fill-primary cursor-pointer"
                opacity={hover?.agent === row.agent && hover.series === "p50" ? 1 : 0.9}
                onMouseEnter={() => setHover({ agent: row.agent, series: "p50", value: row.p50_latency_ms })}
                onMouseLeave={() => setHover(null)}
              />
              <rect
                x={x95}
                y={yFor(row.p95_latency_ms)}
                width={barW}
                height={h95}
                rx={3}
                className="fill-primary cursor-pointer"
                opacity={hover?.agent === row.agent && hover.series === "p95" ? 0.65 : 0.4}
                onMouseEnter={() => setHover({ agent: row.agent, series: "p95", value: row.p95_latency_ms })}
                onMouseLeave={() => setHover(null)}
              />
              <text x={slotX + slot / 2} y={height - 8} textAnchor="middle" className="fill-muted-foreground text-[9.5px]">
                {row.agent}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="mt-1 h-5 text-xs text-muted-foreground">
        {hover ? (
          <span>
            <span className="font-medium text-foreground">{hover.agent}</span> {hover.series}:{" "}
            <span className="tabular-nums text-foreground">{hover.value.toLocaleString()} ms</span>
          </span>
        ) : (
          "Hover a bar for the exact figure."
        )}
      </div>
    </div>
  );
}

/**
 * Real call volume over time, bucketed from the runs actually returned by
 * `GET /agent_runs` — not a fabricated trend line. Scoped honestly to
 * whatever window that page covers (it says so beneath the chart).
 */
export function ActivityChart({ runs, totalRuns }: { runs: AgentRun[]; totalRuns: number }) {
  const width = 640;
  const height = 180;
  const plotW = width - PAD.left - PAD.right;
  const plotH = height - PAD.top - PAD.bottom;

  const [hover, setHover] = useState<number | null>(null);

  const buckets = useMemo(() => {
    if (runs.length === 0) return [];
    const times = runs.map((r) => new Date(r.created_at).getTime()).sort((a, b) => a - b);
    const spanMs = times[times.length - 1] - times[0];
    // Coarser buckets for a wider time span, finer for a short burst — aim
    // for roughly 12-20 bars regardless of how far back the page reaches.
    const bucketMs = Math.max(60_000, Math.ceil(spanMs / 16 / 60_000) * 60_000 || 60_000);
    const start = Math.floor(times[0] / bucketMs) * bucketMs;
    const counts = new Map<number, number>();
    for (const t of times) {
      const key = Math.floor((t - start) / bucketMs) * bucketMs + start;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return [...counts.entries()]
      .sort(([a], [b]) => a - b)
      .map(([bucketStart, count]) => ({ bucketStart, count }));
  }, [runs]);

  if (buckets.length === 0) {
    return <EmptyChart label="No runs yet — activity appears once the queue starts draining." />;
  }

  const maxCount = Math.max(1, ...buckets.map((b) => b.count));
  const niceMax = niceCeiling(maxCount);
  const yFor = (v: number) => PAD.top + plotH - (v / niceMax) * plotH;
  const baseline = yFor(0);
  const slot = plotW / buckets.length;
  const barW = Math.min(28, slot - GAP * 2);

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="mb-3 text-sm font-medium">Recent activity</p>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label="Agent run count over time">
        <line x1={PAD.left} x2={width - PAD.right} y1={baseline} y2={baseline} className="stroke-border" strokeWidth={1} />
        {buckets.map((b, i) => {
          const slotX = PAD.left + i * slot;
          const x = slotX + (slot - barW) / 2;
          const h = Math.max(baseline - yFor(b.count), 1);
          const active = hover === i;
          return (
            <rect
              key={b.bucketStart}
              x={x}
              y={yFor(b.count)}
              width={barW}
              height={h}
              rx={3}
              className="fill-primary cursor-pointer transition-opacity"
              opacity={active ? 1 : 0.8}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            />
          );
        })}
      </svg>
      <div className="mt-1 flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {hover !== null ? (
            <>
              <span className="font-medium text-foreground">{buckets[hover].count}</span> runs at{" "}
              {new Date(buckets[hover].bucketStart).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
            </>
          ) : (
            "Hover a bar for the exact count and time."
          )}
        </span>
        <span>
          newest {runs.length} of {totalRuns.toLocaleString()} total
        </span>
      </div>
    </div>
  );
}

function Legend({ items }: { items: { label: string; opacity: number }[] }) {
  return (
    <div className="flex items-center gap-3">
      {items.map((item) => (
        <span key={item.label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-primary" style={{ opacity: item.opacity }} />
          {item.label}
        </span>
      ))}
    </div>
  );
}

function EmptyChart({ label }: { label: string }) {
  return (
    <div className={cn("flex h-[180px] items-center justify-center rounded-lg border border-dashed border-border text-sm text-muted-foreground")}>
      {label}
    </div>
  );
}
