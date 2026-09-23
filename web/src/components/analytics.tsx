"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  api,
  type Analytics as AnalyticsData,
  type Category,
  type CategoryPoint,
  type ResponseTimes,
  type SentimentPoint,
} from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * The Analytics page (ADR-0005). Every number is computed by SQL in
 * `GET /analytics`; this component only draws it. brand_id, from and to all
 * live in the URL (D17), so a shared link reproduces the same view.
 */

const PRESETS = [7, 30, 90] as const;

// Fixed per category, never reassigned by value, so a colour means the same
// thing on every chart and every day.
const CATEGORY_ORDER: Category[] = ["question", "complaint", "praise", "spam", "other"];
const CATEGORY_COLORS: Record<Category, string> = {
  question: "var(--primary)",
  complaint: "var(--status-bad)",
  praise: "var(--status-good)",
  spam: "var(--chart-4)",
  other: "var(--status-warn)",
};

export function Analytics() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const brandId = Number(searchParams.get("brand_id"));
  const from = searchParams.get("from") ?? undefined;
  const to = searchParams.get("to") ?? undefined;

  const [data, setData] = useState<AnalyticsData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);

  useEffect(() => {
    if (!brandId) return;
    const mine = ++generation.current;
    setData(null);
    api
      .analytics(brandId, { from, to })
      .then((result) => {
        if (mine !== generation.current) return;
        setData(result);
        setError(null);
      })
      .catch((err: Error) => {
        if (mine !== generation.current) return;
        setError(err.message);
      });
  }, [brandId, from, to]);

  function setRange(next: { from?: string; to?: string }) {
    const params = new URLSearchParams(searchParams.toString());
    for (const key of ["from", "to"] as const) {
      if (next[key]) params.set(key, next[key]);
      else params.delete(key);
    }
    router.replace(`${pathname}?${params}`);
  }

  function preset(days: number) {
    // Anchored on the end day the API reported, which is "today" in the
    // brand's time zone, not the viewer's.
    const end = data?.end ?? isoDay(new Date());
    setRange({ from: addDays(end, -(days - 1)), to: end });
  }

  if (!brandId) {
    return <Empty title="No brand selected" body="Pick a brand in the top bar to see its analytics." />;
  }

  const span = data ? daysBetween(data.start, data.end) + 1 : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-center gap-1.5">
          {PRESETS.map((days) => (
            <Button
              key={days}
              size="sm"
              variant={span === days ? "default" : "outline"}
              onClick={() => preset(days)}
            >
              Last {days} days
            </Button>
          ))}
        </div>
        <div className="flex items-end gap-2 text-xs text-muted-foreground">
          <DateField label="From" value={data?.start} onChange={(v) => setRange({ from: v, to: data?.end })} />
          <DateField label="To" value={data?.end} onChange={(v) => setRange({ from: data?.start, to: v })} />
          {data && <span className="pb-2">days in {data.timezone}</span>}
        </div>
      </div>

      {error && (
        <p className="rounded-md border border-status-bad-bg bg-status-bad-bg px-3 py-2 text-sm text-status-bad">
          {error}
        </p>
      )}

      {!data && !error && <p className="text-sm text-muted-foreground">Loading…</p>}

      {data && (
        <>
          <SummaryTiles data={data} />
          <SentimentTrend points={data.sentiment} start={data.start} end={data.end} />
          <CategoryVolume points={data.categories} start={data.start} end={data.end} />
          <ResponseTimeChart rt={data.response_times} />
        </>
      )}
    </div>
  );
}

function SummaryTiles({ data }: { data: AnalyticsData }) {
  const triaged = data.sentiment.reduce((n, p) => n + p.comments, 0);
  const weighted = data.sentiment.reduce((n, p) => n + p.avg_sentiment * p.comments, 0);
  const avg = triaged ? weighted / triaged : null;
  const rt = data.response_times;

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Tile label="Comments triaged" value={triaged.toLocaleString()} sub="in this date range" />
      <Tile
        label="Average sentiment"
        value={avg === null ? "—" : signed(avg)}
        sub="-2 hostile · 0 neutral · +2 delighted"
      />
      <Tile label="Replies published" value={rt.published.toLocaleString()} sub="approved and sent" />
      <Tile
        label="Median time to reply"
        value={rt.p50_seconds === null ? "—" : duration(rt.p50_seconds)}
        sub={rt.p95_seconds === null ? "no replies yet" : `95% within ${duration(rt.p95_seconds)}`}
      />
    </div>
  );
}

// --- sentiment trend ---------------------------------------------------------

const W = 720;
const H = 200;
const PAD = { top: 12, right: 12, bottom: 24, left: 32 };

function SentimentTrend({ points, start, end }: { points: SentimentPoint[]; start: string; end: string }) {
  const days = daysBetween(start, end) + 1;
  const x = (day: string) => PAD.left + (daysBetween(start, day) / Math.max(1, days - 1)) * (W - PAD.left - PAD.right);
  const y = (v: number) => PAD.top + ((2 - v) / 4) * (H - PAD.top - PAD.bottom);
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(p.day).toFixed(1)},${y(p.avg_sentiment).toFixed(1)}`).join("");

  return (
    <Panel title="Sentiment trend" note="daily average of triaged comments">
      {points.length === 0 ? (
        <EmptyChart />
      ) : (
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Daily average sentiment">
          {[2, 1, 0, -1, -2].map((v) => (
            <g key={v}>
              <line
                x1={PAD.left}
                x2={W - PAD.right}
                y1={y(v)}
                y2={y(v)}
                stroke="var(--border)"
                strokeDasharray={v === 0 ? undefined : "2 4"}
              />
              <text x={PAD.left - 8} y={y(v) + 3} textAnchor="end" fontSize="10" fill="var(--muted-foreground)">
                {signed(v, 0)}
              </text>
            </g>
          ))}
          <path d={path} fill="none" stroke="var(--primary)" strokeWidth="2" />
          {points.map((p) => (
            <circle key={p.day} cx={x(p.day)} cy={y(p.avg_sentiment)} r="3" fill="var(--primary)">
              <title>{`${p.day}: ${signed(p.avg_sentiment)} across ${p.comments} comments`}</title>
            </circle>
          ))}
          <AxisLabels start={start} end={end} y={H - 6} />
        </svg>
      )}
    </Panel>
  );
}

// --- category volume ---------------------------------------------------------

function CategoryVolume({ points, start, end }: { points: CategoryPoint[]; start: string; end: string }) {
  const days = daysBetween(start, end) + 1;
  const byDay = useMemo(() => {
    const map = new Map<string, Partial<Record<Category, number>>>();
    for (const p of points) {
      const row = map.get(p.day) ?? {};
      row[p.category] = p.comments;
      map.set(p.day, row);
    }
    return map;
  }, [points]);
  const max = Math.max(1, ...[...byDay.values()].map((row) => Object.values(row).reduce((a, b) => a + b, 0)));
  const slot = (W - PAD.left - PAD.right) / days;
  const barW = Math.max(1, slot * 0.7);
  const plotH = H - PAD.top - PAD.bottom;

  return (
    <Panel title="Comment volume by category" note={`peak ${max.toLocaleString()} per day`}>
      {points.length === 0 ? (
        <EmptyChart />
      ) : (
        <>
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Daily comments by category">
            <line x1={PAD.left} x2={W - PAD.right} y1={H - PAD.bottom} y2={H - PAD.bottom} stroke="var(--border)" />
            {[...byDay.entries()].map(([day, row]) => {
              let top = H - PAD.bottom;
              const left = PAD.left + daysBetween(start, day) * slot + (slot - barW) / 2;
              return CATEGORY_ORDER.filter((c) => row[c]).map((c) => {
                const h = ((row[c] ?? 0) / max) * plotH;
                top -= h;
                return (
                  <rect key={`${day}-${c}`} x={left} y={top} width={barW} height={h} fill={CATEGORY_COLORS[c]}>
                    <title>{`${day}: ${row[c]} ${c}`}</title>
                  </rect>
                );
              });
            })}
            <AxisLabels start={start} end={end} y={H - 6} />
          </svg>
          <Legend />
        </>
      )}
    </Panel>
  );
}

function Legend() {
  return (
    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {CATEGORY_ORDER.map((c) => (
        <span key={c} className="flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-sm" style={{ background: CATEGORY_COLORS[c] }} />
          {c}
        </span>
      ))}
    </div>
  );
}

// --- response times ----------------------------------------------------------

function ResponseTimeChart({ rt }: { rt: ResponseTimes }) {
  const max = Math.max(1, ...rt.histogram.map((b) => b.comments));

  return (
    <Panel title="Time to first response" note="comment posted → reply published">
      {rt.published === 0 ? (
        <EmptyChart label="No published replies in this range yet. Approve a draft in the Inbox to see one here." />
      ) : (
        <div className="space-y-2">
          {rt.histogram.map((b) => (
            <div key={b.label} className="grid grid-cols-[5.5rem_1fr_2.5rem] items-center gap-3 text-xs">
              <span className="text-muted-foreground">{b.label}</span>
              <div className="h-2.5 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-primary" style={{ width: `${(b.comments / max) * 100}%` }} />
              </div>
              <span className="text-right font-mono tabular-nums">{b.comments}</span>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

// --- shared pieces -----------------------------------------------------------

function AxisLabels({ start, end, y }: { start: string; end: string; y: number }) {
  return (
    <g fontSize="10" fill="var(--muted-foreground)">
      <text x={PAD.left} y={y}>
        {start}
      </text>
      <text x={W - PAD.right} y={y} textAnchor="end">
        {end}
      </text>
    </g>
  );
}

function Panel({ title, note, children }: { title: string; note: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-muted-foreground">{note}</p>
      </div>
      {children}
    </div>
  );
}

function Tile({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-2xl tabular-nums">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{sub}</p>
    </div>
  );
}

function DateField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string | undefined;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      {label}
      <input
        type="date"
        value={value ?? ""}
        onChange={(e) => e.target.value && onChange(e.target.value)}
        className={cn(
          "h-8 rounded-md border border-border bg-card px-2 text-sm text-foreground",
          "focus-visible:outline-2 focus-visible:outline-primary",
        )}
      />
    </label>
  );
}

function EmptyChart({ label = "No triaged comments in this date range." }: { label?: string }) {
  return <p className="py-10 text-center text-sm text-muted-foreground">{label}</p>;
}

function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-dashed border-border px-6 py-14 text-center">
      <p className="font-medium">{title}</p>
      <p className="mx-auto mt-1 max-w-prose text-sm text-muted-foreground">{body}</p>
    </div>
  );
}

// --- formatting and date maths -----------------------------------------------
// Dates are plain YYYY-MM-DD strings from the API, already in the brand's time
// zone. The maths runs in UTC so the viewer's own zone can never shift a day.

function daysBetween(a: string, b: string): number {
  return Math.round((Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`)) / 86_400_000);
}

function addDays(day: string, n: number): string {
  return isoDay(new Date(Date.parse(`${day}T00:00:00Z`) + n * 86_400_000));
}

function isoDay(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function signed(v: number, digits = 2): string {
  const s = v.toFixed(digits);
  return v > 0 ? `+${s}` : s;
}

function duration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  if (seconds < 86_400) return `${(seconds / 3600).toFixed(1)} h`;
  return `${(seconds / 86_400).toFixed(1)} days`;
}
