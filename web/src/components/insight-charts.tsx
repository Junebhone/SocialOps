"use client";

import { useMemo, useState } from "react";

import type { Post } from "@/lib/api";

const TOP_N = 10;

interface Row {
  post: Post;
  likes: number;
  comments: number;
  shares: number;
  engagement: number;
}

function toRows(posts: Post[]): Row[] {
  return posts
    .map((post) => {
      const likes = post.metrics_json.likes ?? 0;
      const comments = post.metrics_json.comments ?? 0;
      const shares = post.metrics_json.shares ?? 0;
      return { post, likes, comments, shares, engagement: likes + comments * 3 + shares * 5 };
    })
    .sort((a, b) => b.engagement - a.engagement);
}

/** Real aggregates over the posts the page fetched — sums and an average, never a forecast. */
export function StatTiles({ posts }: { posts: Post[] }) {
  const rows = useMemo(() => toRows(posts), [posts]);
  const totalEngagement = rows.reduce((n, r) => n + r.engagement, 0);
  const avg = rows.length ? Math.round(totalEngagement / rows.length) : 0;
  const best = rows[0];

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <Tile label="Total engagement" value={totalEngagement.toLocaleString()} sub={`across ${rows.length} posts`} />
      <Tile label="Avg per post" value={avg.toLocaleString()} sub="likes + 3×comments + 5×shares" />
      <Tile
        label="Top performer"
        value={best ? best.engagement.toLocaleString() : "—"}
        sub={best ? best.post.text : "no posts yet"}
        truncateSub
      />
    </div>
  );
}

function Tile({ label, value, sub, truncateSub }: { label: string; value: string; sub: string; truncateSub?: boolean }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-2xl tabular-nums">{value}</p>
      <p className={`mt-1 text-xs text-muted-foreground ${truncateSub ? "truncate" : ""}`}>{sub}</p>
    </div>
  );
}

/**
 * Ranked engagement per post. Bar length is the same weighted engagement
 * figure already printed in the table below — this is that number made
 * comparable at a glance, not a second metric.
 */
export function EngagementRanking({ posts }: { posts: Post[] }) {
  const rows = useMemo(() => toRows(posts), [posts]).slice(0, TOP_N);
  const max = Math.max(1, ...rows.map((r) => r.engagement));

  if (rows.length === 0) {
    return <EmptyPanel label="No posts yet — ranking appears once posts have metrics." />;
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <p className="text-sm font-medium">Top posts by engagement</p>
        <p className="text-xs text-muted-foreground">
          top {rows.length} of {posts.length}
        </p>
      </div>
      <div className="space-y-2.5">
        {rows.map((row) => (
          <div key={row.post.id} className="group">
            <div className="mb-1 flex items-baseline justify-between gap-3 text-xs">
              <span className="truncate text-foreground">{row.post.text}</span>
              <span className="shrink-0 font-mono tabular-nums font-semibold text-foreground">
                {row.engagement.toLocaleString()}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-[width] duration-300"
                style={{ width: `${(row.engagement / max) * 100}%` }}
              />
            </div>
            <div className="mt-1 hidden font-mono text-[11px] tabular-nums text-muted-foreground group-hover:block">
              {row.likes.toLocaleString()} likes · {row.comments.toLocaleString()} comments · {row.shares.toLocaleString()} shares
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const MIX_COLORS = {
  likes: "bg-primary",
  comments: "bg-status-good",
  shares: "bg-status-warn",
} as const;

/**
 * What each top post's engagement is actually made of. Categorical hues are
 * fixed by metric (likes/comments/shares), never reassigned by rank or value.
 */
export function MetricMix({ posts }: { posts: Post[] }) {
  const rows = useMemo(() => toRows(posts), [posts]).slice(0, TOP_N);
  const [hover, setHover] = useState<number | null>(null);

  if (rows.length === 0) {
    return <EmptyPanel label="No posts yet — mix appears once posts have metrics." />;
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <p className="text-sm font-medium">Engagement mix</p>
        <Legend />
      </div>
      <div className="space-y-2.5">
        {rows.map((row, i) => {
          const total = Math.max(1, row.likes + row.comments + row.shares);
          const active = hover === i;
          return (
            <div key={row.post.id}>
              <p className="mb-1 truncate text-xs text-foreground">{row.post.text}</p>
              <div
                className="flex h-3 overflow-hidden rounded-full bg-muted"
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
              >
                <Segment color={MIX_COLORS.likes} pct={(row.likes / total) * 100} dim={hover !== null && !active} />
                <Segment color={MIX_COLORS.comments} pct={(row.comments / total) * 100} dim={hover !== null && !active} />
                <Segment color={MIX_COLORS.shares} pct={(row.shares / total) * 100} dim={hover !== null && !active} />
              </div>
              {active && (
                <p className="mt-1 font-mono text-[11px] tabular-nums text-muted-foreground">
                  {row.likes.toLocaleString()} likes · {row.comments.toLocaleString()} comments · {row.shares.toLocaleString()} shares
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Segment({ color, pct, dim }: { color: string; pct: number; dim: boolean }) {
  if (pct <= 0) return null;
  return (
    <div
      className={`h-full ${color} transition-opacity`}
      style={{ width: `${pct}%`, marginRight: 1, opacity: dim ? 0.4 : 1 }}
    />
  );
}

function Legend() {
  return (
    <div className="flex items-center gap-3 text-xs text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-2.5 rounded-sm bg-primary" /> likes
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-2.5 rounded-sm bg-status-good" /> comments
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-2.5 rounded-sm bg-status-warn" /> shares
      </span>
    </div>
  );
}

function EmptyPanel({ label }: { label: string }) {
  return (
    <div className="flex h-32 items-center justify-center rounded-lg border border-dashed border-border text-sm text-muted-foreground">
      {label}
    </div>
  );
}
